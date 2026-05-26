# Primary Literature Sources

This file collects primary sources for modeling cross-situational statistical
learning (CSSL/CSWL), with emphasis on sources that can inform the validation
task and future computational models. Reviews are useful later, but the list
below prioritizes original experiments, original computational models, and
methodological sources from computational linguistics.

## Core CSSL Experiments

| Source | Primary contribution | Relevance here |
| --- | --- | --- |
| Siskind (1996), Cognition. DOI: https://doi.org/10.1016/S0010-0277(96)00728-7 | Early computational study of learning word-to-meaning mappings across ambiguous situations. | Historical root for treating CSSL as a lexicon induction problem. |
| Yu & Smith (2007), Psychological Science. DOI: https://doi.org/10.1111/j.1467-9280.2007.01915.x | Adult participants rapidly learned word-referent mappings from ambiguous trials. | Main behavioral precedent for the validation task structure. |
| Smith & Yu (2008), Cognition. DOI: https://doi.org/10.1016/j.cognition.2007.06.010 | Infants learned word-referent mappings from cross-situational statistics. | Developmental evidence that CSSL is not only an adult strategy. |
| Vouloumanos (2008), Cognition. DOI: https://doi.org/10.1016/j.cognition.2007.08.007 | Tested adults' sensitivity to fine-grained mapping frequencies. | Important for deciding whether learners track graded statistics or only high-probability mappings. |
| Smith, Smith, & Blythe (2011), Cognitive Science. DOI: https://doi.org/10.1111/j.1551-6709.2010.01158.x | Experimental study of word-learning mechanisms in CSSL. | Relevant to comparing associative and hypothesis-like strategies. |
| Suanda, Mugwanya, & Namy (2014), Journal of Experimental Child Psychology. DOI: https://doi.org/10.1016/j.jecp.2014.06.003 | Young children learned word-object mappings from ambiguous naming events. | Developmental benchmark for task difficulty and response format. |
| Vlach & Johnson (2013), Cognition. DOI: https://doi.org/10.1016/j.cognition.2013.02.015 | Examined memory constraints on infant cross-situational learning. | Motivates memory/decay parameters in future CSSL models. |

## Propose-But-Verify And Hypothesis-Based Models

| Source | Primary contribution | Relevance here |
| --- | --- | --- |
| Trueswell, Medina, Hafri, & Gleitman (2013), Cognitive Psychology. DOI: https://doi.org/10.1016/j.cogpsych.2012.10.001 | Proposed a single-hypothesis "propose-but-verify" procedure and used contingent-response analyses. | Direct source for the PbV logic, but note that our no-feedback task should model internal hypothesis consistency rather than objective previous correctness. |
| Stevens, Gleitman, Trueswell, & Yang (2017), Cognitive Science. DOI: https://doi.org/10.1111/cogs.12416 | Introduced the Pursuit model: probabilistic associations plus a local best-hypothesis strategy. | Strong candidate for a CSSL model that bridges associative and PbV accounts. |
| Roembke & McMurray (2016), Journal of Memory and Language. DOI: https://doi.org/10.1016/j.jml.2015.09.005 | Used eye movements and trial histories to argue against overly simple PbV or simple co-occurrence accounts. | Warns that multiple sources of trial history may shape responses beyond a single hypothesis. |

## Associative, Bayesian, And Hybrid CSSL Models

