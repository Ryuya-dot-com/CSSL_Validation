# Stimulus Design

## Rationale

Real English words are not ideal for this validation task because prior knowledge
would be difficult to control. The validation set therefore uses pseudowords with
explicit phonological metadata. The aim is to isolate individual differences in
cross-situational learning and in the timing of mechanism switching.

## Master Set and Participant Sets

The current target is a 40-item master set:

- 20 `control` items.
- 4 `r_l` items.
- 4 `v_b` items.
- 4 `theta_s` items.
- 4 `cluster_r_l` items.
- 4 `cluster_v_b` items.

All items are intended as two-syllable pseudowords. Hard contrast items are
generated in minimal-pair groups, so each contrast group contains two items that
mainly differ in the difficult segment or onset cluster.

The 40-item master set is not the per-participant task length. The adopted
Plan 2 task uses four 20-word lists:

- 10 control items.
- 10 hard items.
- 2 hard items from each contrast class.

Each participant receives one list. Participant ID determines the list assignment
and randomization seed.

This keeps the 3-word learning-trial format clean because each word appears
3 times per block:

```text
20 words * 3 encounters = 60 word events
60 word events / 3 words per trial = 20 learning trials per block
```

## Controlled Dimensions

- `syllableCount`: fixed at 2 for all selected items.
- `syllableTemplate`: `CVC-CVC` for control and singleton contrasts; `CCV-CVC`
  for cluster contrasts.
- `phonology`: `easy` or `hard`.
- `contrast`: contrast family, such as `r_l` or `theta_s`.
- `contrastGroup`: minimal-pair group identifier.
- `phones`: approximate ARPABET phones.
- `ipaTarget`: target pronunciation for human review.
- `ttsText`: practical respelling for audio generation tools.
- `phonologicalNeighborhoodSize`: number of CMUdict words within phone edit
  distance <= 1.
- `nearestRealWordDistance`: nearest phone edit distance to a CMUdict entry.
- `nearestRealWords`: closest CMUdict entries for manual screening.

## Difficult Contrasts

The hard set is designed around contrasts likely to be difficult for Japanese L1
learners of English:

- `r_l`: singleton English /r/ versus /l/.
- `v_b`: /v/ versus /b/.
- `theta_s`: /theta/ versus /s/.
- `cluster_r_l`: consonant clusters with /r/ versus /l/.
- `cluster_v_b`: /v/-initial cluster versus /b/-initial cluster.

The difficult set is intentionally balanced at the contrast-family level. Later
task versions can sample a smaller subset while preserving this balance.

## Review Rules

Before using the set in data collection:

- Remove items that sound like real English words to native or advanced speakers.
- Listen to generated audio and replace TTS respellings where needed.
- Run ASR-based audio QA and inspect transcript collisions or English-like
  transcriptions as risk flags, not as automatic pronunciation ground truth.
- Run automatic image-recognition QA and inspect highly nameable generated
  shapes, especially if pilot participants report verbal-label strategies.
- Keep minimal-pair members in the same counterbalancing family.
- Do not mix real words and pseudowords in the same validation run unless the
  analysis explicitly models prior vocabulary knowledge.
