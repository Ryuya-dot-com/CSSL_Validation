# Analysis Method Catalog

This project should not rely on a single HMM analysis by default. The CSSL task
can support several complementary analysis families, each answering a slightly
different question.

## Descriptive And Psychometric Checks

- Block-level 5AFC accuracy
  - Primary sanity check for learning.
- Hard/easy phonology split
  - Checks whether the intended difficulty manipulation is visible.
- Previous-correct contingency
  - The clearest descriptive PbV signature: stronger performance after a
    correct previous same-word response than after an incorrect one.
- Item-level trajectories
  - Identifies broken audio, overly salient images, or item-specific failures.

Use these before any latent model.

## Mechanism-Inspired Learner Models

- Associative learner
  - Responses are driven by graded accumulated co-occurrence evidence.
- PbV learner
  - Responses are driven by a single proposed hypothesis that is verified or
    revised.
- Mixture-of-mechanisms model
  - Trial-level response probability is a weighted mixture of associative and
    PbV predictions.
- Mechanism likelihood ratio
  - Compares PbV-like and associative emission likelihoods over encounters.

These models are closest to the CSSL/statistical-learning question, but they
still require clear assumptions about what each mechanism predicts.

## State-Space And Switching Models

- HMM or Markov-switching model
  - Treats `explore`, `associative`, and `pbv` as latent states.
- Hidden semi-Markov model
  - Adds explicit state-duration assumptions; useful if rapid back-and-forth
    switching is implausible.
- Dynamic logistic/state-space model
  - Lets a continuous PbV tendency change gradually over encounters.

These are appropriate only if pilot data and simulations show enough temporal
information to recover state changes.

## Change-Point And Survival Approaches

- Bayesian change-point model
  - Estimates whether there is a discrete improvement point in a word
    trajectory.
- Survival or hazard model
  - Treats PbV adoption as a time-to-event outcome, with predictors such as
    phonology, previous correctness, participant-level ability, and item
    difficulty.
- Discrete-time event-history model
  - A regression-friendly version of the hazard approach.

These approaches are useful when the scientific estimand is onset timing rather
than full trial-level response generation.

## Reinforcement-Learning And Sequential-Decision Models

- Rescorla-Wagner or delta-rule learner
  - Updates word-object association strengths after each encounter.
- Win-stay/lose-shift model
  - Captures hypothesis persistence after success and revision after failure.
- Q-learning with perseveration
  - Separates learned values from a bias to repeat the prior response.
- Particle-filter or sequential Monte Carlo learner
  - Tracks uncertainty over possible mappings and hypotheses online.

These models are attractive because the task is a repeated decision problem, but
they need careful mapping from no-feedback trials to internal updating.

## Broader Statistical And Machine-Learning Options

- Hierarchical logistic regression or GLMM
  - Estimates accuracy from encounter, block, phonology, previous correctness,
    participant, and item effects.
- Generalized additive model
  - Allows nonlinear learning curves without imposing a discrete switch.
- Latent class or finite-mixture model
  - Clusters participants or item trajectories into strategy-like profiles.
- IRT-style model
  - Separates participant aptitude, item difficulty, and phonological burden.
- Cross-validated predictive models
  - Useful for prediction and variable importance, but not automatically
    interpretable as learning mechanisms.
- RT-aware models
  - If response times are reliable, drift-diffusion or evidence-accumulation
    models may separate decision confidence from accuracy.

These methods can complement mechanism models, especially for robustness checks
and aptitude measurement.

## Current Simulation Benchmark

`analysis/benchmark_analysis_methods.py` currently compares:

- HMM posterior thresholds,
- rolling-accuracy rules,
- consecutive-correct rules,
- cumulative-accuracy rules,
- PbV-vs-associative likelihood ratio,
- beta-binomial change-point detection,
- a survival-style prior hazard rule.

The benchmark intentionally mixes simple and model-based estimators. If a
complex method only performs well under the `strong_signal` scenario or only at
one threshold, treat it as exploratory until pilot data support it.

## Recommended Analysis Ladder After Pilot

1. Descriptive export QA and item-level diagnostics.
2. GLMM or hierarchical logistic summaries for accuracy.
3. Contingency analysis: previous correct versus previous incorrect.
4. Mechanism likelihood comparison and simple change-point checks.
5. Continuous mixture or state-space model if simulation recovery is acceptable.
6. HMM/HSMM only as a later model, with sensitivity analyses reported.
