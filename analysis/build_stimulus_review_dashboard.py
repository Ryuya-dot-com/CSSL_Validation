#!/usr/bin/env python3
"""
Build a browser-based stimulus QA dashboard from audio and image QA outputs.

The dashboard is intentionally static HTML. It lets reviewers play each MP3,
inspect the paired SVG object, and see ASR/image-recognition flags without
editing source files or opening multiple CSV tables.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "analysis" / "qa_outputs"
AUDIO_MANIFEST = ROOT / "audio" / "manifest.json"
PARTICIPANT_LISTS = ROOT / "stimuli" / "participant_lists_plan2.json"

PRACTICE_OBJECTS = {
    "nupa": 901,
    "teebo": 902,
    "moga": 903,
    "safee": 904,
    "looma": 905,
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_word_metadata() -> dict[str, dict[str, Any]]:
    payload = load_json(PARTICIPANT_LISTS)
    metadata: dict[str, dict[str, Any]] = {}
    list_ids_by_word: dict[str, set[str]] = defaultdict(set)
    object_ids_by_word: dict[str, set[int]] = defaultdict(set)
    assignments_by_word: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for list_id, rows in payload["lists"].items():
        for row in rows:
            word = row["word"]
            metadata.setdefault(word, dict(row))
            list_ids_by_word[word].add(list_id)
            object_ids_by_word[word].add(int(row["objectId"]))
            assignments_by_word[word].append({
                "listId": list_id,
                "listWordId": int(row["listWordId"]),
                "objectId": int(row["objectId"]),
            })

    for word, object_id in PRACTICE_OBJECTS.items():
        metadata.setdefault(word, {
            "word": word,
            "kind": "practice",
            "contrast": "practice",
            "contrastGroup": "",
            "phonology": "practice",
            "objectId": object_id,
        })
        object_ids_by_word[word].add(object_id)
        assignments_by_word[word].append({
            "listId": "practice",
            "listWordId": object_id,
            "objectId": object_id,
        })

    for word, row in metadata.items():
        row["listIds"] = sorted(list_ids_by_word[word])
        row["objectIds"] = sorted(object_ids_by_word[word])
        row["objectAssignments"] = sorted(
            assignments_by_word[word],
            key=lambda item: (str(item["listId"]), int(item["objectId"])),
        )
    return metadata


def row_by_key(rows: list[dict[str, str]], key: str) -> dict[str, dict[str, str]]:
    return {row[key]: row for row in rows if row.get(key)}


def object_filename(object_id: int) -> str:
    if object_id >= 900:
        return f"practice_{object_id}.svg"
    return f"object_{object_id:03d}.svg"


def rel_path(path: Path, report_path: Path) -> str:
    return Path(os.path.relpath(path, report_path.parent)).as_posix()


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def badge(text: str, tone: str = "neutral") -> str:
    if not text:
        return ""
    return f'<span class="badge {tone}">{esc(text)}</span>'


def risk_badge(value: str) -> str:
    tone = {
        "high": "warn",
        "moderate": "note",
        "low": "ok",
    }.get(value, "neutral")
    return badge(value, tone)


def bool_risk(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def image_cell(assignments: list[dict[str, Any]], image_by_id: dict[int, dict[str, str]], report_path: Path) -> str:
    parts = []
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for assignment in assignments:
        grouped[int(assignment["objectId"])].append(assignment)
    for object_id in sorted(grouped):
        filename = object_filename(object_id)
        image_path = ROOT / "images" / "objects" / filename
        image_row = image_by_id.get(object_id, {})
        shape = image_row.get("shapeLabel", "")
        risk = image_row.get("nameabilityRiskLevel", "")
        list_ids = "/".join(str(item["listId"]) for item in grouped[object_id])
        parts.append(
            '<div class="thumb-card">'
            f'<img src="{esc(rel_path(image_path, report_path))}" alt="object {object_id}">'
            f'<div class="thumb-meta">#{object_id} {esc(shape)} {risk_badge(risk)}</div>'
            f'<div class="thumb-meta">lists: {esc(list_ids)}</div>'
            "</div>"
        )
    return '<div class="thumb-grid">' + "".join(parts) + "</div>"


def asr_flags(asr_row: dict[str, str]) -> list[str]:
    flags = []
    if bool_risk(asr_row.get("englishLikeTranscriptRisk", "")):
        flags.append("English-like transcript")
    if bool_risk(asr_row.get("closestOtherTargetRisk", "")):
        flags.append("closer to other target")
    if asr_row.get("asrStatus") not in {"", "completed"}:
        flags.append(asr_row.get("asrStatus", "ASR not completed"))
    return flags


def audio_item_rows(report_path: Path) -> list[dict[str, Any]]:
    manifest = load_json(AUDIO_MANIFEST)
    metadata = load_word_metadata()
    audio_review_by_word = row_by_key(read_csv_rows(DEFAULT_OUT_DIR / "audio_review_template.csv"), "word")
    asr_by_word = row_by_key(read_csv_rows(DEFAULT_OUT_DIR / "audio_asr_review.csv"), "word")
    image_by_id = {
        int(row["objectId"]): row
        for row in read_csv_rows(DEFAULT_OUT_DIR / "image_recognition_review.csv")
        if row.get("objectId")
    }

    rows = []
    for item in manifest["items"]:
        word = item["word"]
        meta = metadata.get(word, {})
        audio_row = audio_review_by_word.get(word, {})
        asr_row = asr_by_word.get(word, {})
        assignments = list(meta.get("objectAssignments", []))
        object_ids = [int(value) for value in meta.get("objectIds", [])]
        rows.append({
            "word": word,
            "kind": item.get("kind", ""),
            "contrast": meta.get("contrast", audio_row.get("contrast", "")),
            "contrastGroup": meta.get("contrastGroup", audio_row.get("contrastGroup", "")),
            "phonology": meta.get("phonology", audio_row.get("phonology", "")),
            "ipaTarget": item.get("ipaTarget", audio_row.get("ipaTarget", "")),
            "ttsText": item.get("ttsText", audio_row.get("ttsText", "")),
            "nearestRealWords": meta.get("nearestRealWords", audio_row.get("nearestRealWords", "")),
            "audioSrc": rel_path(ROOT / "audio" / item["filename"], report_path),
            "audioFilename": item["filename"],
            "asr": asr_row,
            "asrFlags": asr_flags(asr_row),
            "imageHtml": image_cell(assignments, image_by_id, report_path) if assignments else "",
            "objectIds": object_ids,
        })
    return rows


def summary_lookup(path: Path) -> dict[str, str]:
    return {row["metric"]: row.get("value", "") for row in read_csv_rows(path) if row.get("metric")}


def readiness_counts() -> dict[str, int]:
    counts = {"FAIL": 0, "WARN": 0, "PASS": 0, "INFO": 0}
    for row in read_csv_rows(DEFAULT_OUT_DIR / "prepilot_readiness_checks.csv"):
        status = row.get("status", "")
        if status in counts:
            counts[status] += 1
    return counts


def summary_cards() -> str:
    asr = summary_lookup(DEFAULT_OUT_DIR / "audio_asr_summary.csv")
    image = summary_lookup(DEFAULT_OUT_DIR / "image_recognition_summary.csv")
    readiness = readiness_counts()
    cards = [
        ("Readiness FAIL", readiness.get("FAIL", 0), "bad" if readiness.get("FAIL", 0) else "ok"),
        ("Readiness WARN", readiness.get("WARN", 0), "warn" if readiness.get("WARN", 0) else "ok"),
        ("ASR completed", asr.get("completedCount", "missing"), "ok" if asr.get("completedCount") not in {"", "0", None} else "warn"),
        ("ASR status", asr.get("statusCounts", "missing"), "note"),
        ("Image option sets", image.get("testOptionSetsChecked", "missing"), "note"),
        ("Shape-label collisions", image.get("sameLabelFlaggedOptionSets", "missing"), "bad" if image.get("sameLabelFlaggedOptionSets") not in {"", "0", None} else "ok"),
        ("High-nameability images", image.get("highNameabilityImageCount", "missing"), "warn" if image.get("highNameabilityImageCount") not in {"", "0", None} else "ok"),
    ]
    return "".join(
        '<section class="summary-card">'
        f'<div class="summary-label">{esc(label)}</div>'
        f'<div class="summary-value {tone}">{esc(value)}</div>'
        "</section>"
        for label, value, tone in cards
    )


def flagged_image_section(report_path: Path) -> str:
    image_rows = read_csv_rows(DEFAULT_OUT_DIR / "image_recognition_review.csv")
    flagged = [
        row for row in image_rows
        if row.get("kind") == "main" and row.get("nameabilityRiskLevel") == "high"
    ]
    if not flagged:
        return "<p>No high-nameability images were flagged.</p>"
    cards = []
    for row in flagged:
        object_id = int(row["objectId"])
        image_path = ROOT / "images" / "objects" / object_filename(object_id)
        cards.append(
            '<div class="flag-card">'
            f'<img src="{esc(rel_path(image_path, report_path))}" alt="object {object_id}">'
            f'<div><strong>#{object_id}</strong> {esc(row.get("shapeLabel", ""))} '
            f'{risk_badge(row.get("nameabilityRiskLevel", ""))}</div>'
            f'<p>{esc(row.get("nameabilityReason", ""))}</p>'
            "</div>"
        )
    return '<div class="flag-grid">' + "".join(cards) + "</div>"


def audio_table(rows: list[dict[str, Any]]) -> str:
    table_rows = []
    for row in rows:
        flags = row["asrFlags"]
        flag_html = " ".join(badge(flag, "warn") for flag in flags) if flags else badge("no ASR risk flag", "ok")
        asr = row["asr"]
        audio_html = (
            f'<audio controls preload="none" src="{esc(row["audioSrc"])}"></audio>'
            f'<div class="small">{esc(row["audioFilename"])}</div>'
        )
        table_rows.append(
            "<tr>"
            f'<td><strong>{esc(row["word"])}</strong><div class="small">{esc(row["ttsText"])}</div></td>'
            f'<td>{esc(row["kind"])}<div>{badge(row["contrast"], "note")}</div></td>'
            f'<td>{esc(row["ipaTarget"])}<div class="small">{esc(row["nearestRealWords"])}</div></td>'
            f"<td>{audio_html}</td>"
            f'<td><div>{esc(asr.get("asrStatus", "missing"))}</div>'
            f'<div class="small">{esc(asr.get("asrTranscript", ""))}</div>'
            f'<div class="small">closest: {esc(asr.get("closestOtherTarget", ""))}</div>'
            f"<div>{flag_html}</div></td>"
            f'<td>{row["imageHtml"]}</td>'
            "</tr>"
        )
    return (
        '<table class="review-table">'
        "<thead><tr><th>Word</th><th>Group</th><th>Phonology</th><th>Audio</th><th>ASR</th><th>Object</th></tr></thead>"
        "<tbody>"
        + "".join(table_rows)
        + "</tbody></table>"
    )


def render_html(report_path: Path) -> str:
    rows = audio_item_rows(report_path)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CSSL Stimulus Review Dashboard</title>
  <style>
    :root {{
      color-scheme: light;
      --text: #1f2933;
      --muted: #64748b;
      --line: #d8dee9;
      --panel: #f7f9fc;
      --ok: #0f766e;
      --warn: #b45309;
      --bad: #b91c1c;
      --note: #2563eb;
    }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background: #ffffff;
    }}
    header {{
      padding: 28px 32px 18px;
      border-bottom: 1px solid var(--line);
    }}
    main {{
      padding: 22px 32px 40px;
    }}
    h1, h2 {{
      margin: 0 0 10px;
      line-height: 1.2;
    }}
    p {{
      color: var(--muted);
      max-width: 980px;
    }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 12px;
      margin: 18px 0 28px;
    }}
    .summary-card, .flag-card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 12px;
    }}
    .summary-label, .small {{
      color: var(--muted);
      font-size: 12px;
    }}
    .summary-value {{
      font-size: 18px;
      font-weight: 700;
      overflow-wrap: anywhere;
    }}
    .ok {{ color: var(--ok); }}
    .warn {{ color: var(--warn); }}
    .bad {{ color: var(--bad); }}
    .note {{ color: var(--note); }}
    .badge {{
      display: inline-block;
      margin: 2px 4px 2px 0;
      padding: 2px 7px;
      border-radius: 999px;
      border: 1px solid currentColor;
      font-size: 11px;
      font-weight: 600;
      white-space: nowrap;
    }}
    .neutral {{ color: var(--muted); }}
    .flag-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-bottom: 30px;
    }}
    .flag-card img {{
      width: 96px;
      height: 96px;
      display: block;
      margin-bottom: 8px;
    }}
    .review-table {{
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
      font-size: 14px;
    }}
    .review-table th, .review-table td {{
      border-top: 1px solid var(--line);
      padding: 10px;
      vertical-align: top;
      text-align: left;
    }}
    .review-table th {{
      position: sticky;
      top: 0;
      background: #eef3f8;
      z-index: 1;
    }}
    audio {{
      width: 180px;
      max-width: 100%;
    }}
    .thumb-grid {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .thumb-card {{
      width: 112px;
    }}
    .thumb-card img {{
      width: 86px;
      height: 86px;
      display: block;
    }}
    .thumb-meta {{
      font-size: 11px;
      color: var(--muted);
      overflow-wrap: anywhere;
    }}
  </style>
</head>
<body>
  <header>
    <h1>CSSL Stimulus Review Dashboard</h1>
    <p>Static review page generated from QA CSV files. Use it before pilot collection to play MP3s, inspect paired SVGs, and prioritize ASR or image-recognition warnings.</p>
  </header>
  <main>
    <h2>QA Summary</h2>
    <div class="summary-grid">{summary_cards()}</div>
    <h2>High-Nameability Images</h2>
    {flagged_image_section(report_path)}
    <h2>Audio And Object Review</h2>
    {audio_table(rows)}
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report_path = args.out_dir / "stimulus_review_dashboard.html"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_html(report_path), encoding="utf-8")
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    main()
