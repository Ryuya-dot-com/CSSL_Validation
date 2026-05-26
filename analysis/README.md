# Analysis Workspace

This directory is reserved for validation analyses. No scripts here should write
outside `CSSL_Validation` unless explicitly configured by a command-line argument.

Planned outputs:

- `simulation_outputs/`
  - Optional synthetic-data diagnostics produced by
    `simulate_switching_recovery.py`. This directory is ignored by git.
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

1. Validate exports and trial histories.
2. Fit contingent-response summaries.
3. Fit windowed associative/PbV comparisons.
4. Fit a continuous mixture model.
5. Fit a Markov-switching model only if the dataset has enough trials and
   participants.

## Simulation Diagnostic

Before collecting the full sample, run a design-recovery simulation to check
whether Plan 2 has enough observations to recover plausible PbV-onset timing.

```bash
python3 CSSL_Validation/analysis/simulate_switching_recovery.py --participants 80
```

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

Treat this as a design diagnostic, not as the final inferential model. If the
simulation shows poor recovery even under friendly assumptions, the behavioral
task should be adjusted before relying on HMM estimates from real data.