| Source | Primary contribution | Relevance here |
| --- | --- | --- |
| Frank, Goodman, & Tenenbaum (2009), Psychological Science. DOI: https://doi.org/10.1111/j.1467-9280.2009.02335.x | Bayesian model jointly inferring word meanings and speakers' referential intentions. | Useful template for adding referential-pragmatic variables or priors. |
| Fazly, Alishahi, & Stevenson (2010), Cognitive Science. DOI: https://doi.org/10.1111/j.1551-6709.2010.01104.x | Probabilistic computational model of CSSL. | Direct source for EM/probabilistic alignment-style CSSL modeling. |
| Kachergis, Yu, & Shiffrin (2012), Psychonomic Bulletin & Review. DOI: https://doi.org/10.3758/s13423-011-0194-6 | Adaptive associative model with competition, attention, and inference-like behavior. | Important for interpreting "PbV-like" behavior that can emerge from associative dynamics. |
| Yu & Smith (2012), Psychological Review. DOI: https://doi.org/10.1037/a0026182 | Examined prior modeling questions and component interactions in CSSL models. | Methodological warning: different models can produce similar aggregate behavior. |
| Yurovsky, Yu, & Smith (2013), Cognitive Science. DOI: https://doi.org/10.1111/cogs.12035 | Studied competitive processes in CSSL. | Supports adding competition among referents or words rather than independent word learning. |
| Yurovsky & Frank (2015), Cognition. DOI: https://doi.org/10.1016/j.cognition.2015.07.013 | Integrated associative and hypothesis-testing constraints in one account. | Useful precedent for mixed-mechanism or memory-attention models. |
| Bhat, Spencer, & Samuelson (2022), Psychological Review. DOI: https://doi.org/10.1037/rev0000313 | WOLVES neural process model of word-object learning via visual exploration. | Useful if response trajectories and visual attention become central. |

## Broader Word Learning And Statistical Learning Foundations

| Source | Primary contribution | Relevance here |
| --- | --- | --- |
| Saffran, Aslin, & Newport (1996), Science. DOI: https://doi.org/10.1126/science.274.5294.1926 | Foundational demonstration of statistical learning from speech streams. | Background for treating learning as sensitivity to distributional regularities. |
| Xu & Tenenbaum (2007), Psychological Review. DOI: https://doi.org/10.1037/0033-295X.114.2.245 | Word learning as Bayesian inference. | Source for priors, sampling assumptions, and individual-level Bayesian aptitude indices. |
| Xu & Tenenbaum (2007), Developmental Science. DOI: https://doi.org/10.1111/j.1467-7687.2007.00590.x | Sensitivity to sampling in Bayesian word learning. | Useful if task instructions or sampling assumptions may change generalization. |

## Computational Linguistics And Alignment Sources

| Source | Primary contribution | Relevance here |
| --- | --- | --- |
| Brown et al. (1993), Computational Linguistics. ACL Anthology: https://aclanthology.org/J93-2003/ | IBM alignment models for statistical machine translation. | Formal precedent for treating word-object mapping as an alignment problem. IBM Model 1 is a natural baseline. |
| Roy & Pentland (2002), Cognitive Science. DOI: https://doi.org/10.1207/s15516709cog2601_4 | Computational model learning words from paired sights and sounds. | Connects CSSL-style mapping to multimodal grounded language learning. |
| Yu & Ballard (2007), Neurocomputing. DOI: https://doi.org/10.1016/j.neucom.2006.01.034 | Unified model integrating statistical and social cues. | Useful if future versions add gaze, salience, prosody, or social-pragmatic constraints. |

## Direct Implications For The Current Project

1. **CSSL model should be word-object alignment first.**
   HMMs are useful for estimating latent response states, but the generative
   model should represent a learner's evolving beliefs about `P(object | word)`
   or a hypothesis `h_word`.

2. **PbV should use learner-available evidence.**
   In the current no-feedback task, learners do not observe objective
   correctness. PbV-style updating should therefore be based on whether the
   learner's current hypothesis appears in the next context, whether it is
   selected again, and whether the word form is perceived as the same item.

3. **Phonological encoding should be explicit.**
   Hard contrasts can be modeled as a noisy channel:

```text
intended word -> perceived word -> word-object mapping update
```

   This can distinguish a delayed PbV switch from unstable phonological
   encoding.

4. **Model comparison should include non-HMM alternatives.**
   The primary candidates to implement next are:

   - IBM Model 1 / EM alignment baseline,
   - Bayesian lexicon learner with entropy reduction,
   - Pursuit/PbV-style hypothesis learner,
   - noisy-channel phonological learner,
   - associative learner with competition and memory decay.

5. **Aptitude indices can be decomposed.**
   A single CSSL aptitude score may hide multiple components:

   - mapping aptitude: speed of `P(object | word)` concentration,
   - phonological encoding aptitude: stability of intended-to-perceived word
     identity,
   - hypothesis maintenance: tendency to preserve a viable hypothesis,
   - hypothesis revision: tendency to abandon unavailable hypotheses,
   - competition sensitivity: degree of mutual exclusivity or one-to-one
     pressure.
