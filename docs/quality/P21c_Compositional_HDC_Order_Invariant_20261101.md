# Cognitum P21c — Role-aware associative HDC versus symbolic graph

**Date:** November 1, 2026. **Linux-only, research-only, NO production promotion.** Lu unchanged; all Windows tasks deferred.

## Motivation and design

P21b showed that the P21 HDC centroid classifier could not compose relationships or handle reordered evidence. P21c tests a **different HDC approach**: a per-scene bipolar associative memory with noncommutative positional permutations for subject, relation and object, approximate unbinding to retrieve candidate graph successors, and strict independent verification of every proposed evidence path. A separate exact graph remains the authority for facts. This is **not a newly trained physical-world model**; the only P21c calibration is selecting vector dimensions and top-k on a validation split, and the old P21 checkpoint remains frozen.

A verified direct negative contradicted by a verified positive multi-hop path is **disputed/abstained**, not categorically refuted. No claims about hidden interiors are permitted without verified evidence. The provenance boundary must authenticate `verified` inputs separately; this research code does not authenticate them.

## Frozen local outcomes

- HDC config selected without test tuning: **2,048 dimensions, top-k 2, cosine threshold 0.08**. Validation **263/264**.
- **744 fresh synthetic held-out cases**, including **9 whole graph topologies (216 cases)** absent from both pilot and validation.
- HDC approximate retrieval plus verified evidence path: **738/744 (99.19%)**, **0 incorrect factual assertions**, six misses where it conservatively abstained. Previously trained P21 centroid: **350/744 (47.04%)**.
- New withheld topologies: **211/216**. Five misses occur in a multi-successor hub; one additional miss occurs with 80 distractor edges.
- Symbolic graph baseline: **744/744 by construction**, since explicit transitive `part_of` rules define the labels. Direct exact-evidence policy does not handle multi-hop queries.
- Evidence order: **0/744 changed decisions** after reversing fact lists. Prior P21b's 2,400 cases independently replayed: **2,400/2,400** with the new index, compared with original P21 raw **1,400/2,400**.
- Runtime, median over four warm Python runs: **symbolic 0.0280 ms/case**, HDC+verifier **0.505 ms/case (~18× slower)**. This is not a performance win over the graph on small structured facts.
- Research tests **15/15 passed**. The source package was extracted into an independent directory, SHA-256 manifest verified, and both benchmark and tests replayed successfully.

## Scientific scope and decision

**PASS only for scoped relational retrieval, directed role binding, evidence-order invariance, contradiction abstention and an independent witness guard on explicit structured synthetic facts. NO-GO for replacing a symbolic graph, for physical-world competence, open-domain generalization, visual perception, hidden interiors, or safety control.**

Next: compare approximate HDC indexing against a symbolic graph and conventional vector/embedding retrieval on genuinely large, noisy stores. If the graph remains simpler, faster and more accurate, retain it. For Cognitum's long-term NVP goal, the next meaningful dataset must include observations from sensors/rendered scenes with authoritative 3D structure withheld from inputs, and measure uncertainty about unseen interiors.

## Reproducibility

Verified local archive: `Cognitum_P21c_Compositional_HDC_Holdout_2026-11-01.zip`, SHA-256 `873a48a85fd36eea374be60def0e951586edf698cf679956f317ac773c9a842e`. It includes source, pinned P21 checkpoint, validation-selected configuration, benchmark, 744 case-level decisions, P21b replay, timing comparison, tests and checksum manifest. Tested experimental code is in the archive, **not merged into production**. GitHub is repository/documentation only.
