# CSSL Validation

This directory contains a new, non-destructive validation workspace for testing
when learners shift from broad cross-situational tracking to a more
Propose-but-Verify-like learning state.

## Goal

The central question is not only whether participants learn word-object mappings,
but when their trial-by-trial behavior becomes better described by:

- an exploratory or guessing state,
- an associative state that uses graded co-occurrence evidence, or
- a PbV state that maintains and verifies a single word-object hypothesis.

The validation task should therefore preserve learning-trial responses, not only
final test accuracy.

## Current Files

- `stimulus_tools/build_validation_stimuli.py`
  - Generates a controlled pseudoword master set.
  - Scores candidates against CMUdict to avoid accidental real-word-like items.
  - Balances easy controls and difficult non-native contrasts.
- `stimulus_tools/build_plan2_lists.py`
  - Splits the 40-word bank into four 20-word participant lists for Plan 2.
- `stimulus_tools/build_plan2_schedule.py`
  - Builds deterministic participant schedules from participant IDs.
- `stimulus_tools/generate_gtts_audio.py`
  - Generates static MP3 files with gTTS.
- `stimulus_tools/generate_object_svgs.py`
  - Generates abstract SVG object stimuli.
- `analysis/simulate_switching_recovery.py`
  - Simulates latent explore/associative/PbV trajectories and checks whether
    onset timing can be recovered under the Plan 2 schedule.
- `analysis/run_simulation_scenarios.py`
  - Runs the switching-recovery simulation across all predefined generative
    scenarios.
- `analysis/prepare_audio_qa.py`
  - Creates audio-review CSV tables for manual gTTS/stimulus checking.
- `analysis/qa_image_similarity.py`
  - Screens generated SVG objects and 5AFC option sets for obvious visual
    similarity collisions.
- `analysis/analyze_model_ready.py`
  - Summarizes exported `.xlsx` workbooks from the `ModelReady` sheet for pilot
    checks.
- `analysis/benchmark_analysis_methods.py`
  - Benchmarks HMM, rule-based, likelihood-ratio, change-point, and
    survival-style onset estimators on synthetic data.
- `config/task_design_plan2.json`
  - Machine-readable adopted task design: 20 words, 5 blocks, 5AFC.
- `index.html` / `styles.css` / `task.js`
  - Browser task scaffold for Plan 2 with participant-ID seeding and click-based 5AFC.
- `audio/README.md`
  - Naming convention for recorded pseudoword audio files.
- `images/objects/`
  - Generated abstract object images used by the task.
- `stimuli/stimulus_candidates.csv`
  - Full generated candidate pool with phonological diagnostics.
- `stimuli/stimulus_set_selected.csv`
  - Selected master set for validation.
- `stimuli/pronunciation_ipa.json`
  - Target IPA and practical TTS respellings for review/audio generation.
- `stimuli/stimulus_manifest.json`
  - Machine-readable manifest for downstream task code.
- `stimuli/stimulus_report.md`
  - Human-readable review of selected words.
- `stimuli/participant_lists_plan2.csv` / `stimuli/participant_lists_plan2.json`
  - Counterbalanced 20-word lists for participant assignment.
- `docs/stimulus_design.md`
  - Stimulus design rationale and constraints.
- `docs/task_design_plan2.md`
  - Adopted task design and trial-count rationale.
- `docs/randomization_plan.md`
  - Participant-ID seed, list assignment, and schedule generation plan.
- `docs/task_refinement_logic.md`
  - Prior-study logic, practice design, audio, image, and export rationale.
- `docs/mechanism_switching_plan.md`
  - Analysis plan for estimating learning-mechanism switching.
- `docs/analysis_method_catalog.md`
  - Broader analysis-method catalog spanning CSSL-inspired models, state-space
    models, change-point/survival analysis, RL, GLMM, IRT, and RT-aware methods.
