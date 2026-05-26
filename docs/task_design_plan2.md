# Adopted Task Design: Plan 2

## Summary

Plan 2 is the adopted validation design.

- 20 pseudowords per participant.
- 10 easy control words.
- 10 hard words.
- Hard words include one minimal-pair group from each difficult contrast:
  `r_l`, `v_b`, `theta_s`, `cluster_r_l`, `cluster_v_b`.
- 5 learning blocks.
- Each word appears 3 times per learning block.
- Each learning trial presents 3 objects and 3 spoken pseudowords.
- Each block is followed by a click-based 5AFC test.
- 5AFC has a 30-second response window.
- A short practice session uses separate practice words and objects.
- Practice begins with a volume check.
- No familiarization task.

## Trial Counts

```text
Learning per block:
20 words * 3 encounters = 60 word events
60 word events / 3 words per trial = 20 learning trials

Learning total:
20 learning trials/block * 5 blocks = 100 learning trials
20 words * 15 total encounters = 300 word events

Test total:
20 test trials/block * 5 blocks = 100 5AFC test trials

Grand total:
200 main trials, excluding instructions, practice, breaks, and audio checks
```

## Why 20 Words

Twenty words fit the 3-word learning-trial format when each word appears 3
times per block:

```text
20 * 3 = 60
60 / 3 = 20 trials
```

This preserves a clean 3x3 CSSL learning structure while giving enough
word-level repetitions to estimate switching over encounter number 1 to 15.

## Why Keep a 40-Word Bank

The 40-word bank is not intended for a single participant. It supports
counterbalancing and replacement. Plan 2 now uses four participant lists:

- List A: 10 control + 10 hard.
- List B: 10 different control + 10 different hard.
- List C: 10 control + 10 hard.
- List D: 10 control + 10 hard.
- Each hard list keeps one complete minimal-pair group from every contrast.
- Each control item appears in two of the four lists.
- Each hard minimal-pair group appears in two of the four lists for its contrast.

The generated list files are:

- `stimuli/participant_lists_plan2.csv`
- `stimuli/participant_lists_plan2.json`

## Primary Time Axis

For mechanism-switching analyses, the primary time axis should be the
word-specific encounter index:

```text
encounterIndex = 1..15
```

Block index is still useful for reporting and visualization, but relying only on
5 block-level points would be too coarse for estimating switch timing.

## 5AFC Test Structure

Each test block should include one test trial per word. Responses should be
collected by mouse/touch click on one of five object options. Foil sampling
should prioritize interpretability:

- target object,
- same contrast group foil when available,
- same phonology foil,
- different contrast hard foil,
- unrelated control foil.

For control targets, foils should include at least one hard item and multiple
control items to avoid making hard/easy status an obvious answer cue.

Correct target position is balanced within each 5AFC block: 20 test trials
with five options means each screen position is correct exactly four times per
block. This prevents response-side or visual-position bias from being absorbed
into participant-level learning parameters.

### Time Limit And No Response

The validation task uses a 30-second response window for 5AFC trials. This is
not meant to force fast decisions; it prevents the experiment from stalling and
makes non-completion explicit. If the participant does not respond within the
window, the row is saved as:

```text
responseSource = timeout
noResponse = true
responseTimedOut = true
correct = false
```

The trial then advances automatically. Main learning responses remain untimed
because they are used to infer trial-by-trial learning state and should not be
lost due to a strict deadline.

Main-task 5AFC replay is disabled after the initial volume check and practice
session. This keeps the test observation closer to a single standardized
perceptual event; audio play success and timing are still saved for each trial.

## Practice Session

Practice is included to make the response format unambiguous without changing
the main learning statistics.

- Practice starts with an audio volume check.
- Practice uses separate pseudowords and separate abstract objects.
- Practice includes one 3-object learning example and one 5AFC example.
- Practice responses are saved in the workbook but excluded from model fitting.
- Main-task feedback remains absent.

## Stimulus Presentation Logic

The adopted presentation logic follows three constraints from the CSSL and PbV
literatures:

- Maintain referential ambiguity during learning: each learning trial has three
  spoken words and three candidate objects.
- Preserve repeated cross-situational evidence: each word appears three times
  per block and fifteen times total.
- Preserve hypothesis-testing observability: a response is collected after each
  spoken word, so trial-by-trial shifts toward single-hypothesis behavior can be
  estimated.

## Object Images

The task uses generated abstract SVG objects rather than real-object pictures.
This avoids uncontrolled prior labels while keeping the visual set stable.
Each object has a visual family based on outline shape, and the schedule avoids
placing the same visual family in a single learning trial. This keeps CSSL
difficulty driven primarily by word-object ambiguity and phonological contrast,
not accidental visual similarity.

## Output

The browser task writes one Excel workbook (`.xlsx`) containing:

- `Data`: 5AFC test trials.
- `LearningEvents`: one row per spoken word during learning.
- `LearningTrials`: one row per learning context.
- `Practice`: tutorial responses only.
- `PairMap`: word-object mapping and visual-family metadata.
- `ModelReady`: chronological learning and test observations with phonological
  metadata and previous-hypothesis availability flags.
- `LearningSchedule` / `TestSchedule`: deterministic schedules.
- `Config`, `Summary`, and `Notes`.

## Browser

The task is restricted to Google Chrome. Browser audio policies, MP3 playback,
download behavior, and timing APIs differ across browsers; restricting the
runtime reduces avoidable variance in audio playback and response collection.

## Randomization

Participant ID should be used as the seed source. The same participant ID should
always reproduce the same list assignment, learning schedule, object positions,
word order, 5AFC foils, balanced target positions, and 5AFC option order.

Use:

```bash
python3 CSSL_Validation/stimulus_tools/build_plan2_schedule.py --participant-id SUB001
```

List assignment is deterministic:

```text
listId = ["A", "B", "C", "D"][seed mod 4]
```
