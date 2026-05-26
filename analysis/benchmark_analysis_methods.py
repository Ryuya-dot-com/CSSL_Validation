#!/usr/bin/env python3
"""
Benchmark multiple analysis strategies on synthetic CSSL validation data.

The goal is not to declare a winner from simulation alone. It is to make clear
which classes of analysis can recover a known PbV onset under the Plan 2 design,
and which methods are too threshold-sensitive or too optimistic.
"""

from __future__ import annotations

import argparse
import csv
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from simulate_switching_recovery import (
    BASE_PROFILE,
    DEFAULT_OUT_DIR,
    SCENARIOS,
    STATES,
    emission_correct_probability,
    first_encounter,
    group_events_by_word,
    infer_posteriors,
    participant_ids,
    parse_previous_correct,
    simulate_participant,
)


DEFAULT_METHOD_OUT_DIR = DEFAULT_OUT_DIR / "method_benchmark"
EPSILON = 1e-9


@dataclass(frozen=True)
class MethodSpec:
    name: str
    family: str
    uses_future_data: bool
    description: str
    estimator: Callable[[list[dict[str, Any]], list[dict[str, Any]]], int | None]


def clamp_probability(value: float) -> float:
    return min(1.0 - EPSILON, max(EPSILON, value))


def correct_values(events: list[dict[str, Any]]) -> list[int]:
    return [int(row["correct"]) for row in events]


def true_onset(events: list[dict[str, Any]]) -> int | None:
    return first_encounter(events, lambda row: row["trueState"] == "pbv")


def onset_from_hmm(threshold: float) -> Callable[[list[dict[str, Any]], list[dict[str, Any]]], int | None]:
    def estimator(_events: list[dict[str, Any]], posteriors: list[dict[str, Any]]) -> int | None:
        return first_encounter(
            posteriors,
            lambda row: float(row["posteriorPbv"]) >= threshold,
        )
    return estimator


def onset_from_rolling_accuracy(
    window: int,
    hits_required: int,
) -> Callable[[list[dict[str, Any]], list[dict[str, Any]]], int | None]:
    def estimator(events: list[dict[str, Any]], _posteriors: list[dict[str, Any]]) -> int | None:
        values = correct_values(events)
        for index in range(window - 1, len(values)):
            if sum(values[index - window + 1:index + 1]) >= hits_required:
                return int(events[index]["encounterIndex"])
        return None
    return estimator


def onset_from_consecutive_correct(
    run_length: int,
) -> Callable[[list[dict[str, Any]], list[dict[str, Any]]], int | None]:
    def estimator(events: list[dict[str, Any]], _posteriors: list[dict[str, Any]]) -> int | None:
        streak = 0
        for event in events:
            streak = streak + 1 if int(event["correct"]) == 1 else 0
            if streak >= run_length:
                return int(event["encounterIndex"])
        return None
    return estimator


def onset_from_cumulative_accuracy(
    minimum_encounter: int,
    threshold: float,
) -> Callable[[list[dict[str, Any]], list[dict[str, Any]]], int | None]:
    def estimator(events: list[dict[str, Any]], _posteriors: list[dict[str, Any]]) -> int | None:
        correct_count = 0
        for index, event in enumerate(events, start=1):
            correct_count += int(event["correct"])
            if index >= minimum_encounter and correct_count / index >= threshold:
                return int(event["encounterIndex"])
        return None
    return estimator


def onset_from_posterior_free_loglikelihood(
    threshold: float,
) -> Callable[[list[dict[str, Any]], list[dict[str, Any]]], int | None]:
    def estimator(events: list[dict[str, Any]], _posteriors: list[dict[str, Any]]) -> int | None:
        cumulative_loglr = 0.0
        for event in events:
            previous_correct = parse_previous_correct(event["previousCorrect"])
            associative = emission_correct_probability(
                state="associative",
                encounter_index=int(event["encounterIndex"]),
                previous_correct=previous_correct,
                is_hard=bool(int(event["isHard"])),
                aptitude=0.0,
                profile=BASE_PROFILE,
            )
            pbv = emission_correct_probability(
                state="pbv",
                encounter_index=int(event["encounterIndex"]),
                previous_correct=previous_correct,
                is_hard=bool(int(event["isHard"])),
                aptitude=0.0,
                profile=BASE_PROFILE,
            )
            observed_correct = int(event["correct"]) == 1
            p_assoc = associative if observed_correct else 1.0 - associative
            p_pbv = pbv if observed_correct else 1.0 - pbv
            cumulative_loglr += math.log(clamp_probability(p_pbv)) - math.log(clamp_probability(p_assoc))
            if cumulative_loglr >= threshold:
                return int(event["encounterIndex"])
        return None
    return estimator


