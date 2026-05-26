# Pilot Runbook

This runbook defines the minimum pilot procedure before collecting the full CSSL
validation sample.

## Pilot Size

Start with 5-10 participants. This is enough to catch task-flow failures,
audio/image problems, export problems, and obvious floor/ceiling effects. It is
not enough for final HMM claims.

## Before The First Pilot Participant

Run the static QA scripts:

```bash
python3 CSSL_Validation/analysis/prepilot_readiness.py --participants 80 --refresh
```

Review:

- `CSSL_Validation/analysis/qa_outputs/prepilot_readiness_report.md`
- `CSSL_Validation/analysis/qa_outputs/prepilot_readiness_checks.csv`
- `CSSL_Validation/analysis/qa_outputs/stimulus_review_dashboard.html`

The readiness report intentionally treats incomplete manual audio review and
weak-signal simulation recovery as warnings rather than automatic task failure.
Formal pilot collection should not start with any `FAIL` rows.

The refresh step also runs ASR and automatic image-recognition QA. In an
environment without `OPENAI_API_KEY`, the ASR table is still written but marked
as skipped; run `analysis/qa_audio_asr.py` once with API access before formal
collection. Image recognition has a deterministic SVG-based layer that runs
without external dependencies and checks for high-nameability objects and
same-shape-label collisions in 5AFC option sets.

Open the dashboard in Chrome for the final stimulus pass. It shows each MP3
with its paired object thumbnail, ASR status, and image-nameability flags on one
page, so the reviewer does not have to cross-reference CSV files by hand.

## During Pilot

Use Google Chrome only. Record:

- participant ID,
- device and display size,
- Chrome version if available,
- whether the volume check was clear,
- whether practice instructions were understood,
- whether any ASR-flagged item sounds ambiguous in the actual testing setup,
- any item that sounded wrong or looked confusable,
- whether the final `.xlsx` file downloaded without help.

Do not give correctness feedback during the main task.

## After Each Pilot Workbook

Run:

```bash
python3 CSSL_Validation/analysis/analyze_model_ready.py path/to/export.xlsx
python3 CSSL_Validation/analysis/prepilot_readiness.py --workbook path/to/export.xlsx
```

Inspect:

- `overall_summary.csv`
  - block-independent learning/test accuracy, hard/easy split, timeout rate,
    and previous-correct contingency.
- `block_summary.csv`
  - block-level improvement and floor/ceiling checks.
- `word_trajectory.csv`
  - item-level sequences; use this to find broken audio or images.
- `timeout_rows.csv`
  - no-response/timeouts that may indicate unclear instructions or fatigue.
- `prepilot_readiness_checks.csv`
  - workbook schema, row counts, chronological ordering, timeout coding, and
    target-position balance.

## Go / Revise Criteria

Proceed to a larger sample only if:

- Chrome gate, volume check, practice, and export work without intervention,
- 5AFC timeout rate is low enough that timeout handling will not dominate the
  analysis,
- block-5 accuracy is clearly above chance but not near ceiling for most items,
- hard items are harder than controls but not uniformly at floor,
- no single image pair or audio contrast is repeatedly blamed by participants,
- simulation recovery is not acceptable only under the `strong_signal` scenario.

If the pilot fails any criterion, revise the stimulus set or task instructions
before collecting the full sample.
