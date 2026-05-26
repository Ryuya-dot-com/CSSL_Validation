#!/usr/bin/env python3
"""
Create audio-stimulus QA tables for manual review before pilot testing.

The output is intentionally a review template: it combines the generated gTTS
manifest with stimulus metadata, then leaves explicit columns for a human
reviewer to mark audibility, pronunciation quality, and possible confusions.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "analysis" / "qa_outputs"
AUDIO_MANIFEST = ROOT / "audio" / "manifest.json"
PARTICIPANT_LISTS = ROOT / "stimuli" / "participant_lists_plan2.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_word_metadata() -> dict[str, dict[str, Any]]:
    payload = load_json(PARTICIPANT_LISTS)
    metadata: dict[str, dict[str, Any]] = {}
    list_ids_by_word: dict[str, set[str]] = defaultdict(set)
    object_ids_by_word: dict[str, set[int]] = defaultdict(set)
    list_word_ids_by_word: dict[str, set[int]] = defaultdict(set)

    for list_id, rows in payload["lists"].items():
        for row in rows:
            word = row["word"]
            list_ids_by_word[word].add(list_id)
            object_ids_by_word[word].add(int(row["objectId"]))
            list_word_ids_by_word[word].add(int(row["listWordId"]))
            metadata.setdefault(word, row)

    for word, row in metadata.items():
        row["listIds"] = sorted(list_ids_by_word[word])
        row["objectIds"] = sorted(object_ids_by_word[word])
        row["listWordIds"] = sorted(list_word_ids_by_word[word])
    return metadata


def build_review_rows() -> list[dict[str, Any]]:
    manifest = load_json(AUDIO_MANIFEST)
    word_metadata = load_word_metadata()
    rows: list[dict[str, Any]] = []

    for index, item in enumerate(manifest["items"], start=1):
        word = item["word"]
        metadata = word_metadata.get(word, {})
        contrast = metadata.get("contrast", "practice" if item.get("kind") == "practice" else "")
        phonology = metadata.get("phonology", "practice" if item.get("kind") == "practice" else "")
        audio_path = ROOT / "audio" / item["filename"]
        rows.append({
            "reviewOrder": index,
            "word": word,
            "kind": item.get("kind", ""),
            "ttsText": item.get("ttsText", metadata.get("ttsText", "")),
            "ipaTarget": item.get("ipaTarget", metadata.get("ipaTarget", "")),
            "contrast": contrast,
            "contrastGroup": metadata.get("contrastGroup", ""),
            "phonology": phonology,
            "syllableTemplate": metadata.get("syllableTemplate", ""),
            "nearestRealWords": metadata.get("nearestRealWords", ""),
            "listIds": "|".join(metadata.get("listIds", [])),
            "objectIds": "|".join(str(value) for value in metadata.get("objectIds", [])),
            "audioFilename": item["filename"],
            "audioPath": str(audio_path),
            "audioExists": int(audio_path.exists()),
            "audioFileSizeBytes": audio_path.stat().st_size if audio_path.exists() else "",
            "attentionLevel": attention_level(item.get("kind", ""), str(contrast)),
            "reviewStatus": "",
            "audibleInChrome": "",
            "pronunciationAcceptable": "",
            "soundsLikeOtherTarget": "",
            "soundsLikeEnglishWord": "",
            "suspectedConfusionWord": "",
            "reviewerMemo": "",
        })
    return rows


def attention_level(kind: str, contrast: str) -> str:
    if kind == "practice":
        return "practice_check"
    if contrast and contrast != "control":
        return "hard_contrast_review"
    return "standard_check"


def build_summary_rows(review_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: Counter[tuple[str, str, str, str]] = Counter()
    missing_audio = 0
    for row in review_rows:
        grouped[(
            str(row["kind"]),
            str(row["contrast"]),
            str(row["phonology"]),
            str(row["attentionLevel"]),
        )] += 1
        missing_audio += 0 if row["audioExists"] else 1

    summary = [{
        "scope": "all",
        "kind": "",
        "contrast": "",
        "phonology": "",
        "attentionLevel": "",
        "count": len(review_rows),
        "missingAudioCount": missing_audio,
    }]
    for (kind, contrast, phonology, attention), count in sorted(grouped.items()):
        summary.append({
            "scope": "group",
            "kind": kind,
            "contrast": contrast,
            "phonology": phonology,
            "attentionLevel": attention,
            "count": count,
            "missingAudioCount": "",
        })
    return summary


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
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    review_rows = build_review_rows()
    summary_rows = build_summary_rows(review_rows)
    review_path = args.out_dir / "audio_review_template.csv"
    summary_path = args.out_dir / "audio_review_summary.csv"
    write_csv(review_path, review_rows)
    write_csv(summary_path, summary_rows)
    print(f"Wrote {review_path}")
    print(f"Wrote {summary_path}")


if __name__ == "__main__":
    main()