def onset_from_beta_binomial_changepoint(
    log_bayes_factor_threshold: float,
) -> Callable[[list[dict[str, Any]], list[dict[str, Any]]], int | None]:
    def estimator(events: list[dict[str, Any]], _posteriors: list[dict[str, Any]]) -> int | None:
        values = correct_values(events)
        if len(values) < 5:
            return None
        no_change = beta_binomial_log_marginal(sum(values), len(values), alpha=2.0, beta=2.0)
        best_log_marginal = -math.inf
        best_onset = None
        for split_index in range(2, len(values) - 2):
            pre = values[:split_index]
            post = values[split_index:]
            log_marginal = (
                beta_binomial_log_marginal(sum(pre), len(pre), alpha=2.0, beta=4.0)
                + beta_binomial_log_marginal(sum(post), len(post), alpha=5.0, beta=2.0)
            )
            if log_marginal > best_log_marginal:
                best_log_marginal = log_marginal
                best_onset = int(events[split_index]["encounterIndex"])
        if best_onset is None:
            return None
        return best_onset if best_log_marginal - no_change >= log_bayes_factor_threshold else None
    return estimator


def beta_binomial_log_marginal(successes: int, trials: int, alpha: float, beta: float) -> float:
    failures = trials - successes
    return (
        math.lgamma(alpha + beta)
        - math.lgamma(alpha)
        - math.lgamma(beta)
        + math.lgamma(successes + alpha)
        + math.lgamma(failures + beta)
        - math.lgamma(trials + alpha + beta)
    )


def onset_from_hazard_prior(
    threshold: float,
) -> Callable[[list[dict[str, Any]], list[dict[str, Any]]], int | None]:
    def estimator(events: list[dict[str, Any]], _posteriors: list[dict[str, Any]]) -> int | None:
        cumulative_survival = 1.0
        for event in events:
            encounter = int(event["encounterIndex"])
            hard = int(event["isHard"])
            previous_correct = parse_previous_correct(event["previousCorrect"])
            previous_correct_bonus = 1.0 if previous_correct is True else 0.0
            logit_hazard = -3.40 + 0.22 * encounter + 0.95 * previous_correct_bonus - 0.42 * hard
            hazard = 1.0 / (1.0 + math.exp(-logit_hazard))
            onset_probability_by_now = 1.0 - cumulative_survival * (1.0 - hazard)
            cumulative_survival *= 1.0 - hazard
            if onset_probability_by_now >= threshold:
                return encounter
        return None
    return estimator


