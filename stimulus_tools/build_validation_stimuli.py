#!/usr/bin/env python3
"""
Build a controlled pseudoword master set for CSSL mechanism validation.

The selected set is intended for testing when learners shift from graded
cross-situational evidence tracking to a more Propose-but-Verify-like state.
All generated items are pseudowords, and selected items are designed as
two-syllable forms.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cmudict

try:
    from wordfreq import zipf_frequency
except Exception:  # pragma: no cover - optional dependency
    zipf_frequency = None


ROOT = Path(__file__).resolve().parents[1]
STIMULI_DIR = ROOT / "stimuli"

TARGET_COUNTS = {
    "control": 20,
    "r_l": 4,
    "v_b": 4,
    "theta_s": 4,
    "cluster_r_l": 4,
    "cluster_v_b": 4,
}

CONTRAST_ORDER = [
    "control",
    "r_l",
    "v_b",
    "theta_s",
    "cluster_r_l",
    "cluster_v_b",
]

VOWEL_PHONES = {
    "a": "AE",
    "e": "EH",
    "i": "IH",
    "o": "AA",
    "u": "AH",
}

CONSONANT_PHONES = {
    "b": "B",
    "d": "D",
    "f": "F",
    "g": "G",
    "h": "HH",
    "k": "K",
    "l": "L",
    "m": "M",
    "n": "N",
    "p": "P",
    "r": "R",
    "s": "S",
    "t": "T",
    "v": "V",
    "w": "W",
    "z": "Z",
}

DIGRAPH_PHONES = {
    "th": "TH",
    "sh": "SH",
    "ch": "CH",
}

ARPABET_TO_IPA = {
    "AA": "ɑ",
    "AE": "æ",
    "AH": "ʌ",
    "B": "b",
    "D": "d",
    "EH": "ɛ",
    "F": "f",
    "G": "g",
    "HH": "h",
    "IH": "ɪ",
    "K": "k",
    "L": "l",
    "M": "m",
    "N": "n",
    "P": "p",
    "R": "ɹ",
    "S": "s",
    "T": "t",
    "TH": "θ",
    "V": "v",
    "W": "w",
    "Z": "z",
}

TTS_ONSET = {
    "r": "r",
    "l": "l",
    "v": "v",
    "b": "b",
    "th": "th",
    "s": "s",
    "kr": "kr",
    "kl": "kl",
    "vr": "vr",
    "br": "br",
}


@dataclass(frozen=True)
class Candidate:
    word: str
    phonology: str
    contrast: str
    contrast_group: str
    source: str
    syllables: tuple[str, str]
    syllable_template: str


@dataclass(frozen=True)
class ScoredCandidate:
    candidate: Candidate
    phones: tuple[str, ...]
    neighbor_size: int
    nearest_distance: int
    nearest_words: tuple[str, ...]
    real_word_zipf: float
    orth_length: int
    score: float


@dataclass
class CmuIndex:
    by_length: dict[int, list[tuple[str, tuple[str, ...]]]]
    phone_to_words: dict[tuple[str, ...], set[str]]
    substitution_index: dict[tuple[str, ...], set[str]]
    deletion_index: dict[tuple[str, ...], set[str]]


def strip_stress(phone: str) -> str:
    return re.sub(r"\d", "", phone)


def clean_word(word: str) -> str:
    return re.sub(r"[^a-z]", "", word.lower())


def grapheme_to_phones(word: str) -> tuple[str, ...]:
    word = clean_word(word)
    phones: list[str] = []
    i = 0
    while i < len(word):
        digraph = word[i : i + 2]
        if digraph in DIGRAPH_PHONES:
            phones.append(DIGRAPH_PHONES[digraph])
            i += 2
            continue
        char = word[i]
        if char in VOWEL_PHONES:
            phones.append(VOWEL_PHONES[char])
        elif char in CONSONANT_PHONES:
            phones.append(CONSONANT_PHONES[char])
        i += 1
    return tuple(phones)


def phones_to_ipa(phones: tuple[str, ...]) -> str:
    return "/" + "".join(ARPABET_TO_IPA.get(phone, phone.lower()) for phone in phones) + "/"


def tts_text(candidate: Candidate) -> str:
    first, second = candidate.syllables
    return f"{respell_syllable(first)}-{respell_syllable(second)}"


def respell_syllable(syllable: str) -> str:
    for onset in sorted(TTS_ONSET, key=len, reverse=True):
        if syllable.startswith(onset):
            return TTS_ONSET[onset] + syllable[len(onset):]
    return syllable


def wildcard_key(phones: tuple[str, ...], index: int) -> tuple[str, ...]:
    return phones[:index] + ("*",) + phones[index + 1 :]


def deletion_keys(phones: tuple[str, ...]) -> Iterable[tuple[str, ...]]:
    for index in range(len(phones)):
        yield phones[:index] + phones[index + 1 :]


def load_cmudict_index() -> CmuIndex:
    by_length: dict[int, list[tuple[str, tuple[str, ...]]]] = {}
    phone_to_words: dict[tuple[str, ...], set[str]] = {}
    substitution_index: dict[tuple[str, ...], set[str]] = {}
    deletion_index: dict[tuple[str, ...], set[str]] = {}
    seen: set[tuple[str, tuple[str, ...]]] = set()

    for word, phones in cmudict.entries():
        cleaned = clean_word(word)
        if not cleaned or cleaned != word.lower():
            continue
        if len(cleaned) < 2 or len(cleaned) > 12:
            continue
        phone_tuple = tuple(strip_stress(phone) for phone in phones)
        key = (cleaned, phone_tuple)
        if key in seen:
            continue
        seen.add(key)
        by_length.setdefault(len(phone_tuple), []).append(key)
        phone_to_words.setdefault(phone_tuple, set()).add(cleaned)
        for index in range(len(phone_tuple)):
            substitution_index.setdefault(wildcard_key(phone_tuple, index), set()).add(cleaned)
        for deletion_key in deletion_keys(phone_tuple):
            deletion_index.setdefault(deletion_key, set()).add(cleaned)

    return CmuIndex(by_length, phone_to_words, substitution_index, deletion_index)


def edit_distance(a: tuple[str, ...], b: tuple[str, ...], max_distance: int | None = None) -> int:
    if max_distance is not None and abs(len(a) - len(b)) > max_distance:
        return max_distance + 1

    previous = list(range(len(b) + 1))
    for i, pa in enumerate(a, 1):
        current = [i]
        row_min = current[0]
        for j, pb in enumerate(b, 1):
            cost = 0 if pa == pb else 1
            value = min(
                previous[j] + 1,
                current[j - 1] + 1,
                previous[j - 1] + cost,
            )
            current.append(value)
            row_min = min(row_min, value)
        previous = current
        if max_distance is not None and row_min > max_distance:
            return max_distance + 1
    return previous[-1]


def words_within_one_phone(phones: tuple[str, ...], cmu_index: CmuIndex) -> set[str]:
    words: set[str] = set(cmu_index.phone_to_words.get(phones, set()))
    for index in range(len(phones)):
        words.update(cmu_index.substitution_index.get(wildcard_key(phones, index), set()))
    words.update(cmu_index.deletion_index.get(phones, set()))
    for deletion_key in deletion_keys(phones):
        words.update(cmu_index.phone_to_words.get(deletion_key, set()))
    return words


def nearest_distance_and_words(
    phones: tuple[str, ...],
    cmu_index: CmuIndex,
    neighbor_words: set[str],
) -> tuple[int, tuple[str, ...]]:
    exact = cmu_index.phone_to_words.get(phones, set())
    if exact:
        return 0, tuple(sorted(exact)[:10])
    if neighbor_words:
        return 1, tuple(sorted(neighbor_words)[:10])

    nearest_words: list[str] = []
    nearest_distance = 4
    for length in range(len(phones) - 2, len(phones) + 3):
        if length < 1:
            continue
        for real_word, real_phones in cmu_index.by_length.get(length, []):
            distance = edit_distance(phones, real_phones, max_distance=3)
            if distance <= 3:
                if distance < nearest_distance:
                    nearest_distance = distance
                    nearest_words = [real_word]
                elif len(nearest_words) < 10:
                    nearest_words.append(real_word)
        if nearest_distance <= 3:
            break
    return nearest_distance, tuple(nearest_words[:10])


def score_candidate(candidate: Candidate, cmu_index: CmuIndex) -> ScoredCandidate:
    phones = grapheme_to_phones(candidate.word)
    neighbor_words = words_within_one_phone(phones, cmu_index)
    nearest_distance, nearest_words = nearest_distance_and_words(phones, cmu_index, neighbor_words)
    real_word_zipf = zipf_frequency(candidate.word, "en") if zipf_frequency else 0.0
    neighbor_size = len(neighbor_words)

    target_density = 4 if candidate.contrast == "control" else 3
    density_penalty = abs(math.log1p(neighbor_size) - math.log1p(target_density))
    if neighbor_size == 0:
        density_penalty += 0.75
    real_word_penalty = max(0.0, real_word_zipf - 1.0) * 3.0
    distance_bonus = min(nearest_distance, 3) * 0.25
    length_penalty = abs(len(candidate.word) - 6) * 0.08
    score = density_penalty + real_word_penalty + length_penalty - distance_bonus

    return ScoredCandidate(
        candidate=candidate,
        phones=phones,
        neighbor_size=neighbor_size,
        nearest_distance=nearest_distance,
        nearest_words=nearest_words,
        real_word_zipf=real_word_zipf,
        orth_length=len(candidate.word),
        score=score,
    )


def make_control_candidates() -> list[Candidate]:
    onsets = ["m", "n", "p", "t", "k", "s", "h", "f", "d", "g", "w"]
    vowels = ["a", "e", "i", "o", "u"]
    codas = ["m", "n", "p", "t", "k", "s"]
    candidates: list[Candidate] = []

    for onset1 in onsets:
        for vowel1 in vowels:
            for coda1 in codas:
                first = f"{onset1}{vowel1}{coda1}"
                for onset2 in ["m", "n", "p", "t", "k", "s"]:
                    if onset2 == onset1:
                        continue
                    for vowel2 in vowels:
                        if vowel2 == vowel1:
                            continue
                        for coda2 in ["m", "n", "t", "k", "s"]:
                            second = f"{onset2}{vowel2}{coda2}"
                            word = first + second
                            candidates.append(Candidate(
                                word=word,
                                phonology="easy",
                                contrast="control",
                                contrast_group="",
                                source="generated",
                                syllables=(first, second),
                                syllable_template="CVC-CVC",
                            ))
    return candidates


def make_contrast_candidates() -> list[Candidate]:
    specs = [
        ("r_l", "hard", ("r", "l"), "CVC-CVC", ["ekum", "alim", "opin", "uten", "afem", "edon", "ipak", "osim"]),
        ("v_b", "hard", ("v", "b"), "CVC-CVC", ["esam", "opin", "ekum", "adim", "uten", "afil", "osim", "ipak"]),
        ("theta_s", "hard", ("th", "s"), "CVC-CVC", ["ekun", "ipam", "udon", "afim", "open", "iten", "osak", "emut"]),
        ("cluster_r_l", "hard", ("kr", "kl"), "CCV-CVC", ["afem", "opin", "edum", "iten", "okun", "asem", "ipak", "udon"]),
        ("cluster_v_b", "hard", ("vr", "br"), "CCV-CVC", ["elok", "afem", "ipon", "udek", "amen", "osit", "ekum", "adon"]),
    ]
    candidates: list[Candidate] = []
    for contrast, phonology, onsets, template, rimes in specs:
        for rime in rimes:
            group = f"{onsets[0]}{rime}_{onsets[1]}{rime}"
            for onset in onsets:
                word = f"{onset}{rime}"
                if template == "CVC-CVC":
                    first = f"{onset}{rime[0]}{rime[1]}"
                    second = rime[2:]
                else:
                    first = f"{onset}{rime[0]}"
                    second = rime[1:]
                candidates.append(Candidate(
                    word=word,
                    phonology=phonology,
                    contrast=contrast,
                    contrast_group=group,
                    source="generated",
                    syllables=(first, second),
                    syllable_template=template,
                ))
    return candidates


def all_candidates() -> list[Candidate]:
    deduped: dict[str, Candidate] = {}
    controls = make_control_candidates()
    # The full combinatorial control pool is intentionally large, but scoring
    # every form against CMUdict is slow. Use a deterministic spread across the
    # generated space; this keeps regeneration reproducible without carrying a
    # fixed hand-picked list in the script.
    controls.sort(key=lambda candidate: stable_rank(candidate.word))
    for candidate in controls[:1200] + make_contrast_candidates():
        deduped.setdefault(candidate.word, candidate)
    return list(deduped.values())


def stable_rank(text: str) -> int:
    value = 0
    for index, char in enumerate(text, 1):
        value += index * ord(char) * 131
    return value % 1000003


def pair_distance_ok(
    selected: list[ScoredCandidate],
    candidate: ScoredCandidate,
    min_distance: int,
    allow_group: str | None = None,
) -> bool:
    for item in selected:
        same_allowed_group = allow_group and item.candidate.contrast_group == allow_group
        if same_allowed_group:
            continue
        if edit_distance(candidate.phones, item.phones, max_distance=min_distance - 1) < min_distance:
            return False
    return True


def control_balance_penalty(selected: list[ScoredCandidate], candidate: ScoredCandidate) -> float:
    syll1, syll2 = candidate.candidate.syllables
    features = [
        ("onset1", syll1[0]),
        ("vowel1", next((c for c in syll1 if c in VOWEL_PHONES), "")),
        ("coda1", syll1[-1]),
        ("onset2", syll2[0]),
        ("vowel2", next((c for c in syll2 if c in VOWEL_PHONES), "")),
        ("coda2", syll2[-1]),
    ]
    penalty = 0.0
    for feature, value in features:
        count = 0
        for item in selected:
            left, right = item.candidate.syllables
            if feature == "onset1":
                observed = left[0]
            elif feature == "vowel1":
                observed = next((c for c in left if c in VOWEL_PHONES), "")
            elif feature == "coda1":
                observed = left[-1]
            elif feature == "onset2":
                observed = right[0]
            elif feature == "vowel2":
                observed = next((c for c in right if c in VOWEL_PHONES), "")
            else:
                observed = right[-1]
            if observed == value:
                count += 1
        penalty += count * 0.08
    return penalty


def select_controls(scored: list[ScoredCandidate]) -> list[ScoredCandidate]:
    pool = [
        row for row in scored
        if row.candidate.contrast == "control"
        and row.real_word_zipf < 1.0
        and row.nearest_distance >= 1
        and row.neighbor_size <= 14
    ]
    selected: list[ScoredCandidate] = []
    while len(selected) < TARGET_COUNTS["control"]:
        ranked = sorted(
            [row for row in pool if row not in selected and pair_distance_ok(selected, row, min_distance=3)],
            key=lambda row: (row.score + control_balance_penalty(selected, row), row.candidate.word),
        )
        if not ranked:
            ranked = sorted(
                [row for row in pool if row not in selected and pair_distance_ok(selected, row, min_distance=2)],
                key=lambda row: (row.score + control_balance_penalty(selected, row), row.candidate.word),
            )
        if not ranked:
            raise RuntimeError("Could not select enough control stimuli")
        selected.append(ranked[0])
    return selected


def select_contrast_pairs(scored: list[ScoredCandidate], selected_so_far: list[ScoredCandidate]) -> list[ScoredCandidate]:
    selected: list[ScoredCandidate] = []
    for contrast in CONTRAST_ORDER:
        if contrast == "control":
            continue

        target = TARGET_COUNTS[contrast]
        groups: dict[str, list[ScoredCandidate]] = {}
        for row in scored:
            if row.candidate.contrast != contrast:
                continue
            if row.real_word_zipf >= 1.0 or row.nearest_distance == 0:
                continue
            groups.setdefault(row.candidate.contrast_group, []).append(row)

        group_scores: list[tuple[float, str, list[ScoredCandidate]]] = []
        for group, rows in groups.items():
            if len(rows) != 2:
                continue
            rows = sorted(rows, key=lambda row: row.candidate.word)
            density_gap = abs(rows[0].neighbor_size - rows[1].neighbor_size)
            score = sum(row.score for row in rows) + density_gap * 0.15
            group_scores.append((score, group, rows))
        group_scores.sort(key=lambda item: (item[0], item[1]))

        needed_pairs = target // 2
        added = 0
        for _score, group, rows in group_scores:
            comparison_set = selected_so_far + selected
            if all(pair_distance_ok(comparison_set, row, min_distance=2, allow_group=group) for row in rows):
                selected.extend(rows)
                added += 1
            if added == needed_pairs:
                break
        if added != needed_pairs:
            raise RuntimeError(f"Could not select enough pairs for {contrast}")
    return selected


def selected_set(scored: list[ScoredCandidate]) -> list[ScoredCandidate]:
    controls = select_controls(scored)
    contrasts = select_contrast_pairs(scored, controls)
    selected = controls + contrasts
    selected.sort(key=lambda row: (
        CONTRAST_ORDER.index(row.candidate.contrast),
        row.candidate.contrast_group,
        row.candidate.word,
    ))
    return selected


def row_dict(row: ScoredCandidate, selected: bool = False) -> dict[str, object]:
    candidate = row.candidate
    return {
        "selected": 1 if selected else 0,
        "word": candidate.word,
        "phonology": candidate.phonology,
        "contrast": candidate.contrast,
        "contrastGroup": candidate.contrast_group,
        "source": candidate.source,
        "syllableCount": len(candidate.syllables),
        "syllableTemplate": candidate.syllable_template,
        "syllable1": candidate.syllables[0],
        "syllable2": candidate.syllables[1],
        "phones": " ".join(row.phones),
        "phoneLength": len(row.phones),
        "orthLength": row.orth_length,
        "ipaTarget": phones_to_ipa(row.phones),
        "ttsText": tts_text(candidate),
        "phonologicalNeighborhoodSize": row.neighbor_size,
        "nearestRealWordDistance": row.nearest_distance,
        "nearestRealWords": "|".join(row.nearest_words),
        "englishZipfFrequency": round(row.real_word_zipf, 4),
        "selectionScore": round(row.score, 4),
    }


def write_csv(path: Path, rows: Iterable[dict[str, object]]) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        if not rows:
            return
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_pronunciation_json(path: Path, selected: list[ScoredCandidate], selected_csv: Path) -> None:
    items = []
    for row in selected:
        row_data = row_dict(row, selected=True)
        items.append({
            "word": row.candidate.word,
            "ipa": row_data["ipaTarget"],
            "arpabet": list(row.phones),
            "ttsText": row_data["ttsText"],
            "phonology": row.candidate.phonology,
            "contrast": row.candidate.contrast,
            "contrastGroup": row.candidate.contrast_group,
            "syllableCount": len(row.candidate.syllables),
            "syllableTemplate": row.candidate.syllable_template,
            "phonologicalNeighborhoodSize": row.neighbor_size,
            "nearestRealWordDistance": row.nearest_distance,
            "nearestRealWords": list(row.nearest_words),
            "notes": "IPA is the target pronunciation; ttsText is a practical audio-generation respelling.",
        })

    payload = {
        "metadata": {
            "schema": "cssl-validation-pronunciation-v1",
            "source": str(selected_csv),
            "itemCount": len(items),
            "allItemsTwoSyllables": all(item["syllableCount"] == 2 for item in items),
        },
        "items": items,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_manifest(path: Path, selected: list[ScoredCandidate]) -> None:
    payload = {
        "schema": "cssl-validation-stimulus-manifest-v1",
        "source": "stimulus_tools/build_validation_stimuli.py",
        "itemCount": len(selected),
        "targetCounts": TARGET_COUNTS,
        "words": [
            {
                "wordId": index + 1,
                "word": row.candidate.word,
                "phonology": row.candidate.phonology,
                "contrast": row.candidate.contrast,
                "contrastGroup": row.candidate.contrast_group,
                "syllableCount": len(row.candidate.syllables),
                "syllableTemplate": row.candidate.syllable_template,
                "ipaTarget": phones_to_ipa(row.phones),
                "ttsText": tts_text(row.candidate),
            }
            for index, row in enumerate(selected)
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_report(path: Path, selected: list[ScoredCandidate]) -> None:
    counts: dict[str, int] = {}
    for row in selected:
        counts[row.candidate.contrast] = counts.get(row.candidate.contrast, 0) + 1

    lines = [
        "# CSSL Validation Stimulus Review",
        "",
        "Generated by `stimulus_tools/build_validation_stimuli.py`.",
        "",
        "All selected items are intended as two-syllable pseudowords.",
        "`phonologicalNeighborhoodSize` counts CMUdict words with phone edit distance <= 1.",
        "`nearestRealWordDistance` is the minimum phone edit distance to a CMUdict entry.",
        "",
        "## Selected Counts",
        "",
    ]
    for key in CONTRAST_ORDER:
        lines.append(f"- {key}: {counts.get(key, 0)}")

    lines.extend(["", "## Selected Words", ""])
    for index, row in enumerate(selected, 1):
        lines.append(
            f"- {index:02d}. {row.candidate.word}: {row.candidate.contrast}, "
            f"{row.candidate.syllable_template}, phones={'.'.join(row.phones)}, "
            f"IPA={phones_to_ipa(row.phones)}, N={row.neighbor_size}, "
            f"nearest={row.nearest_distance} ({'|'.join(row.nearest_words[:4])})"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def assert_selected_set(selected: list[ScoredCandidate]) -> None:
    if len(selected) != sum(TARGET_COUNTS.values()):
        raise AssertionError(f"Expected {sum(TARGET_COUNTS.values())} selected items, got {len(selected)}")
    counts: dict[str, int] = {}
    words = [row.candidate.word for row in selected]
    if len(words) != len(set(words)):
        raise AssertionError("Selected words contain duplicates")
    for row in selected:
        counts[row.candidate.contrast] = counts.get(row.candidate.contrast, 0) + 1
        if len(row.candidate.syllables) != 2:
            raise AssertionError(f"Selected item is not two syllables: {row.candidate.word}")
        if row.real_word_zipf >= 1.0:
            raise AssertionError(f"Selected item may be real-word-like: {row.candidate.word}")
        if row.nearest_distance == 0:
            raise AssertionError(f"Selected item exactly matches CMUdict pronunciation: {row.candidate.word}")
    if counts != TARGET_COUNTS:
        raise AssertionError(f"Count mismatch: expected {TARGET_COUNTS}, got {counts}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=STIMULI_DIR)
    args = parser.parse_args()

    cmu_index = load_cmudict_index()
    scored = [score_candidate(candidate, cmu_index) for candidate in all_candidates()]
    selected = selected_set(scored)
    assert_selected_set(selected)

    selected_words = {row.candidate.word for row in selected}
    candidates_path = args.out_dir / "stimulus_candidates.csv"
    selected_path = args.out_dir / "stimulus_set_selected.csv"
    write_csv(
        candidates_path,
        [
            row_dict(row, selected=row.candidate.word in selected_words)
            for row in sorted(scored, key=lambda row: (
                CONTRAST_ORDER.index(row.candidate.contrast),
                row.score,
                row.candidate.word,
            ))
        ],
    )
    write_csv(selected_path, [row_dict(row, selected=True) for row in selected])
    write_pronunciation_json(args.out_dir / "pronunciation_ipa.json", selected, selected_path)
    write_manifest(args.out_dir / "stimulus_manifest.json", selected)
    write_report(args.out_dir / "stimulus_report.md", selected)
    print(f"Wrote {len(scored)} candidates and {len(selected)} selected stimuli to {args.out_dir}")


if __name__ == "__main__":
    main()
