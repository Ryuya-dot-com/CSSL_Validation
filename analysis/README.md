# Analysis Workspace

This directory is reserved for validation analyses. No scripts here should write
outside `CSSL_Validation` unless explicitly configured by a command-line argument.

Planned outputs:

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
