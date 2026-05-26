#!/usr/bin/env python3
"""
Simulate whether the Plan 2 task can recover latent learning-mechanism switches.

The script uses the same deterministic schedules as the browser task, simulates
learning responses under explore/associative/PbV states, then runs a small
fixed-parameter HMM to estimate the posterior probability of each state. It is
intended as a design diagnostic before fitting real participant data.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "analysis" / "simulation_outputs"
STIMULUS_TOOLS = ROOT / "stimulus_tools"
sys.path.insert(0, str(STIMULUS_TOOLS))

from build_plan2_schedule import build_schedule  # noqa: E402


STATES = ("explore", "associative", "pbv")
STATE_INDEX = {state: index for index, state in enumerate(STATES)}
INITIAL_STATE_PRIOR = [0.76, 0.22, 0.02]


@dataclass(frozen=True)
class SimulationConfig:
    participants: int
    seed: int
    posterior_threshold: float
    out_dir: Path


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def bool_int(value: bool) -> int:
    return 1 if value else 0


def participant_ids(count: int) -> list[str]:
    return [f"SIM{index:04d}" for index in range(1, count + 1)]


def is_hard_item(row: dict[str, Any]) -> bool:
    return row.get("contrast") != "control"


def transition_distribution(
    current_state: str,
    encounter_index: int,
    previous_correct: bool | None,
    is_hard: bool,
    aptitude: float,
) -> dict[str, float]:
    hard = 1.0 if is_hard else 0.0
    previous_correct_bonus = 1.0 if previous_correct is True else 0.0
    previous_incorrect_penalty = 1.0 if previous_correct is False else 0.0

    if current_state == "explore":
        to_pbv = clamp(
            0.002
            + 0.010 * encounter_index
            + 0.075 * previous_correct_bonus
            + 0.030 * aptitude
            - 0.022 * hard
            - 0.006 * previous_incorrect_penalty,
            0.0,
            0.20,
        )
        to_associative = clamp(
            0.035
            + 0.017 * encounter_index
            + 0.035 * aptitude
            - 0.018 * hard,
            0.01,
            0.28,
        )
        stay_explore = clamp(1.0 - to_pbv - to_associative, 0.0, 1.0)
        return normalize_distribution({
            "explore": stay_explore,
            "associative": to_associative,
            "pbv": to_pbv,
        })

    if current_state == "associative":
        to_pbv = clamp(
            0.018
            + 0.018 * encounter_index
            + 0.115 * previous_correct_bonus
            + 0.040 * aptitude
            - 0.030 * hard
            - 0.010 * previous_incorrect_penalty,
            0.005,
            0.36,
        )
        to_explore = clamp(
            0.008 + 0.010 * hard + 0.020 * previous_incorrect_penalty - 0.010 * aptitude,
            0.0,
            0.10,
        )
        stay_associative = clamp(1.0 - to_pbv - to_explore, 0.0, 1.0)
        return normalize_distribution({
            "explore": to_explore,
            "associative": stay_associative,
            "pbv": to_pbv,
        })

    drop_to_associative = clamp(
        0.015
        + 0.050 * previous_incorrect_penalty
        + 0.015 * hard
        - 0.012 * aptitude,
        0.0,
        0.14,
    )
    drop_to_explore = clamp(0.003 + 0.006 * previous_incorrect_penalty, 0.0, 0.05)
    stay_pbv = clamp(1.0 - drop_to_associative - drop_to_explore, 0.0, 1.0)
    return normalize_distribution({
        "explore": drop_to_explore,
        "associative": drop_to_associative,
        "pbv": stay_pbv,
    })


def emission_correct_probability(
    state: str,
    encounter_index: int,
    previous_correct: bool | None,
    is_hard: bool,
    aptitude: float,
) -> float:
    hard = 1.0 if is_hard else 0.0
    previous_correct_bonus = 1.0 if previous_correct is True else 0.0
    previous_incorrect = 1.0 if previous_correct is False else 0.0

    if state == "explore":
        return clamp(1.0 / 3.0 + 0.010 * aptitude - 0.010 * hard, 0.27, 0.40)

    if state == "associative":
        return clamp(
            0.34
            + 0.032 * encounter_index
            + 0.035 * previous_correct_bonus
            + 0.020 * aptitude
            - 0.040 * hard,
            0.34,
            0.82,
        )

    if previous_correct is True:
        return clamp(0.91 + 0.015 * aptitude - 0.030 * hard, 0.76, 0.96)
    if previous_correct is False:
        return clamp(0.45 + 0.015 * aptitude - 0.050 * hard, 0.30, 0.62)
    return clamp(0.62 + 0.015 * aptitude - 0.030 * hard, 0.45, 0.75)


def normalize_distribution(distribution: dict[str, float]) -> dict[str, float]:
    total = sum(distribution.values())
    if total <= 0:
        return {state: 1.0 / len(distribution) for state in distribution}
    return {state: value / total for state, value in distribution.items()}


def draw_from_distribution(distribution: dict[str, float], rng: random.Random) -> str:
    threshold = rng.random()
    cumulative = 0.0
    last_state = next(reversed(distribution))
    for state, probability in distribution.items():
        cumulative += probability
        if threshold <= cumulative:
            return state
    return last_state


def choose_response_object(
    target_object_id: int,
    context_object_ids: list[int],
    correct: bool,
    previous_response_object_id: int | None,
    state: str,
    rng: random.Random,
) -> int:
    if correct:
        return target_object_id

    foils = [object_id for object_id in context_object_ids if object_id != target_object_id]
    if (
        state == "pbv"
        and previous_response_object_id in foils
        and rng.random() < 0.68
    ):
        return int(previous_response_object_id)
    return int(rng.choice(foils))


def simulate_participant(participant_id: str, rng: random.Random) -> list[dict[str, Any]]:
    schedule = build_schedule(participant_id)
    words_by_pair_id = {int(row["listWordId"]): row for row in schedule["words"]}
    state_by_pair_id = {pair_id: "explore" for pair_id in words_by_pair_id}
    encounter_by_pair_id = {pair_id: 0 for pair_id in words_by_pair_id}
    previous_by_pair_id: dict[int, dict[str, Any]] = {}
    aptitude = rng.normalvariate(0.0, 0.75)
    rows: list[dict[str, Any]] = []
    event_seq = 0

    for block in schedule["learningBlocks"]:
        for trial in block["trials"]:
            for word_event_in_trial, pair_id in enumerate(trial["wordOrderPairIds"], start=1):
                pair_id = int(pair_id)
                word = words_by_pair_id[pair_id]
                target_object_id = int(word["objectId"])
                context_object_ids = [int(object_id) for object_id in trial["objectIds"]]
                previous = previous_by_pair_id.get(pair_id)
                previous_correct = previous["correct"] if previous else None
                previous_response_object_id = previous["responseObjectId"] if previous else None
                encounter_by_pair_id[pair_id] += 1
                encounter_index = encounter_by_pair_id[pair_id]
                current_state = state_by_pair_id[pair_id]
                transition = transition_distribution(
                    current_state=current_state,
                    encounter_index=encounter_index,
                    previous_correct=previous_correct,
                    is_hard=is_hard_item(word),
                    aptitude=aptitude,
                )
                true_state = draw_from_distribution(transition, rng)
                state_by_pair_id[pair_id] = true_state

                p_correct = emission_correct_probability(
                    state=true_state,
                    encounter_index=encounter_index,
                    previous_correct=previous_correct,
                    is_hard=is_hard_item(word),
                    aptitude=aptitude,
                )
                correct = rng.random() < p_correct
                response_object_id = choose_response_object(
                    target_object_id=target_object_id,
                    context_object_ids=context_object_ids,
                    correct=correct,
                    previous_response_object_id=previous_response_object_id,
                    state=true_state,
                    rng=rng,
                )
                event_seq += 1
                row = {
                    "participantId": participant_id,
                    "listId": schedule["listId"],
                    "participantAptitude": round(aptitude, 6),
                    "eventSeq": event_seq,
                    "block": int(trial["block"]),
                    "blockTrial": int(trial["blockTrial"]),
                    "wordEventInTrial": word_event_in_trial,
                    "pairId": pair_id,
                    "word": word["word"],
                    "targetObjectId": target_object_id,
                    "contrast": word["contrast"],
                    "contrastGroup": word.get("contrastGroup", ""),
                    "phonology": word["phonology"],
                    "isHard": bool_int(is_hard_item(word)),
                    "encounterIndex": encounter_index,
                    "contextObjectIds": json.dumps(context_object_ids),
                    "targetPosition": context_object_ids.index(target_object_id) + 1,
                    "previousResponseObjectId": previous_response_object_id or "",
                    "previousCorrect": "" if previous_correct is None else bool_int(previous_correct),
                    "trueState": true_state,
                    "truePCorrect": round(p_correct, 6),
                    "responseObjectId": response_object_id,
                    "responsePosition": context_object_ids.index(response_object_id) + 1,
                    "correct": bool_int(correct),
                }
                rows.append(row)
                previous_by_pair_id[pair_id] = {
                    "correct": correct,
                    "responseObjectId": response_object_id,
                }

    return rows


def infer_posteriors(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    grouped = group_events_by_word(events)

    for (_participant_id, _pair_id), sequence in grouped.items():
        sequence.sort(key=lambda row: int(row["encounterIndex"]))
        posterior_sequence = forward_backward(sequence)
        for event, posterior in zip(sequence, posterior_sequence):
            inferred_state = STATES[max(range(len(STATES)), key=lambda index: posterior[index])]
            rows.append({
                "participantId": event["participantId"],
                "listId": event["listId"],
                "eventSeq": event["eventSeq"],
                "block": event["block"],
                "pairId": event["pairId"],
                "word": event["word"],
                "contrast": event["contrast"],
                "phonology": event["phonology"],
                "isHard": event["isHard"],
                "encounterIndex": event["encounterIndex"],
                "correct": event["correct"],
                "previousCorrect": event["previousCorrect"],
                "trueState": event["trueState"],
                "inferredState": inferred_state,
                "posteriorExplore": round(posterior[STATE_INDEX["explore"]], 6),
                "posteriorAssociative": round(posterior[STATE_INDEX["associative"]], 6),
                "posteriorPbv": round(posterior[STATE_INDEX["pbv"]], 6),
                "stateRecovered": bool_int(inferred_state == event["trueState"]),
            })

    rows.sort(key=lambda row: (row["participantId"], int(row["eventSeq"])))
    return rows


def group_events_by_word(events: list[dict[str, Any]]) -> dict[tuple[str, int], list[dict[str, Any]]]:
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for event in events:
        key = (str(event["participantId"]), int(event["pairId"]))
        grouped.setdefault(key, []).append(event)
    return grouped


def forward_backward(sequence: list[dict[str, Any]]) -> list[list[float]]:
    alpha: list[list[float]] = []
    for time_index, event in enumerate(sequence):
        emission = [emission_likelihood(state, event) for state in STATES]
        if time_index == 0:
            values = [INITIAL_STATE_PRIOR[index] * emission[index] for index in range(len(STATES))]
        else:
            previous_event = sequence[time_index - 1]
            transition_matrix = inference_transition_matrix(event, previous_event)
            values = []
            for to_index in range(len(STATES)):
                total = sum(
                    alpha[time_index - 1][from_index] * transition_matrix[from_index][to_index]
                    for from_index in range(len(STATES))
                )
                values.append(total * emission[to_index])
        alpha.append(normalize_vector(values))

    beta: list[list[float]] = [[1.0 for _state in STATES] for _event in sequence]
    for time_index in range(len(sequence) - 2, -1, -1):
        next_event = sequence[time_index + 1]
        current_event = sequence[time_index]
        transition_matrix = inference_transition_matrix(next_event, current_event)
        next_emission = [emission_likelihood(state, next_event) for state in STATES]
        values = []
        for from_index in range(len(STATES)):
            total = sum(
                transition_matrix[from_index][to_index]
                * next_emission[to_index]
                * beta[time_index + 1][to_index]
                for to_index in range(len(STATES))
            )
            values.append(total)
        beta[time_index] = normalize_vector(values)

    posteriors = []
    for alpha_row, beta_row in zip(alpha, beta):
        posteriors.append(normalize_vector([
            alpha_row[index] * beta_row[index] for index in range(len(STATES))
        ]))
    return posteriors


def inference_transition_matrix(
    current_event: dict[str, Any],
    previous_event: dict[str, Any],
) -> list[list[float]]:
    del previous_event
    encounter_index = int(current_event["encounterIndex"])
    previous_correct = parse_previous_correct(current_event["previousCorrect"])
    is_hard = bool(int(current_event["isHard"]))
    matrix = []
    for state in STATES:
        distribution = transition_distribution(
            current_state=state,
            encounter_index=encounter_index,
            previous_correct=previous_correct,
            is_hard=is_hard,
            aptitude=0.0,
        )
        matrix.append([distribution[to_state] for to_state in STATES])
    return matrix


def emission_likelihood(state: str, event: dict[str, Any]) -> float:
    p_correct = emission_correct_probability(
        state=state,
        encounter_index=int(event["encounterIndex"]),
        previous_correct=parse_previous_correct(event["previousCorrect"]),
        is_hard=bool(int(event["isHard"])),
        aptitude=0.0,
    )
    return p_correct if int(event["correct"]) == 1 else (1.0 - p_correct)


def parse_previous_correct(value: Any) -> bool | None:
    if value == "" or value is None:
        return None
    return bool(int(value))


def normalize_vector(values: list[float]) -> list[float]:
    total = sum(values)
    if total <= 0 or not math.isfinite(total):
        return [1.0 / len(values) for _value in values]
    return [value / total for value in values]


def summarize_recovery(
    events: list[dict[str, Any]],
    posteriors: list[dict[str, Any]],
    posterior_threshold: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events_by_word = group_events_by_word(events)
    posteriors_by_word = group_events_by_word(posteriors)
    by_word_rows: list[dict[str, Any]] = []

    for key, event_sequence in events_by_word.items():
        posterior_sequence = posteriors_by_word[key]
        event_sequence.sort(key=lambda row: int(row["encounterIndex"]))
        posterior_sequence.sort(key=lambda row: int(row["encounterIndex"]))
        true_onset = first_encounter(event_sequence, lambda row: row["trueState"] == "pbv")
        estimated_onset = first_encounter(
            posterior_sequence,
            lambda row: float(row["posteriorPbv"]) >= posterior_threshold,
        )
        onset_error = ""
        recovered_exact = ""
        recovered_within_one = ""
        recovered_within_two = ""
        if true_onset and estimated_onset:
            onset_error = estimated_onset - true_onset
            recovered_exact = bool_int(onset_error == 0)
            recovered_within_one = bool_int(abs(onset_error) <= 1)
            recovered_within_two = bool_int(abs(onset_error) <= 2)
        participant_id, pair_id = key
        first_event = event_sequence[0]
        last_posterior = posterior_sequence[-1]
        by_word_rows.append({
            "participantId": participant_id,
            "listId": first_event["listId"],
            "pairId": pair_id,
            "word": first_event["word"],
            "contrast": first_event["contrast"],
            "phonology": first_event["phonology"],
            "isHard": first_event["isHard"],
            "truePbvOnsetEncounter": true_onset or "",
            "estimatedPbvOnsetEncounter": estimated_onset or "",
            "onsetError": onset_error,
            "recoveredExact": recovered_exact,
            "recoveredWithinOne": recovered_within_one,
            "recoveredWithinTwo": recovered_within_two,
            "missedTrueOnset": bool_int(bool(true_onset) and not bool(estimated_onset)),
            "falseEstimatedOnset": bool_int(not bool(true_onset) and bool(estimated_onset)),
            "finalPosteriorPbv": last_posterior["posteriorPbv"],
            "finalTrueState": event_sequence[-1]["trueState"],
        })

    summary_rows = build_summary_rows(by_word_rows, posteriors, posterior_threshold)
    return by_word_rows, summary_rows


def first_encounter(sequence: list[dict[str, Any]], predicate: Any) -> int | None:
    for row in sequence:
        if predicate(row):
            return int(row["encounterIndex"])
    return None


def build_summary_rows(
    by_word_rows: list[dict[str, Any]],
    posteriors: list[dict[str, Any]],
    posterior_threshold: float,
) -> list[dict[str, Any]]:
    scopes = [("all", by_word_rows)]
    scopes.append(("control", [row for row in by_word_rows if int(row["isHard"]) == 0]))
    scopes.append(("hard", [row for row in by_word_rows if int(row["isHard"]) == 1]))
    summary_rows = []
    state_accuracy = mean_or_blank([int(row["stateRecovered"]) for row in posteriors])

    for scope, rows in scopes:
        onset_rows = [
            row for row in rows
            if row["truePbvOnsetEncounter"] != "" and row["estimatedPbvOnsetEncounter"] != ""
        ]
        onset_errors = [abs(int(row["onsetError"])) for row in onset_rows]
        true_onset_count = sum(1 for row in rows if row["truePbvOnsetEncounter"] != "")
        estimated_onset_count = sum(1 for row in rows if row["estimatedPbvOnsetEncounter"] != "")
        summary_rows.append({
            "scope": scope,
            "posteriorThreshold": posterior_threshold,
            "wordTrajectories": len(rows),
            "stateAccuracyEventLevel": state_accuracy if scope == "all" else "",
            "trueOnsetCount": true_onset_count,
            "estimatedOnsetCount": estimated_onset_count,
            "meanAbsoluteOnsetError": mean_or_blank(onset_errors),
            "medianAbsoluteOnsetError": median_or_blank(onset_errors),
            "exactOnsetRecoveryRate": rate_or_blank(rows, "recoveredExact"),
            "withinOneEncounterRecoveryRate": rate_or_blank(rows, "recoveredWithinOne"),
            "withinTwoEncounterRecoveryRate": rate_or_blank(rows, "recoveredWithinTwo"),
            "missedTrueOnsetRate": (
                sum(int(row["missedTrueOnset"]) for row in rows) / true_onset_count
                if true_onset_count else ""
            ),
            "falseEstimatedOnsetRate": (
                sum(int(row["falseEstimatedOnset"]) for row in rows)
                / max(1, len(rows) - true_onset_count)
                if len(rows) - true_onset_count > 0 else ""
            ),
        })
    return summary_rows


def rate_or_blank(rows: list[dict[str, Any]], key: str) -> float | str:
    values = [int(row[key]) for row in rows if row[key] != ""]
    return mean_or_blank(values)


def mean_or_blank(values: list[int | float]) -> float | str:
    return round(statistics.fmean(values), 6) if values else ""


def median_or_blank(values: list[int | float]) -> float | str:
    return round(statistics.median(values), 6) if values else ""


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_simulation(config: SimulationConfig) -> dict[str, Path]:
    rng = random.Random(config.seed)
    events: list[dict[str, Any]] = []
    for participant_id in participant_ids(config.participants):
        events.extend(simulate_participant(participant_id, rng))

    posteriors = infer_posteriors(events)
    recovery_rows, summary_rows = summarize_recovery(
        events=events,
        posteriors=posteriors,
        posterior_threshold=config.posterior_threshold,
    )

    config.out_dir.mkdir(parents=True, exist_ok=True)
    output_paths = {
        "synthetic_learning_events": config.out_dir / "synthetic_learning_events.csv",
        "state_posterior_by_event": config.out_dir / "state_posterior_by_event.csv",
        "switch_recovery_by_word": config.out_dir / "switch_recovery_by_word.csv",
        "switch_recovery_summary": config.out_dir / "switch_recovery_summary.csv",
        "simulation_parameters": config.out_dir / "simulation_parameters.json",
    }
    write_csv(output_paths["synthetic_learning_events"], events)
    write_csv(output_paths["state_posterior_by_event"], posteriors)
    write_csv(output_paths["switch_recovery_by_word"], recovery_rows)
    write_csv(output_paths["switch_recovery_summary"], summary_rows)
    output_paths["simulation_parameters"].write_text(
        json.dumps({
            "participants": config.participants,
            "seed": config.seed,
            "posteriorThreshold": config.posterior_threshold,
            "states": list(STATES),
            "note": "Fixed-parameter design diagnostic, not a final inferential model.",
        }, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_paths


def parse_args() -> SimulationConfig:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--participants", type=int, default=80)
    parser.add_argument("--seed", type=int, default=20260526)
    parser.add_argument("--posterior-threshold", type=float, default=0.70)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    if args.participants <= 0:
        raise SystemExit("--participants must be positive")
    if not 0 < args.posterior_threshold < 1:
        raise SystemExit("--posterior-threshold must be between 0 and 1")
    return SimulationConfig(
        participants=args.participants,
        seed=args.seed,
        posterior_threshold=args.posterior_threshold,
        out_dir=args.out_dir,
    )


def main() -> None:
    config = parse_args()
    output_paths = run_simulation(config)
    summary_path = output_paths["switch_recovery_summary"]
    print(f"Wrote simulation outputs to {config.out_dir}")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
