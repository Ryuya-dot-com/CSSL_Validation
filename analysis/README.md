# Analysis Workspace

This directory is reserved for validation analyses. No scripts here should write
outside `CSSL_Validation` unless explicitly configured by a command-line argument.

Planned outputs:

- `qa_outputs/`
  - Optional audio/image QA tables produced by `prepare_audio_qa.py`,
    `qa_audio_asr.py`, `qa_image_similarity.py`, and
    `qa_image_recognition.py`, plus the consolidated readiness report produced
    by `prepilot_readiness.py`. This directory is ignored by git.
- `participant_summaries/`
  - Optional descriptive pilot summaries produced by `analyze_model_ready.py`.
    This directory is ignored by git.
- `simulation_outputs/`
  - Optional synthetic-data diagnostics produced by
    `simulate_switching_recovery.py`. This directory is ignored by git.
- `simulation_outputs/method_benchmark/`
  - Optional benchmark results comparing multiple onset estimators on the same
    synthetic trajectories.
- `contingent_response.csv`
  - Participant-level and block-level previous-correct versus previous-incorrect
    summaries.
- `windowed_model_fit.csv`
  - Associative/PbV likelihood comparison by time window.
- `mixture_model_fit.csv`
  - Trial-level continuous PbV mixture estimates.
- `switching_model_fit.csv`
  - Optional Markov-switching/HMM estimates after the simpler models are stable.

The adopted design is Plan 2:

- 20 words per participant.
- 5 learning blocks.
- 3 learning encounters per word per block.
- 15 learning encounters per word total.
- Click-based 5AFC test after each learning block.

Participant ID should be used as the deterministic seed for list assignment and
schedule generation. See `../docs/randomization_plan.md`.

Recommended order:

1. Validate audio, images, exports, and trial histories.
2. Run descriptive pilot summaries from `ModelReady`.
3. Fit contingent-response summaries.
4. Fit windowed associative/PbV comparisons.
5. Fit a continuous mixture model.
6. Fit a Markov-switching model only if the dataset has enough trials and
   participants.

## Pilot QA

Before pilot collection:

```bash
python3 CSSL_Validation/analysis/prepare_audio_qa.py
python3 CSSL_Validation/analysis/qa_audio_asr.py
python3 CSSL_Validation/analysis/qa_image_similarity.py --participants 80
python3 CSSL_Validation/analysis/qa_image_recognition.py --participants 80
python3 CSSL_Validation/analysis/prepilot_readiness.py --participants 80
```

`qa_audio_asr.py` is an ASR risk screen for pseudoword MP3s. It uses OpenAI
speech-to-text when `OPENAI_API_KEY` is present and writes
`skipped_no_api_key` rows otherwise, so the readiness report records that the
ASR layer still needs to be run.

`qa_image_recognition.py` runs without external dependencies by using the SVG
generation formula to infer each object's shape label and nameability risk. It
also checks whether any participant's 5AFC option set contains duplicate
shape-label families. Optional OpenAI recognizer modes are available for
additional SVG-text or rendered-image review.

To regenerate QA outputs, scenario simulations, method benchmarks, and the
readiness report in one command:

```bash
python3 CSSL_Validation/analysis/prepilot_readiness.py --participants 80 --refresh
```

After collecting a pilot workbook:

```bash
python3 CSSL_Validation/analysis/analyze_model_ready.py path/to/export.xlsx
python3 CSSL_Validation/analysis/prepilot_readiness.py --workbook path/to/export.xlsx
```

The workbook summary intentionally uses transparent descriptive quantities:
block-level accuracy, hard/easy splits, timeout/no-response rates,
word-trajectory sequences, and previous-correct contingency.

`prepilot_readiness.py` adds schema and task-integrity checks around those
summaries: required sheets, required `ModelReady` columns, row counts,
chronological ordering, timeout coding, and 5AFC target-position balance.

## Simulation Diagnostic

Before collecting the full sample, run a design-recovery simulation to check
whether Plan 2 has enough observations to recover plausible PbV-onset timing.

```bash
python3 CSSL_Validation/analysis/simulate_switching_recovery.py --participants 80
```

Useful variants:

```bash
python3 CSSL_Validation/analysis/simulate_switching_recovery.py \
  --participants 80 \
  --scenario weak_signal \
  --posterior-threshold 0.80
```

Run all predefined scenarios:

```bash
python3 CSSL_Validation/analysis/run_simulation_scenarios.py --participants 80
```

Benchmark multiple analysis families on the same synthetic data:

```bash
python3 CSSL_Validation/analysis/benchmark_analysis_methods.py --participants 80
```

Available scenarios are:

- `balanced`
  - Baseline simulation assumptions.
- `late_switch`
  - PbV transitions are delayed, especially for hard phonology items.
- `weak_signal`
  - State-specific accuracy differences are smaller, making state recovery more
    difficult.
- `strong_signal`
  - State-specific accuracy differences are larger, giving an optimistic upper
    bound.

The script writes:

- `synthetic_learning_events.csv`
  - Simulated learning responses with known latent states.
- `state_posterior_by_event.csv`
  - Fixed-parameter HMM posterior probabilities for `explore`,
    `associative`, and `pbv`.
- `switch_recovery_by_word.csv`
  - True versus estimated PbV onset encounter for each word trajectory.
- `switch_recovery_summary.csv`
  - Recovery rates and onset-error summaries overall and by easy/hard items.
- `threshold_sensitivity_summary.csv`
  - The same recovery summaries across a posterior-threshold grid.
- `method_benchmark/method_recovery_summary.csv`
  - Recovery metrics for HMM thresholds, rule-based estimators, mechanism
    likelihood ratios, change-point detection, and a survival-style hazard
    baseline.

Treat this as a design diagnostic, not as the final inferential model. If the
simulation shows poor recovery even under friendly assumptions, the behavioral
task should be adjusted before relying on HMM estimates from real data.
