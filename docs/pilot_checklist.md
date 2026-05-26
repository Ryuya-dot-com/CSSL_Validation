# Pilot Checklist

Use this checklist before running the full validation sample. The aim is to
catch design failures that would make switching estimates uninterpretable.

## Audio

- Confirm every MP3 is audible in Google Chrome.
- Check whether each pseudoword pronunciation matches the intended TTS
  respelling closely enough for the task goal.
- Pay special attention to hard contrasts: `r_l`, `v_b`, `theta_s`,
  `cluster_r_l`, and `cluster_v_b`.
- Record any item that sounds like a real English word or another target item.

## Images

- Confirm all SVG objects load in the task.
- Check that no 5AFC option set contains two images that are hard to distinguish
  at the displayed size.
- Check whether any abstract object invites an obvious verbal label that could
  become easier than the word-object mapping itself.

## Task Flow

- Confirm non-Chrome browsers are blocked.
- Confirm the volume check occurs before practice.
- Confirm practice is understandable but short enough not to teach the main
  stimulus structure.
- Confirm the main task feels monotonous but not confusing; visual simplicity is
  intentional.

## Data Export

- Confirm one `.xlsx` file downloads at the end.
- Confirm the workbook includes `Metadata`, `Summary`, `Data`, `ModelReady`,
  `LearningEvents`, `Practice`, and schedule sheets.
- Confirm timeout rows in `Data` have `noResponse=1`, `timedOut=1` in
  `ModelReady`, and `correct=0`.
- Confirm `ModelReady` is chronologically ordered within each participant.

## Pilot Decision Rules

- If block-5 5AFC is near chance for most participants, simplify images or audio.
- If block-1 or block-2 5AFC is near ceiling, reduce item salience or inspect
  whether images have obvious verbal labels.
- If hard contrasts are uniformly at floor, replace the most ambiguous MP3s or
  reduce the number of hard items.
- If timeouts are frequent, lengthen the 5AFC window or revise instructions.
- If the switching simulation cannot recover onset within 1-2 encounters under
  plausible assumptions, avoid strong HMM claims until the design is revised.
