#!/usr/bin/env python3
"""
Run ASR-based QA for generated pseudoword audio.

The ASR transcript is not treated as ground truth for pseudowords. It is a risk
screen: if the recognizer consistently hears a real English-like word, or if
two target items collapse to the same transcript, those items deserve manual
review before pilot collection.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "analysis" / "qa_outputs"
AUDIO_MANIFEST = ROOT / "audio" / "manifest.json"
PARTICIPANT_LISTS = ROOT / "stimuli" / "participant_lists_plan2.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_text(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower())


def levenshtein(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, start=1):
        current = [i]
        for j, right_char in enumerate(right, start=1):
            current.append(min(
                previous[j] + 1,
                current[j - 1] + 1,
                previous[j - 1] + (left_char != right_char),
            ))
        previous = current
    return previous[-1]


def similarity(left: str, right: str) -> float:
    length = max(len(left), len(right), 1)
    return round(1.0 - levenshtein(left, right) / length, 6)


def load_word_metadata() -> dict[str, dict[str, Any]]:
    payload = load_json(PARTICIPANT_LISTS)
    metadata: dict[str, dict[str, Any]] = {}
    list_ids_by_word: dict[str, set[str]] = defaultdict(set)
    for list_id, rows in payload["lists"].items():
        for row in rows:
            word = row["word"]
            metadata.setdefault(word, row)
            list_ids_by_word[word].add(list_id)
    for word, row in metadata.items():
        row["listIds"] = sorted(list_ids_by_word[word])
    return metadata


def target_words() -> list[str]:
    manifest = load_json(AUDIO_MANIFEST)
    return [item["word"] for item in manifest["items"]]


def closest_target(normalized_transcript: str, current_word: str) -> tuple[str, int | str, float | str]:
    candidates = [word for word in target_words() if word != current_word]
    if not normalized_transcript or not candidates:
        return "", "", ""
    scored = [
        (
            word,
            levenshtein(normalized_transcript, normalize_text(word)),
            similarity(normalized_transcript, normalize_text(word)),
        )
        for word in candidates
    ]
    scored.sort(key=lambda item: (item[1], -item[2], item[0]))
    return scored[0]


def transcribe_openai(audio_path: Path, model: str, prompt: str) -> str:
    from openai import OpenAI

    client = OpenAI()
    with audio_path.open("rb") as audio_file:
        result = client.audio.transcriptions.create(
            model=model,
            file=audio_file,
            prompt=prompt,
            response_format="json",
        )
    return str(getattr(result, "text", "")).strip()


def build_asr_rows(args: argparse.Namespace) -> list[dict[str, Any]]:
    manifest = load_json(AUDIO_MANIFEST)
    metadata = load_word_metadata()
    items = manifest["items"]
    if args.limit:
        items = items[:args.limit]

    has_api_key = bool(os.environ.get("OPENAI_API_KEY"))
    rows: list[dict[str, Any]] = []
    prompt = (
        "The audio contains exactly one short English-like pseudoword from a "
        "word-learning experiment. Preserve the syllables as heard. Return only "
        "the heard word or phrase."
    )

    for item in items:
        word = item["word"]
        meta = metadata.get(word, {})
        audio_path = ROOT / "audio" / item["filename"]
        transcript = ""
        status = "not_run"
        error = ""

        if not audio_path.exists():
            status = "missing_audio"
            error = "audio file does not exist"
        elif args.provider == "openai" and not has_api_key:
            status = "skipped_no_api_key"
        elif args.provider == "openai":
            try:
                transcript = transcribe_openai(audio_path, args.model, prompt)
                status = "completed"
            except Exception as exc:  # noqa: BLE001
                status = "api_error"
                error = str(exc).replace("\n", " ")[:500]
        else:
            status = "skipped_provider_none"

        normalized_transcript = normalize_text(transcript)
        normalized_word = normalize_text(word)
        distance = levenshtein(normalized_transcript, normalized_word) if normalized_transcript else ""
        target_similarity = similarity(normalized_transcript, normalized_word) if normalized_transcript else ""
        closest_word, closest_distance, closest_similarity = closest_target(normalized_transcript, word)
        transcript_has_spaces = int(bool(re.search(r"\s", transcript.strip())))
        english_like_risk = int(
            status == "completed"
            and bool(normalized_transcript)
            and (
                transcript_has_spaces
                or (isinstance(distance, int) and distance >= 3)
            )
        )
        closest_other_risk = int(
            status == "completed"
            and isinstance(closest_distance, int)
            and isinstance(distance, int)
            and closest_distance <= distance
        )

        rows.append({
            "word": word,
            "kind": item.get("kind", ""),
            "ttsText": item.get("ttsText", meta.get("ttsText", "")),
            "ipaTarget": item.get("ipaTarget", meta.get("ipaTarget", "")),
            "contrast": meta.get("contrast", "practice" if item.get("kind") == "practice" else ""),
            "contrastGroup": meta.get("contrastGroup", ""),
            "phonology": meta.get("phonology", "practice" if item.get("kind") == "practice" else ""),
            "listIds": "|".join(meta.get("listIds", [])),
            "audioFilename": item["filename"],
            "audioPath": str(audio_path),
            "provider": args.provider,
            "model": args.model if args.provider == "openai" else "",
            "asrStatus": status,
            "asrTranscript": transcript,
            "normalizedTranscript": normalized_transcript,
            "normalizedTarget": normalized_word,
            "editDistanceToTarget": distance,
            "similarityToTarget": target_similarity,
            "closestOtherTarget": closest_word,
            "closestOtherDistance": closest_distance,
            "closestOtherSimilarity": closest_similarity,
            "transcriptHasSpaces": transcript_has_spaces,
            "englishLikeTranscriptRisk": english_like_risk,
            "closestOtherTargetRisk": closest_other_risk,
            "error": error,
        })
    return rows


def build_summary_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    statuses = Counter(str(row["asrStatus"]) for row in rows)
    completed = [row for row in rows if row["asrStatus"] == "completed"]
    transcript_groups: dict[str, list[str]] = defaultdict(list)
    for row in completed:
        if row["normalizedTranscript"]:
            transcript_groups[str(row["normalizedTranscript"])].append(str(row["word"]))
    collisions = {
        transcript: words
        for transcript, words in transcript_groups.items()
        if len(words) > 1
    }
    english_like = [row["word"] for row in completed if int(row["englishLikeTranscriptRisk"]) == 1]
    closest_other = [row["word"] for row in completed if int(row["closestOtherTargetRisk"]) == 1]

    rows_out = [{
        "metric": "rows",
        "value": len(rows),
        "detail": "",
    }, {
        "metric": "completedCount",
        "value": len(completed),
        "detail": "",
    }, {
        "metric": "statusCounts",
        "value": json.dumps(statuses, sort_keys=True),
        "detail": "",
    }, {
        "metric": "transcriptCollisionCount",
        "value": len(collisions),
        "detail": json.dumps(collisions, sort_keys=True),
    }, {
        "metric": "englishLikeTranscriptRiskCount",
        "value": len(english_like),
        "detail": "|".join(english_like),
    }, {
        "metric": "closestOtherTargetRiskCount",
        "value": len(closest_other),
        "detail": "|".join(closest_other),
    }]
    return rows_out


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
    parser.add_argument("--provider", choices=["openai", "none"], default="openai")
    parser.add_argument("--model", default="gpt-4o-mini-transcribe")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    if args.limit < 0:
        raise SystemExit("--limit must be non-negative")
    return args


def main() -> None:
    args = parse_args()
    rows = build_asr_rows(args)
    summary_rows = build_summary_rows(rows)
    detail_path = args.out_dir / "audio_asr_review.csv"
    summary_path = args.out_dir / "audio_asr_summary.csv"
    write_csv(detail_path, rows)
    write_csv(summary_path, summary_rows)
    print(f"Wrote {detail_path}")
    print(f"Wrote {summary_path}")


if __name__ == "__main__":
    main()
