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
python3 CSSL_Validation/analysis/prepare_audio_qa.py
python3 CSSL_Validation/analysis/qa_image_similarity.py --participants 80
python3 CSSL_Validation/analysis/run_simulation_scenarios.py --participants 80
```

Review the generated files under `CSSL_Validation/analysis/qa_outputs/` and
`CSSL_Validation/analysis/simulation_outputs/`.

## During Pilot

Use Google Chrome only. Record:

- participant ID,
- device and display size,
- Chrome version if available,
- whether the volume check was clear,
- whether practice instructions were understood,
- any item that sounded wrong or looked confusable,
- whether the final `.xlsx` file downloaded without help.

Do not give correctness feedback during the main task.

## After Each Pilot Workbook

Run:

```bash
python3 CSSL_Validation/analysis/analyze_model_ready.py path/to/export.xlsx
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
