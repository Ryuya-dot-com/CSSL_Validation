#!/usr/bin/env python3
"""
Run a lightweight QA check for visually similar abstract object stimuli.

This is not a psychophysical similarity model. It is a deterministic screen for
obvious collisions in generated SVG objects and in the 5AFC option sets produced
by the Plan 2 scheduler.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "analysis" / "qa_outputs"
IMAGE_DIR = ROOT / "images" / "objects"
STIMULUS_TOOLS = ROOT / "stimulus_tools"
sys.path.insert(0, str(STIMULUS_TOOLS))

from build_plan2_schedule import build_schedule  # noqa: E402


HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}")


@dataclass(frozen=True)
class ImageFeatures:
    object_id: int
    filename: str
    kind: str
    visual_family: int
    variant: int
    palette_index: int
    colors: tuple[str, ...]


def object_visual_family(object_id: int) -> int:
    variant = (object_id - 1) // 8
    return ((object_id - 1) + variant * 3) % 8


def object_palette_index(object_id: int) -> int:
    variant = (object_id - 1) // 8
    return ((object_id - 1) * 3 + variant) % 8


def image_kind(path: Path) -> str:
    return "practice" if path.name.startswith("practice_") else "main"


def object_id_from_path(path: Path) -> int:
    match = re.search(r"(\d+)", path.stem)
    if not match:
        raise ValueError(f"Could not parse object id from {path}")
    return int(match.group(1))


def extract_features(path: Path) -> ImageFeatures:
    object_id = object_id_from_path(path)
    text = path.read_text(encoding="utf-8")
    colors = tuple(sorted(set(color.lower() for color in HEX_COLOR.findall(text))))
    variant = (object_id - 1) // 8 if object_id < 900 else object_id - 900
    return ImageFeatures(
        object_id=object_id,
        filename=path.name,
        kind=image_kind(path),
        visual_family=object_visual_family(object_id),
        variant=variant,
        palette_index=object_palette_index(object_id),
        colors=colors,
    )


def color_jaccard(left: ImageFeatures, right: ImageFeatures) -> float:
    left_colors = set(left.colors)
    right_colors = set(right.colors)
    if not left_colors and not right_colors:
        return 0.0
    return len(left_colors & right_colors) / len(left_colors | right_colors)


def similarity_score(left: ImageFeatures, right: ImageFeatures) -> float:
    score = 0.0
    if left.visual_family == right.visual_family:
        score += 0.55
    if left.palette_index == right.palette_index:
        score += 0.18
    score += 0.22 * color_jaccard(left, right)
    if left.variant == right.variant:
        score += 0.05
    return round(min(score, 1.0), 6)


def load_features() -> dict[int, ImageFeatures]:
    features = {}
    for path in sorted(IMAGE_DIR.glob("*.svg")):
        feature = extract_features(path)
        features[feature.object_id] = feature
    return features


def build_pair_rows(
    features: dict[int, ImageFeatures],
    min_similarity: float,
) -> list[dict[str, Any]]:
    rows = []
    main_features = [feature for feature in features.values() if feature.kind == "main"]
    for left, right in itertools.combinations(main_features, 2):
        score = similarity_score(left, right)
        if score >= min_similarity:
            rows.append({
                "leftObjectId": left.object_id,
                "rightObjectId": right.object_id,
                "similarityScore": score,
                "sameVisualFamily": int(left.visual_family == right.visual_family),
                "samePalette": int(left.palette_index == right.palette_index),
                "colorJaccard": round(color_jaccard(left, right), 6),
                "leftFile": left.filename,
                "rightFile": right.filename,
            })
    rows.sort(key=lambda row: (-float(row["similarityScore"]), row["leftObjectId"], row["rightObjectId"]))
    return rows


def participant_ids(count: int) -> list[str]:
    return [f"QA{index:04d}" for index in range(1, count + 1)]


def build_option_flag_rows(
    features: dict[int, ImageFeatures],
    participants: int,
    min_similarity: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for participant_id in participant_ids(participants):
        schedule = build_schedule(participant_id)
        for block in schedule["testBlocks"]:
            for trial in block["trials"]:
                object_ids = [int(object_id) for object_id in trial["optionObjectIds"]]
                pair_scores = []
                for left_id, right_id in itertools.combinations(object_ids, 2):
                    pair_scores.append((
                        similarity_score(features[left_id], features[right_id]),
                        left_id,
                        right_id,
                    ))
                max_score, left_id, right_id = max(pair_scores)
                rows.append({
                    "participantId": participant_id,
                    "listId": schedule["listId"],
                    "block": trial["block"],
                    "blockTrial": trial["blockTrial"],
                    "targetPairId": trial["targetPairId"],
                    "targetWord": trial["targetWord"],
                    "optionObjectIds": "|".join(str(value) for value in object_ids),
                    "maxSimilarityScore": max_score,
                    "mostSimilarPair": f"{left_id}|{right_id}",
                    "flagged": int(max_score >= min_similarity),
                })
    return rows


def build_summary_rows(
    pair_rows: list[dict[str, Any]],
    option_rows: list[dict[str, Any]],
    min_similarity: float,
) -> list[dict[str, Any]]:
    flagged_options = [row for row in option_rows if int(row["flagged"]) == 1]
    return [{
        "metric": "minSimilarityThreshold",
        "value": min_similarity,
    }, {
        "metric": "flaggedObjectPairs",
        "value": len(pair_rows),
    }, {
        "metric": "testOptionSetsChecked",
        "value": len(option_rows),
    }, {
        "metric": "flaggedTestOptionSets",
        "value": len(flagged_options),
    }, {
        "metric": "flaggedTestOptionSetRate",
        "value": round(len(flagged_options) / len(option_rows), 6) if option_rows else "",
    }]


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows and not fieldnames:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = fieldnames or list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--participants", type=int, default=80)
    parser.add_argument("--min-similarity", type=float, default=0.55)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    if args.participants <= 0:
        raise SystemExit("--participants must be positive")
    if not 0 <= args.min_similarity <= 1:
        raise SystemExit("--min-similarity must be between 0 and 1")
    return args


def main() -> None:
    args = parse_args()
    features = load_features()
    pair_rows = build_pair_rows(features, args.min_similarity)
    option_rows = build_option_flag_rows(features, args.participants, args.min_similarity)
    summary_rows = build_summary_rows(pair_rows, option_rows, args.min_similarity)

    pair_path = args.out_dir / "image_pair_similarity_flags.csv"
    option_path = args.out_dir / "image_test_option_similarity.csv"
    summary_path = args.out_dir / "image_similarity_summary.csv"
    write_csv(pair_path, pair_rows, [
        "leftObjectId",
        "rightObjectId",
        "similarityScore",
        "sameVisualFamily",
        "samePalette",
        "colorJaccard",
        "leftFile",
        "rightFile",
    ])
    write_csv(option_path, option_rows)
    write_csv(summary_path, summary_rows)
    print(f"Wrote {pair_path}")
    print(f"Wrote {option_path}")
    print(f"Wrote {summary_path}")


if __name__ == "__main__":
    main()
