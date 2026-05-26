#!/usr/bin/env python3
"""
Build 20-word participant lists for the adopted Plan 2 validation design.

Plan 2 uses a 40-word master bank but presents 20 words per participant.
This script builds four counterbalanced lists. Each list contains 10 easy
controls plus 10 hard words, with one minimal-pair group from each hard
contrast class.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STIMULI_DIR = ROOT / "stimuli"
SELECTED_CSV = STIMULI_DIR / "stimulus_set_selected.csv"
OUT_CSV = STIMULI_DIR / "participant_lists_plan2.csv"
OUT_JSON = STIMULI_DIR / "participant_lists_plan2.json"

CONTRASTS = ["r_l", "v_b", "theta_s", "cluster_r_l", "cluster_v_b"]
LIST_IDS = ["A", "B", "C", "D"]

CONTROL_GROUP_ASSIGNMENTS = {
    "A": (0, 1),
    "B": (0, 2),
    "C": (1, 3),
    "D": (2, 3),
}

HARD_GROUP_ASSIGNMENTS = {
    "A": (0, 0, 0, 0, 0),
    "B": (0, 1, 1, 0, 1),
    "C": (1, 0, 1, 1, 0),
    "D": (1, 1, 0, 1, 1),
}


def read_rows() -> list[dict[str, str]]:
    with SELECTED_CSV.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def split_controls(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    controls = [row for row in rows if row["contrast"] == "control"]
    controls.sort(key=lambda row: row["word"])
    if len(controls) != 20:
        raise ValueError(f"Expected 20 control items, got {len(controls)}")
    control_groups = [controls[index : index + 5] for index in range(0, len(controls), 5)]
    return {
        list_id: [
            row
            for group_index in CONTROL_GROUP_ASSIGNMENTS[list_id]
            for row in control_groups[group_index]
        ]
        for list_id in LIST_IDS
    }


def split_hard_groups(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    by_list: dict[str, list[dict[str, str]]] = {list_id: [] for list_id in LIST_IDS}
    for contrast_index, contrast in enumerate(CONTRASTS):
        groups: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            if row["contrast"] == contrast:
                groups[row["contrastGroup"]].append(row)
        group_items = sorted(groups.items(), key=lambda item: item[0])
        if len(group_items) != 2:
            raise ValueError(f"Expected 2 minimal-pair groups for {contrast}, got {len(group_items)}")
        for list_id in LIST_IDS:
            group_choice = HARD_GROUP_ASSIGNMENTS[list_id][contrast_index]
            _group, items = group_items[group_choice]
            if len(items) != 2:
                raise ValueError(f"Expected 2 items in {_group}, got {len(items)}")
            by_list[list_id].extend(sorted(items, key=lambda row: row["word"]))
    return by_list


def participant_rows(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    controls = split_controls(rows)
    hard = split_hard_groups(rows)
    output: list[dict[str, object]] = []
    for list_id in LIST_IDS:
        list_rows = controls[list_id] + hard[list_id]
        list_rows.sort(key=lambda row: (row["contrast"] != "control", row["contrast"], row["contrastGroup"], row["word"]))
        if len(list_rows) != 20:
            raise ValueError(f"List {list_id} has {len(list_rows)} items instead of 20")
        for index, row in enumerate(list_rows, 1):
            output.append({
                "listId": list_id,
                "listWordId": index,
                "objectId": index,
                "word": row["word"],
                "phonology": row["phonology"],
                "contrast": row["contrast"],
                "contrastGroup": row["contrastGroup"],
                "syllableCount": row["syllableCount"],
                "syllableTemplate": row["syllableTemplate"],
                "phones": row["phones"],
                "ipaTarget": row["ipaTarget"],
                "ttsText": row["ttsText"],
                "phonologicalNeighborhoodSize": row["phonologicalNeighborhoodSize"],
                "nearestRealWordDistance": row["nearestRealWordDistance"],
                "nearestRealWords": row["nearestRealWords"],
            })
    return output


def validate(rows: list[dict[str, object]]) -> None:
    for list_id in LIST_IDS:
        subset = [row for row in rows if row["listId"] == list_id]
        if len(subset) != 20:
            raise AssertionError(f"List {list_id} expected 20 rows, got {len(subset)}")
        counts: dict[str, int] = defaultdict(int)
        for row in subset:
            counts[str(row["contrast"])] += 1
        expected = {
            "control": 10,
            "r_l": 2,
            "v_b": 2,
            "theta_s": 2,
            "cluster_r_l": 2,
            "cluster_v_b": 2,
        }
        if dict(counts) != expected:
            raise AssertionError(f"List {list_id} count mismatch: {dict(counts)}")
        hard_groups = [
            row["contrastGroup"]
            for row in subset
            if row["contrast"] != "control"
        ]
        group_counts: dict[object, int] = defaultdict(int)
        for group in hard_groups:
            group_counts[group] += 1
        if sorted(group_counts.values()) != [2, 2, 2, 2, 2]:
            raise AssertionError(f"List {list_id} hard groups are not paired: {dict(group_counts)}")


def write_csv(rows: list[dict[str, object]]) -> None:
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(rows: list[dict[str, object]]) -> None:
    payload = {
        "schema": "cssl-validation-plan2-lists-v1",
        "source": str(SELECTED_CSV),
        "design": "four 20-word lists; 10 control + 10 hard; one minimal-pair group per hard contrast",
        "lists": {},
    }
    for list_id in LIST_IDS:
        payload["lists"][list_id] = [row for row in rows if row["listId"] == list_id]
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    rows = participant_rows(read_rows())
    validate(rows)
    write_csv(rows)
    write_json(rows)
    print(f"Wrote Plan 2 participant lists to {OUT_CSV} and {OUT_JSON}")


if __name__ == "__main__":
    main()
