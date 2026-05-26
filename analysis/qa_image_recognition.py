#!/usr/bin/env python3
"""
Run automatic recognition-oriented QA for generated abstract object images.

The default check is deterministic and dependency-free: it reads the SVG object
IDs and uses the same visual-family formula as the generator/scheduler to label
the outline family, estimate nameability risk, and screen 5AFC option sets for
within-set label collisions. Optional OpenAI modes can be used as an additional
recognizer layer when an API key and, for true vision input, an SVG renderer are
available.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "analysis" / "qa_outputs"
IMAGE_DIR = ROOT / "images" / "objects"
STIMULUS_TOOLS = ROOT / "stimulus_tools"
sys.path.insert(0, str(STIMULUS_TOOLS))

from build_plan2_schedule import build_schedule, object_visual_family  # noqa: E402


HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}")
OBJECT_ID = re.compile(r"(\d+)")

SHAPE_LABELS = {
    0: "hexagon",
    1: "rounded_square",
    2: "bean_blob",
    3: "organic_blob",
    4: "star",
    5: "capsule",
    6: "pentagon",
    7: "ring",
}

NAMEABILITY = {
    "hexagon": (0.58, "moderate", "common geometric word, but less iconic than star/ring"),
    "rounded_square": (0.62, "moderate", "simple geometric label is available"),
    "bean_blob": (0.34, "low", "irregular shape has no single dominant English label"),
    "organic_blob": (0.38, "low", "irregular shape has no single dominant English label"),
    "star": (0.88, "high", "highly nameable common shape"),
    "capsule": (0.70, "moderate", "may invite pill/capsule labels"),
    "pentagon": (0.64, "moderate", "common geometric label is available"),
    "ring": (0.84, "high", "may invite ring/donut labels"),
}


def participant_ids(count: int) -> list[str]:
    return [f"QA{index:04d}" for index in range(1, count + 1)]


def image_kind(path: Path) -> str:
    return "practice" if path.name.startswith("practice_") else "main"


def object_id_from_path(path: Path) -> int:
    match = OBJECT_ID.search(path.stem)
    if not match:
        raise ValueError(f"Could not parse object id from {path}")
    return int(match.group(1))


def object_palette_index(object_id: int) -> int:
    variant = (object_id - 1) // 8
    return ((object_id - 1) * 3 + variant) % 8


def shape_label(object_id: int) -> str:
    return SHAPE_LABELS[object_visual_family(object_id)]


def svg_counts(svg_text: str) -> dict[str, int]:
    tags = ["path", "rect", "circle", "ellipse"]
    return {f"{tag}Count": svg_text.count(f"<{tag}") for tag in tags}


def deterministic_row(path: Path) -> dict[str, Any]:
    object_id = object_id_from_path(path)
    svg_text = path.read_text(encoding="utf-8")
    label = shape_label(object_id)
    risk_score, risk_level, reason = NAMEABILITY[label]
    colors = sorted(set(color.lower() for color in HEX_COLOR.findall(svg_text)))
    counts = svg_counts(svg_text)
    return {
        "objectId": object_id,
        "kind": image_kind(path),
        "filename": path.name,
        "imagePath": str(path),
        "visualFamily": object_visual_family(object_id),
        "shapeLabel": label,
        "nameabilityRiskScore": risk_score,
        "nameabilityRiskLevel": risk_level,
        "nameabilityReason": reason,
        "paletteIndex": object_palette_index(object_id),
        "colorCount": len(colors),
        "colors": "|".join(colors),
        **counts,
    }


def response_text(response: Any) -> str:
    text = getattr(response, "output_text", "")
    if text:
        return str(text)
    try:
        parts = []
        for output in getattr(response, "output", []):
            for item in getattr(output, "content", []):
                maybe_text = getattr(item, "text", "")
                if maybe_text:
                    parts.append(str(maybe_text))
        return "\n".join(parts)
    except Exception:  # noqa: BLE001
        return ""


def parse_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        return {}
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped).strip()
        stripped = re.sub(r"```$", "", stripped).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return {}
    return {}


def openai_svg_text_recognition(path: Path, model: str) -> tuple[str, dict[str, Any], str]:
    from openai import OpenAI

    svg_text = path.read_text(encoding="utf-8")
    prompt = (
        "You are checking abstract SVG stimuli for a word-learning experiment. "
        "Infer the most likely simple visual label a participant might assign. "
        "Return compact JSON with keys label, category, nameabilityRisk "
        "(low/moderate/high), and notes. Do not invent semantic object identity "
        "unless the image strongly implies one.\n\n"
        f"SVG:\n{svg_text}"
    )
    client = OpenAI()
    response = client.responses.create(
        model=model,
        input=[{
            "role": "user",
            "content": [{"type": "input_text", "text": prompt}],
        }],
    )
    text = response_text(response)
    return text, parse_json_object(text), ""


def render_svg_to_png(svg_path: Path, png_path: Path) -> str:
    png_path.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("rsvg-convert"):
        subprocess.run(["rsvg-convert", str(svg_path), "-o", str(png_path)], check=True)
        return "rsvg-convert"
    if shutil.which("magick"):
        subprocess.run(["magick", str(svg_path), str(png_path)], check=True)
        return "magick"
    if shutil.which("convert"):
        subprocess.run(["convert", str(svg_path), str(png_path)], check=True)
        return "convert"
    try:
        import cairosvg

        cairosvg.svg2png(url=str(svg_path), write_to=str(png_path))
        return "cairosvg"
    except ImportError as error:
        raise RuntimeError("no SVG renderer found: install rsvg-convert, ImageMagick, or cairosvg") from error


def openai_vision_recognition(path: Path, model: str, png_dir: Path) -> tuple[str, dict[str, Any], str]:
    from openai import OpenAI

    png_path = png_dir / f"{path.stem}.png"
    renderer = render_svg_to_png(path, png_path)
    client = OpenAI()
    with png_path.open("rb") as image_file:
        uploaded = client.files.create(file=image_file, purpose="vision")
    response = client.responses.create(
        model=model,
        input=[{
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": (
                        "This is an abstract object stimulus for a word-learning experiment. "
                        "Return compact JSON with keys label, category, nameabilityRisk "
                        "(low/moderate/high), and notes. Focus on what label a participant "
                        "might naturally use, not on artistic style."
                    ),
                },
                {"type": "input_image", "file_id": uploaded.id},
            ],
        }],
    )
    text = response_text(response)
    parsed = parse_json_object(text)
    parsed["renderer"] = renderer
    return text, parsed, renderer


def add_optional_recognition(
    rows: list[dict[str, Any]],
    provider: str,
    model: str,
    png_dir: Path,
    limit: int,
) -> list[dict[str, Any]]:
    has_api_key = bool(os.environ.get("OPENAI_API_KEY"))
    output: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        recognizer_status = "not_requested"
        recognizer_label = ""
        recognizer_category = ""
        recognizer_risk = ""
        recognizer_notes = ""
        recognizer_raw = ""
        recognizer_renderer = ""
        error = ""

        should_run = provider != "none" and (limit <= 0 or index < limit)
        if provider != "none" and not should_run:
            recognizer_status = "skipped_limit"
        elif should_run and not has_api_key:
            recognizer_status = "skipped_no_api_key"
        elif provider == "openai-svg" and should_run:
            try:
                recognizer_raw, parsed, recognizer_renderer = openai_svg_text_recognition(
                    Path(str(row["imagePath"])),
                    model,
                )
                recognizer_status = "completed"
                recognizer_label = str(parsed.get("label", ""))
                recognizer_category = str(parsed.get("category", ""))
                recognizer_risk = str(parsed.get("nameabilityRisk", ""))
                recognizer_notes = str(parsed.get("notes", ""))
            except Exception as exc:  # noqa: BLE001
                recognizer_status = "api_error"
                error = str(exc).replace("\n", " ")[:500]
        elif provider == "openai-vision" and should_run:
            try:
                recognizer_raw, parsed, recognizer_renderer = openai_vision_recognition(
                    Path(str(row["imagePath"])),
                    model,
                    png_dir,
                )
                recognizer_status = "completed"
                recognizer_label = str(parsed.get("label", ""))
                recognizer_category = str(parsed.get("category", ""))
                recognizer_risk = str(parsed.get("nameabilityRisk", ""))
                recognizer_notes = str(parsed.get("notes", ""))
                recognizer_renderer = str(parsed.get("renderer", recognizer_renderer))
            except Exception as exc:  # noqa: BLE001
                recognizer_status = "api_error"
                error = str(exc).replace("\n", " ")[:500]

        enriched = dict(row)
        enriched.update({
            "recognizerProvider": provider,
            "recognizerModel": model if provider != "none" else "",
            "recognizerStatus": recognizer_status,
            "recognizerLabel": recognizer_label,
            "recognizerCategory": recognizer_category,
            "recognizerNameabilityRisk": recognizer_risk,
            "recognizerRenderer": recognizer_renderer,
            "recognizerNotes": recognizer_notes,
            "recognizerRaw": recognizer_raw,
            "recognizerError": error,
        })
        output.append(enriched)
    return output


def build_image_rows(args: argparse.Namespace) -> list[dict[str, Any]]:
    paths = sorted(IMAGE_DIR.glob("*.svg"))
    rows = [deterministic_row(path) for path in paths]
    if args.provider == "openai-vision" and args.png_dir is None:
        with tempfile.TemporaryDirectory(prefix="cssl_image_recognition_") as temp_dir:
            return add_optional_recognition(rows, args.provider, args.model, Path(temp_dir), args.limit)
    png_dir = args.png_dir or (args.out_dir / "image_recognition_png")
    return add_optional_recognition(rows, args.provider, args.model, png_dir, args.limit)


def build_option_rows(
    image_rows: list[dict[str, Any]],
    participants: int,
    high_nameability_threshold: float,
) -> list[dict[str, Any]]:
    by_id = {int(row["objectId"]): row for row in image_rows}
    rows: list[dict[str, Any]] = []
    for participant_id in participant_ids(participants):
        schedule = build_schedule(participant_id)
        for block in schedule["testBlocks"]:
            for trial in block["trials"]:
                object_ids = [int(value) for value in trial["optionObjectIds"]]
                labels = [str(by_id[object_id]["shapeLabel"]) for object_id in object_ids]
                label_counts = Counter(labels)
                duplicate_labels = sorted(label for label, count in label_counts.items() if count > 1)
                high_nameability = [
                    object_id
                    for object_id in object_ids
                    if float(by_id[object_id]["nameabilityRiskScore"]) >= high_nameability_threshold
                ]
                rows.append({
                    "participantId": participant_id,
                    "listId": schedule["listId"],
                    "block": trial["block"],
                    "blockTrial": trial["blockTrial"],
                    "targetPairId": trial["targetPairId"],
                    "targetWord": trial["targetWord"],
                    "targetObjectId": trial["targetObjectId"],
                    "optionObjectIds": "|".join(str(value) for value in object_ids),
                    "optionShapeLabels": "|".join(labels),
                    "duplicateShapeLabels": "|".join(duplicate_labels),
                    "sameLabelFlagged": int(bool(duplicate_labels)),
                    "highNameabilityObjectIds": "|".join(str(value) for value in high_nameability),
                    "highNameabilityCount": len(high_nameability),
                })
    return rows


def build_summary_rows(
    image_rows: list[dict[str, Any]],
    option_rows: list[dict[str, Any]],
    provider: str,
    high_nameability_threshold: float,
) -> list[dict[str, Any]]:
    statuses = Counter(str(row["recognizerStatus"]) for row in image_rows)
    high_nameability = [
        f"{row['objectId']}:{row['shapeLabel']}"
        for row in image_rows
        if row["kind"] == "main" and float(row["nameabilityRiskScore"]) >= high_nameability_threshold
    ]
    same_label = [row for row in option_rows if int(row["sameLabelFlagged"]) == 1]
    high_option_sets = [row for row in option_rows if int(row["highNameabilityCount"]) > 0]
    return [{
        "metric": "imagesChecked",
        "value": len(image_rows),
        "detail": "",
    }, {
        "metric": "mainImages",
        "value": sum(1 for row in image_rows if row["kind"] == "main"),
        "detail": "",
    }, {
        "metric": "practiceImages",
        "value": sum(1 for row in image_rows if row["kind"] == "practice"),
        "detail": "",
    }, {
        "metric": "recognizerProvider",
        "value": provider,
        "detail": "",
    }, {
        "metric": "recognizerCompletedCount",
        "value": sum(1 for row in image_rows if row["recognizerStatus"] == "completed"),
        "detail": "",
    }, {
        "metric": "recognizerStatusCounts",
        "value": json.dumps(statuses, sort_keys=True),
        "detail": "",
    }, {
        "metric": "highNameabilityThreshold",
        "value": high_nameability_threshold,
        "detail": "",
    }, {
        "metric": "highNameabilityImageCount",
        "value": len(high_nameability),
        "detail": "|".join(high_nameability),
    }, {
        "metric": "testOptionSetsChecked",
        "value": len(option_rows),
        "detail": "",
    }, {
        "metric": "sameLabelFlaggedOptionSets",
        "value": len(same_label),
        "detail": "|".join(
            f"{row['participantId']}:b{row['block']}t{row['blockTrial']}={row['duplicateShapeLabels']}"
            for row in same_label[:20]
        ),
    }, {
        "metric": "optionSetsWithHighNameability",
        "value": len(high_option_sets),
        "detail": "",
    }]


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--participants", type=int, default=80)
    parser.add_argument("--provider", choices=["none", "openai-svg", "openai-vision"], default="none")
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--limit", type=int, default=0, help="Limit optional OpenAI recognition calls; 0 means all.")
    parser.add_argument("--high-nameability-threshold", type=float, default=0.80)
    parser.add_argument("--png-dir", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    if args.participants <= 0:
        raise SystemExit("--participants must be positive")
    if args.limit < 0:
        raise SystemExit("--limit must be non-negative")
    if not 0 <= args.high_nameability_threshold <= 1:
        raise SystemExit("--high-nameability-threshold must be between 0 and 1")
    return args


def main() -> None:
    args = parse_args()
    image_rows = build_image_rows(args)
    option_rows = build_option_rows(image_rows, args.participants, args.high_nameability_threshold)
    summary_rows = build_summary_rows(image_rows, option_rows, args.provider, args.high_nameability_threshold)

    detail_path = args.out_dir / "image_recognition_review.csv"
    option_path = args.out_dir / "image_recognition_option_sets.csv"
    summary_path = args.out_dir / "image_recognition_summary.csv"
    write_csv(detail_path, image_rows)
    write_csv(option_path, option_rows)
    write_csv(summary_path, summary_rows)
    print(f"Wrote {detail_path}")
    print(f"Wrote {option_path}")
    print(f"Wrote {summary_path}")


if __name__ == "__main__":
    main()
