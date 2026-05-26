#!/usr/bin/env python3
"""Generate MP3 pseudoword audio with gTTS for the validation task."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from gtts import gTTS

try:
    from pydub import AudioSegment
    from pydub.silence import detect_nonsilent
except Exception:  # pragma: no cover - optional post-processing dependency
    AudioSegment = None
    detect_nonsilent = None


ROOT = Path(__file__).resolve().parents[1]
LISTS_JSON = ROOT / "stimuli" / "participant_lists_plan2.json"
AUDIO_DIR = ROOT / "audio"
MANIFEST_PATH = AUDIO_DIR / "manifest.json"

PRACTICE_WORDS = [
    {"word": "nupa", "ttsText": "noo-pah", "kind": "practice"},
    {"word": "teebo", "ttsText": "tee-boh", "kind": "practice"},
    {"word": "moga", "ttsText": "moh-gah", "kind": "practice"},
    {"word": "safee", "ttsText": "sah-fee", "kind": "practice"},
    {"word": "looma", "ttsText": "loo-mah", "kind": "practice"},
]

LANG = "en"
TLD = "com"
SLOW = False
PAUSE_SECONDS = 0.2
LEADING_SILENCE_MS = 100
TARGET_DBFS = -20.0


def load_words() -> list[dict[str, Any]]:
    payload = json.loads(LISTS_JSON.read_text(encoding="utf-8"))
    rows_by_word: dict[str, dict[str, Any]] = {}
    for rows in payload["lists"].values():
        for row in rows:
            rows_by_word[row["word"]] = {
                "word": row["word"],
                "ttsText": row.get("ttsText") or row["word"],
                "ipaTarget": row.get("ipaTarget", ""),
                "kind": "main",
            }
    for row in PRACTICE_WORDS:
        rows_by_word[row["word"]] = row
    return [rows_by_word[word] for word in sorted(rows_by_word)]


def synthesize(row: dict[str, Any], out_path: Path, overwrite: bool) -> bool:
    if out_path.exists() and out_path.stat().st_size > 0 and not overwrite:
        return False
    tts = gTTS(text=row["ttsText"], lang=LANG, tld=TLD, slow=SLOW)
    tts.save(str(out_path))
    if not out_path.exists() or out_path.stat().st_size == 0:
        raise RuntimeError(f"gTTS failed to create {out_path}")
    trim_head_and_normalize(out_path)
    time.sleep(PAUSE_SECONDS)
    return True


def trim_head_and_normalize(audio_path: Path) -> None:
    if AudioSegment is None or detect_nonsilent is None:
        return

    audio = AudioSegment.from_file(audio_path)
    if audio.rms == 0:
        return

    silence_thresh = max(audio.dBFS - 16, -50)
    nonsilent = detect_nonsilent(audio, min_silence_len=20, silence_thresh=silence_thresh, seek_step=1)
    speech = audio[nonsilent[0][0]:] if nonsilent else audio
    gain_db = TARGET_DBFS - speech.dBFS
    peak_headroom = -speech.max_dBFS
    speech = speech.apply_gain(min(gain_db, peak_headroom))
    processed = AudioSegment.silent(duration=LEADING_SILENCE_MS) + speech
    processed.export(audio_path, format="mp3")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    rows = load_words()
    generated = 0
    skipped = 0
    for row in rows:
        out_path = AUDIO_DIR / f"{row['word'].lower()}.mp3"
        if synthesize(row, out_path, args.overwrite):
            generated += 1
        else:
            skipped += 1

    manifest = {
        "schema": "cssl-validation-gtts-audio-v1",
        "engine": "gTTS",
        "lang": LANG,
        "tld": TLD,
        "slow": SLOW,
        "generated": generated,
        "skippedExisting": skipped,
        "items": [
            {
                **row,
                "filename": f"{row['word'].lower()}.mp3",
            }
            for row in rows
        ],
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {generated}, skipped {skipped}; manifest: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