- `docs/pilot_checklist.md`
  - Pilot QA checklist for audio, images, task flow, export, and model recovery.
- `docs/pilot_runbook.md`
  - Step-by-step pilot procedure and go/revise criteria.
- `analysis/README.md`
  - Planned modeling outputs and file conventions.

## Stimulus Policy

The validation set uses pseudowords rather than real English words. This avoids
uncontrolled prior vocabulary knowledge and allows tighter control over syllable
count, segmental contrasts, and phonological neighborhood density.

The default selected master set is:

- 40 pseudowords total.
- 20 easy control pseudowords.
- 20 difficult pseudowords, balanced across 5 contrast classes.
- All items are designed as two-syllable pseudowords.
- Difficult items are organized as minimal-pair groups where possible.

The adopted task design is Plan 2:

- 20 words per participant.
- 5 learning blocks.
- 3 encounters per word per block.
- 3 words and 3 objects per learning trial.
- Click-based 5AFC test after each learning block.
- Chrome-only browser gate.
- Volume check and short practice session with separate stimuli.
- 30-second 5AFC response window; timeouts are saved as no response.
- No familiarization task.

## Regenerate Stimuli

From this repository root:

```bash
python3 CSSL_Validation/stimulus_tools/build_validation_stimuli.py
python3 CSSL_Validation/stimulus_tools/build_plan2_lists.py
python3 CSSL_Validation/stimulus_tools/generate_object_svgs.py
python3 CSSL_Validation/stimulus_tools/generate_gtts_audio.py
```

These scripts write inside `CSSL_Validation/stimuli/`, `CSSL_Validation/audio/`,
and `CSSL_Validation/images/objects/`.

## Run Switching Simulation

From this repository root:

```bash
python3 CSSL_Validation/analysis/simulate_switching_recovery.py --participants 80
```

Or run the predefined scenario sweep:

```bash
python3 CSSL_Validation/analysis/run_simulation_scenarios.py --participants 80
```

Benchmark multiple analysis strategies:

```bash
python3 CSSL_Validation/analysis/benchmark_analysis_methods.py --participants 80
```

This writes ignored diagnostic files under
`CSSL_Validation/analysis/simulation_outputs/`. Use the summary to check whether
the adopted schedule can recover plausible PbV onset timing before collecting a
full sample. Use `--scenario weak_signal`, `--scenario late_switch`, or
`--scenario strong_signal` to inspect whether conclusions depend on the assumed
generative process; `threshold_sensitivity_summary.csv` reports recovery across
posterior cutoffs.

## Run Pilot QA

From this repository root:

```bash
python3 CSSL_Validation/analysis/prepare_audio_qa.py
python3 CSSL_Validation/analysis/qa_image_similarity.py --participants 80
```

These scripts write ignored QA tables under
`CSSL_Validation/analysis/qa_outputs/`.

After collecting a pilot workbook:

```bash
python3 CSSL_Validation/analysis/analyze_model_ready.py path/to/export.xlsx
```

This writes ignored descriptive summaries under
`CSSL_Validation/analysis/participant_summaries/`.

## Run Browser Task

From this directory:

```bash
python3 -m http.server 8787
```

Then open:

```text
http://127.0.0.1:8787/index.html
```

The browser task loads the four counterbalanced lists, assigns list A/B/C/D
from the participant ID, generates the deterministic Plan 2 schedule, runs a
short practice session, and exports one Excel workbook at the end. Audio is read
from `audio/{word}.mp3`; if a file is missing, the browser falls back to speech
synthesis for interface checks.

## Data Export

For switching analyses, the task should export at minimum:

- participant ID and deterministic seed,
- block and trial indices,
- word ID, object ID, option set, and word-object context,
- response object/position/key,
- response correctness,
- response time,
- previous response/correctness for the same word where available.

The workbook also includes a `ModelReady` sheet. It combines learning and 5AFC
observations in chronological order and adds numeric flags for contingency and
switching analyses.
