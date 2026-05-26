# Randomization Plan

## Deterministic Seed

Participant ID should determine all counterbalancing and randomization.

```text
seed = first 12 hex digits of SHA-256(participantId)
```

Within-list randomization uses a small mulberry32-compatible 32-bit PRNG. This
keeps Python precomputation and browser-side generation aligned.

The same participant ID will always produce the same:

- list assignment,
- learning trial schedule,
- word order within learning trials,
- object positions,
- 5AFC foil sets,
- 5AFC option order.

## List Assignment

The adopted Plan 2 design uses four lists:

```text
listId = ["A", "B", "C", "D"][seed mod 4]
```

The four lists are generated from the 40-word master bank by
`stimulus_tools/build_plan2_lists.py`.

Each list contains:

- 10 control words.
- 10 hard words.
- one complete minimal-pair group for each hard contrast.

Control words are arranged so each control appears in two of the four lists.
Hard minimal-pair groups are arranged so each group appears in two of the four
lists within its contrast family.

## Schedule Generation

Generate a participant schedule with:

```bash
python3 CSSL_Validation/stimulus_tools/build_plan2_schedule.py --participant-id SUB001
```

This writes:

```text
CSSL_Validation/schedules/sub-SUB001_plan2_schedule.json
```

The browser task in `index.html` reproduces the same logic in JavaScript. The
Python script remains useful for precomputing and auditing schedules.

For 5AFC tests, target position is balanced within each block. Each of the five
screen positions is correct exactly four times in the 20 trials of a block,
while foil identity and option order remain participant-seeded.

## Response Modes

- Learning trials: click or keyboard response after each spoken word.
- 5AFC test trials: click response on one of five object options.

Click coordinates or selected option index should be saved with RT.