def method_specs() -> list[MethodSpec]:
    return [
        MethodSpec(
            name="hmm_posterior_0.70",
            family="state_space_hmm",
            uses_future_data=True,
            description="Smoothed HMM posterior PbV probability crosses 0.70.",
            estimator=onset_from_hmm(0.70),
        ),
        MethodSpec(
            name="hmm_posterior_0.80",
            family="state_space_hmm",
            uses_future_data=True,
            description="Smoothed HMM posterior PbV probability crosses 0.80.",
            estimator=onset_from_hmm(0.80),
        ),
        MethodSpec(
            name="rolling_2_of_3_correct",
            family="nonparametric_rule",
            uses_future_data=False,
            description="First 3-encounter rolling window with at least 2 correct responses.",
            estimator=onset_from_rolling_accuracy(window=3, hits_required=2),
        ),
        MethodSpec(
            name="rolling_3_of_4_correct",
            family="nonparametric_rule",
            uses_future_data=False,
            description="First 4-encounter rolling window with at least 3 correct responses.",
            estimator=onset_from_rolling_accuracy(window=4, hits_required=3),
        ),
        MethodSpec(
            name="two_consecutive_correct",
            family="win_stay_rule",
            uses_future_data=False,
            description="First point with two consecutive correct responses for the word.",
            estimator=onset_from_consecutive_correct(run_length=2),
        ),
        MethodSpec(
            name="cumulative_accuracy_0.70_from_6",
            family="nonparametric_rule",
            uses_future_data=False,
            description="Cumulative learning accuracy reaches 0.70 after at least 6 encounters.",
            estimator=onset_from_cumulative_accuracy(minimum_encounter=6, threshold=0.70),
        ),
        MethodSpec(
            name="pbv_assoc_loglr_1.5",
            family="mechanism_likelihood_ratio",
            uses_future_data=False,
            description="Cumulative PbV-vs-associative emission log-likelihood ratio crosses 1.5.",
            estimator=onset_from_posterior_free_loglikelihood(threshold=1.5),
        ),
        MethodSpec(
            name="beta_binomial_changepoint_bf2",
            family="bayesian_changepoint",
            uses_future_data=True,
            description="Offline beta-binomial change-point with log Bayes factor >= 2.",
            estimator=onset_from_beta_binomial_changepoint(log_bayes_factor_threshold=2.0),
        ),
        MethodSpec(
            name="hazard_prior_0.70",
            family="survival_prior",
            uses_future_data=False,
            description="Covariate-only onset hazard reaches cumulative probability 0.70.",
            estimator=onset_from_hazard_prior(threshold=0.70),
        ),
    ]


def simulate_events(participants: int, seed: int, scenario: str) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    profile = SCENARIOS[scenario]
    events: list[dict[str, Any]] = []
    for participant_id in participant_ids(participants):
        events.extend(simulate_participant(participant_id, rng, profile))
    return events


