# Task Refinement Logic

## Prior-Study Logic

The validation task keeps the core CSSL structure from Yu & Smith (2007) and
Smith & Yu (2008): learners hear words in referentially ambiguous scenes and can
learn mappings by aggregating word-object co-occurrences over situations.

The task also keeps the modeling contrast motivated by Medina et al. (2011) and
Trueswell et al. (2013): participants may not always behave like pure graded
associators; they may adopt and verify a single candidate referent. Berens et
al. (2018) motivates tracking the first reliable behavioral verification point,
while Kachergis et al. (2012) and Yurovsky & Frank (2015) motivate keeping
graded associative and hybrid alternatives in the analysis plan.

For the present validation task, the resulting design choices are:

- Use repeated 3-word/3-object ambiguity instead of explicit teaching.
- Save learning responses after each spoken word, not only final test accuracy.
- Treat `encounterIndex = 1..15` as the primary time axis for switch estimation.
- Keep blockwise 5AFC tests to provide clean retrieval checkpoints.
- Balance phonologically difficult items so mechanism switching is not confounded
  with one hard contrast.

## Instructions And Practice

The practice session is intentionally short and separate from the main schedule.
It teaches only the response rule:

- Hear a pseudoword.
- Click the matching picture.
- In the test phase, click one picture from five options.

Practice data are exported for QA but excluded from model fitting.

## Visual Stimulus Policy

Real pictures are not ideal here because familiar objects invite existing labels
and semantic associations. Purely random abstract images can also be problematic
if some pairs are visually too similar. The current compromise is a generated
abstract SVG set:

- no real-world object labels;
- high discriminability through outline, palette, rotation, and internal marks;
- deterministic file generation for reproducibility;
- visual-family constraints in schedule generation.

If pilot participants still confuse visual neighbors, the next correction should
be to increase the number of outline families or manually replace the confusing
SVGs, not to move to real-object pictures.

## Audio Policy

The current audio files are generated with gTTS from `ttsText` respellings.
This is more stable than browser speech synthesis and produces static MP3 files
for deployment. The MP3s still require human review because pseudoword
pronunciation can drift from the target IPA.
