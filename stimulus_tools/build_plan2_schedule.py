#!/usr/bin/env python3
"""
Build a deterministic Plan 2 schedule from a participant ID.

The participant ID is hashed to assign a counterbalanced list and to seed all
within-list randomization. The generated schedule is intended to be loaded by
the future web task.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LIST_CSV = ROOT / "stimuli" / "participant_lists_plan2.csv"
CONFIG_JSON = ROOT / "config" / "task_design_plan2.json"
DEFAULT_OUT_DIR = ROOT / "schedules"
LIST_IDS = ["A", "B", "C", "D"]
MASK_32 = 0xFFFFFFFF
UINT_32 = 2**32


def stable_seed(text: str) -> int:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


class DeterministicRng:
    """Small JS-compatible PRNG for matching browser task schedules."""

    def __init__(self, seed: int) -> None:
        self.state = seed & MASK_32

    def random(self) -> float:
        self.state = (self.state + 0x6D2B79F5) & MASK_32
        value = self.state
        value = ((value ^ (value >> 15)) * (value | 1)) & MASK_32
        value = (
            value
            ^ ((value + (((value ^ (value >> 7)) * (value | 61)) & MASK_32)) & MASK_32)
        ) & MASK_32
        return ((value ^ (value >> 14)) & MASK_32) / UINT_32

    def choice(self, items: list[Any]) -> Any:
        if not items:
            raise ValueError("Cannot choose from an empty list")
        return items[int(self.random() * len(items))]

    def shuffle(self, items: list[Any]) -> None:
        for index in range(len(items) - 1, 0, -1):
            swap_index = int(self.random() * (index + 1))
            items[index], items[swap_index] = items[swap_index], items[index]


def load_config() -> dict[str, Any]:
    return json.loads(CONFIG_JSON.read_text(encoding="utf-8"))


def load_list(list_id: str) -> list[dict[str, Any]]:
    with LIST_CSV.open("r", encoding="utf-8", newline="") as f:
        rows = [row for row in csv.DictReader(f) if row["listId"] == list_id]
    if len(rows) != 20:
        raise ValueError(f"Expected 20 rows for list {list_id}, got {len(rows)}")
    for row in rows:
        row["listWordId"] = int(row["listWordId"])
        row["objectId"] = int(row["objectId"])
    return rows


def assign_list(seed: int) -> str:
    return LIST_IDS[seed % len(LIST_IDS)]


def nonempty_group(row: dict[str, Any]) -> str:
    return str(row.get("contrastGroup") or "")


def object_visual_family(object_id: int) -> int:
    variant = (int(object_id) - 1) // 8
    return ((int(object_id) - 1) + variant * 3) % 8


def trial_is_valid(candidates: list[dict[str, Any]]) -> bool:
    ids = [row["listWordId"] for row in candidates]
    if len(ids) != len(set(ids)):
        return False
    groups = [nonempty_group(row) for row in candidates if nonempty_group(row)]
    if len(groups) != len(set(groups)):
        return False
    visual_families = [object_visual_family(row["objectId"]) for row in candidates]
    if len(visual_families) != len(set(visual_families)):
        return False
    return True


def build_learning_block(
    words: list[dict[str, Any]],
    block: int,
    rng: DeterministicRng,
) -> list[dict[str, Any]]:
    word_by_id = {row["listWordId"]: row for row in words}
    remaining = {row["listWordId"]: 3 for row in words}
    pair_counts: dict[tuple[int, int], int] = defaultdict(int)
    trials: list[dict[str, Any]] = []

    for block_trial in range(1, 21):
        trial_rows: list[dict[str, Any]] = []
        for _slot in range(3):
            candidates = [
                word_by_id[word_id]
                for word_id, count in remaining.items()
                if count > 0 and word_by_id[word_id] not in trial_rows
            ]
            valid = []
            for candidate in candidates:
                proposed = trial_rows + [candidate]
                if not trial_is_valid(proposed):
                    continue
                pair_penalty = sum(
                    pair_counts[tuple(sorted((candidate["listWordId"], item["listWordId"])))]
                    for item in trial_rows
                )
                valid.append((pair_penalty, -remaining[candidate["listWordId"]], rng.random(), candidate))
            if not valid:
                raise RuntimeError("Could not build a valid learning trial")
            valid.sort(key=lambda item: item[:3])
            choice = valid[0][3]
            trial_rows.append(choice)
            remaining[choice["listWordId"]] -= 1

        object_positions = trial_rows[:]
        word_order = trial_rows[:]
        rng.shuffle(object_positions)
        rng.shuffle(word_order)
        for left in trial_rows:
            for right in trial_rows:
                if left["listWordId"] < right["listWordId"]:
                    pair_counts[(left["listWordId"], right["listWordId"])] += 1

        trials.append({
            "block": block,
            "blockTrial": block_trial,
            "trialType": "learning",
            "pairIds": [row["listWordId"] for row in trial_rows],
            "objectIds": [row["objectId"] for row in object_positions],
            "wordOrderPairIds": [row["listWordId"] for row in word_order],
            "words": [row["word"] for row in word_order],
            "objectPositions": {
                str(index + 1): row["objectId"]
                for index, row in enumerate(object_positions)
            },
        })

    if any(count != 0 for count in remaining.values()):
        raise RuntimeError(f"Unbalanced block {block}: {remaining}")
    return trials


def choose_foils(
    target: dict[str, Any],
    words: list[dict[str, Any]],
    rng: DeterministicRng,
) -> list[dict[str, Any]]:
    target_id = target["listWordId"]
    foils: list[dict[str, Any]] = []

    same_group = [
        row for row in words
        if row["listWordId"] != target_id
        and nonempty_group(row)
        and nonempty_group(row) == nonempty_group(target)
    ]
    if same_group:
        foils.append(rng.choice(same_group))

    def add_from(pool: list[dict[str, Any]]) -> None:
        used_visual_families = {object_visual_family(row["objectId"]) for row in [target] + foils}
        filtered_pool = [
            row for row in pool
            if row["listWordId"] != target_id
            and row["listWordId"] not in {foil["listWordId"] for foil in foils}
            and object_visual_family(row["objectId"]) not in used_visual_families
        ]
        if not filtered_pool:
            filtered_pool = [
                row for row in pool
                if row["listWordId"] != target_id
                and row["listWordId"] not in {foil["listWordId"] for foil in foils}
            ]
        if filtered_pool and len(foils) < 4:
            foils.append(rng.choice(filtered_pool))

    if target["contrast"] == "control":
        add_from([row for row in words if row["contrast"] == "control"])
        add_from([row for row in words if row["contrast"] == "control"])
        add_from([row for row in words if row["contrast"] != "control"])
        add_from([row for row in words if row["contrast"] != "control"])
    else:
        add_from([row for row in words if row["phonology"] == target["phonology"]])
        add_from([row for row in words if row["contrast"] not in ("control", target["contrast"])])
        add_from([row for row in words if row["contrast"] == "control"])

    while len(foils) < 4:
        add_from(words)
    return foils[:4]


def balanced_target_positions(
    trial_count: int,
    option_count: int,
    rng: DeterministicRng,
) -> list[int]:
    if trial_count % option_count != 0:
        raise ValueError(f"Cannot balance {trial_count} trials across {option_count} positions")
    repeats = trial_count // option_count
    positions = [
        position
        for position in range(1, option_count + 1)
        for _repeat in range(repeats)
    ]
    rng.shuffle(positions)
    return positions


def build_test_block(words: list[dict[str, Any]], block: int, rng: DeterministicRng) -> list[dict[str, Any]]:
    targets = words[:]
    rng.shuffle(targets)
    config = load_config()
    target_positions = balanced_target_positions(
        len(words),
        int(config["test"]["testOptions"]),
        rng,
    )
    trials = []
    for block_trial, target in enumerate(targets, 1):
        target_position = target_positions[block_trial - 1]
        foils = choose_foils(target, words, rng)
        rng.shuffle(foils)
        options = foils[:]
        options.insert(target_position - 1, target)
        trials.append({
            "block": block,
            "blockTrial": block_trial,
            "trialType": "test_5afc",
            "targetPairId": target["listWordId"],
            "targetWord": target["word"],
            "targetObjectId": target["objectId"],
            "optionPairIds": [row["listWordId"] for row in options],
            "optionObjectIds": [row["objectId"] for row in options],
            "targetPosition": target_position,
            "responseMethod": "click",
        })
    return trials


def build_schedule(participant_id: str, list_override: str | None = None) -> dict[str, Any]:
    seed = stable_seed(participant_id)
    list_id = list_override or assign_list(seed)
    if list_id not in LIST_IDS:
        raise ValueError(f"Unknown list ID: {list_id}")
    rng = DeterministicRng(seed)
    config = load_config()
    words = load_list(list_id)

    learning_blocks = []
    test_blocks = []
    for block in range(1, config["learning"]["blocks"] + 1):
        # Retry block generation with deterministic sub-seeds if constraints fail.
        for attempt in range(100):
            block_rng = DeterministicRng(seed + block * 1009 + attempt)
            try:
                learning_blocks.append({
                    "block": block,
                    "trials": build_learning_block(words, block, block_rng),
                })
                break
            except RuntimeError:
                continue
        else:
            raise RuntimeError(f"Could not generate learning block {block}")
        test_blocks.append({
            "block": block,
            "trials": build_test_block(words, block, rng),
        })

    return {
        "schema": "cssl-validation-plan2-schedule-v1",
        "participantId": participant_id,
        "seed": seed,
        "listId": list_id,
        "responseMode": {
            "learning": "click_or_keyboard",
            "test": "click_5afc",
        },
        "config": config,
        "words": words,
        "learningBlocks": learning_blocks,
        "testBlocks": test_blocks,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--participant-id", required=True)
    parser.add_argument("--list-id", choices=LIST_IDS, default=None)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    schedule = build_schedule(args.participant_id, args.list_id)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    safe_id = "".join(char if char.isalnum() or char in "-_" else "_" for char in args.participant_id)
    out_path = args.out_dir / f"sub-{safe_id}_plan2_schedule.json"
    out_path.write_text(json.dumps(schedule, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote schedule to {out_path}")


if __name__ == "__main__":
    main()