def benchmark_scenario(
    participants: int,
    seed: int,
    scenario: str,
    specs: list[MethodSpec],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events = simulate_events(participants, seed, scenario)
    posteriors = infer_posteriors(events)
    events_by_word = group_events_by_word(events)
    posteriors_by_word = group_events_by_word(posteriors)
    rows: list[dict[str, Any]] = []

    for key, event_sequence in events_by_word.items():
        event_sequence.sort(key=lambda row: int(row["encounterIndex"]))
        posterior_sequence = posteriors_by_word[key]
        posterior_sequence.sort(key=lambda row: int(row["encounterIndex"]))
        true = true_onset(event_sequence)
        participant_id, pair_id = key
        first = event_sequence[0]
        for spec in specs:
            estimated = spec.estimator(event_sequence, posterior_sequence)
            rows.append(onset_result_row(
                spec=spec,
                scenario=scenario,
                participant_id=participant_id,
                pair_id=pair_id,
                first_event=first,
                true_onset_value=true,
                estimated_onset_value=estimated,
            ))

    return rows, summarize_method_results(rows)


def onset_result_row(
    spec: MethodSpec,
    scenario: str,
    participant_id: str,
    pair_id: int,
    first_event: dict[str, Any],
    true_onset_value: int | None,
    estimated_onset_value: int | None,
) -> dict[str, Any]:
    onset_error = ""
    exact = ""
    within_one = ""
    within_two = ""
    if true_onset_value is not None and estimated_onset_value is not None:
        onset_error = estimated_onset_value - true_onset_value
        exact = int(onset_error == 0)
        within_one = int(abs(onset_error) <= 1)
        within_two = int(abs(onset_error) <= 2)
    return {
        "simulationScenario": scenario,
        "method": spec.name,
        "methodFamily": spec.family,
        "usesFutureData": int(spec.uses_future_data),
        "participantId": participant_id,
        "listId": first_event["listId"],
        "pairId": pair_id,
        "word": first_event["word"],
        "contrast": first_event["contrast"],
        "phonology": first_event["phonology"],
        "isHard": first_event["isHard"],
        "truePbvOnsetEncounter": true_onset_value or "",
        "estimatedPbvOnsetEncounter": estimated_onset_value or "",
        "onsetError": onset_error,
        "recoveredExact": exact,
        "recoveredWithinOne": within_one,
        "recoveredWithinTwo": within_two,
        "missedTrueOnset": int(true_onset_value is not None and estimated_onset_value is None),
        "falseEstimatedOnset": int(true_onset_value is None and estimated_onset_value is not None),
    }


def summarize_method_results(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        for scope in ("all", "control" if int(row["isHard"]) == 0 else "hard"):
            key = (row["simulationScenario"], row["method"], scope)
            groups.setdefault(key, []).append(row)

    summaries = []
    for (scenario, method, scope), group_rows in sorted(groups.items()):
        method_family = str(group_rows[0]["methodFamily"])
        uses_future_data = int(group_rows[0]["usesFutureData"])
        true_onset_rows = [row for row in group_rows if row["truePbvOnsetEncounter"] != ""]
        no_true_onset_rows = [row for row in group_rows if row["truePbvOnsetEncounter"] == ""]
        paired_rows = [
            row for row in group_rows
            if row["truePbvOnsetEncounter"] != "" and row["estimatedPbvOnsetEncounter"] != ""
        ]
        onset_errors = [int(row["onsetError"]) for row in paired_rows]
        summaries.append({
            "simulationScenario": scenario,
            "method": method,
            "methodFamily": method_family,
            "usesFutureData": uses_future_data,
            "scope": scope,
            "wordTrajectories": len(group_rows),
            "trueOnsetCount": len(true_onset_rows),
            "estimatedOnsetCount": sum(1 for row in group_rows if row["estimatedPbvOnsetEncounter"] != ""),
            "meanSignedOnsetError": mean_or_blank(onset_errors),
            "meanAbsoluteOnsetError": mean_or_blank([abs(value) for value in onset_errors]),
            "exactOnsetRecoveryRate": rate_or_blank(group_rows, "recoveredExact"),
            "withinOneEncounterRecoveryRate": rate_or_blank(group_rows, "recoveredWithinOne"),
            "withinTwoEncounterRecoveryRate": rate_or_blank(group_rows, "recoveredWithinTwo"),
            "missedTrueOnsetRate": (
                sum(int(row["missedTrueOnset"]) for row in true_onset_rows) / len(true_onset_rows)
                if true_onset_rows else ""
            ),
            "falseEstimatedOnsetRate": (
                sum(int(row["falseEstimatedOnset"]) for row in no_true_onset_rows) / len(no_true_onset_rows)
                if no_true_onset_rows else ""
            ),
        })
    return summaries


def mean_or_blank(values: list[int | float]) -> float | str:
    return round(sum(values) / len(values), 6) if values else ""


def rate_or_blank(rows: list[dict[str, Any]], key: str) -> float | str:
    values = [int(row[key]) for row in rows if row[key] != ""]
    return mean_or_blank(values)


def method_catalog_rows(specs: list[MethodSpec]) -> list[dict[str, Any]]:
    return [{
        "method": spec.name,
        "methodFamily": spec.family,
        "usesFutureData": int(spec.uses_future_data),
        "description": spec.description,
    } for spec in specs]


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
    parser.add_argument("--seed", type=int, default=20260526)
    parser.add_argument(
        "--scenario",
        choices=["all", *sorted(SCENARIOS)],
        default="all",
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_METHOD_OUT_DIR)
    args = parser.parse_args()
    if args.participants <= 0:
        raise SystemExit("--participants must be positive")
    return args


def main() -> None:
    args = parse_args()
    specs = method_specs()
    scenarios = sorted(SCENARIOS) if args.scenario == "all" else [args.scenario]
    detail_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        scenario_detail_rows, scenario_summary_rows = benchmark_scenario(
            participants=args.participants,
            seed=args.seed,
            scenario=scenario,
            specs=specs,
        )
        detail_rows.extend(scenario_detail_rows)
        summary_rows.extend(scenario_summary_rows)
        print(f"{scenario}: {len(scenario_detail_rows)} method-word rows")

    write_csv(args.out_dir / "method_catalog.csv", method_catalog_rows(specs))
    write_csv(args.out_dir / "method_onset_by_word.csv", detail_rows)
    write_csv(args.out_dir / "method_recovery_summary.csv", summary_rows)
    print(f"Wrote benchmark outputs to {args.out_dir}")


if __name__ == "__main__":
    main()
