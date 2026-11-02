# Cognitum P21 — First offline HDC training run

**Date:** November 1, 2026 (America/Phoenix; UTC test artifacts may show November 2)  
**Disposition:** Synthetic **research training completed**, NOT a physical-world model and NOT production-certified.  
**Scope:** Linux-only Cognitum research overlay on P20. No Lu source modified; Windows and P15 deferred.

## Goal and experimental boundary

Train an evidence-aware, **role-sensitive directed-relation triage model** as the first HDC training milestone for Cognitum's future physical-world representations. A structured query (subject, predicate, object) and its evidence records are provided as inputs. The model predicts `supported`, `refuted` or `unverified`. No visual or physical raw sensor perception is included. Real-world interiors are neither inferred nor fabricated.

**Important:** a **deterministic preprocessor performs exact directed tuple matching and supplies trusted/untrusted evidence fields**. The trained HDC is a small *policy classifier*, not a system that independently discovers relational facts. The reference evidence policy remains authoritative and prevents an incorrect HDC positive claim from being used as evidence. Provenance attestation itself must occur at an external trusted ingestion boundary, not by accepting user-supplied `verified=true` strings.

## Data and training

- Offline synthetic generator: `cognitum/research/grounded_hdc_p21.py`. Deterministic sources, queries and evidence; every fixture's label comes from a small reference evidence policy.
- Training: **2,400** balanced cases; holdout validation: **600**; engineering development test: **900**. Distinct subject/object identifiers and relation vocabularies are used for train, validation and test.
- Eight abstention challenges: role reversal, other object, other predicate, untrusted rumor, missing fact, conflicting facts, photo-only evidence, source name with unverified receipt.
- Grid search: dimensions **256, 1,024, 2,048** and corrective epochs **0 or 4**. Selection used validation accuracy, then smallest dimension and fewest epochs.
- Selected configuration: **256 dimensions / four correction epochs**; trained through P19's single-pass centroid bundling and mistake-driven corrections. Trained checkpoint: `artifacts/p21/hdc_evidence_classifier_p21.npz` (**1,796 bytes**; SHA-256 `585fe8d1e4e1c16e1ef5bc3a009db6889887e81036f29713ae6509215808e0c8`). The model is real trained numeric centroids, not a hand-authored fixture. Checkpoint contains labels, dimensions, encoder and training-dataset digest, not raw training rows.

## Scored results

| Test | Raw HDC accuracy | Notes |
|---|---:|---|
| Validation, 600 cases | **100.00%** | Used for model selection |
| Development test, 900 cases | **100.00%** | Earlier version exposed role-reversal errors, so this set is NOT a pristine final holdout |
| Fresh post-selection audit, seed 20261127, 1,800 cases | **100.00%** | Independent entity IDs; same generator/labeling mechanism |
| Fresh post-selection audit, seed 20261229, 1,800 cases | **100.00%** | Independent entity IDs; same generator/labeling mechanism |
| Fresh post-selection audit, seed 20270119, 1,800 cases | **100.00%** | Independent entity IDs; same generator/labeling mechanism |
| Role reversal, development test, 38 cases | **38 / 38** | Role-sensitive feature extraction |
| Unordered token-bag ablation on development test | **91.89%** | Only 4 / 38 role-reversal cases correct |
| Majority-class baseline on balanced development test | **33.33%** | Fails to distinguish claim statuses |
| Exact deterministic reference policy | **100.00%** | Solves this toy task without learned HDC |

On the final 5,400 synthetic audit examples, guarded false assertions were **zero**. This is a property of the synthetic test plus the independent deterministic guard, **not an empirical physical-world safety guarantee**.

One coding issue from the first development run was discovered: including novel predicate names in the learned feature vector degraded role-reversal performance. Removing that irrelevant lexical token and preserving directed tuple structure improved development accuracy. Because this correction used results from the development test, the independent post-selection audit uses separate seeds and disjoint identities; the family generators and underlying mechanism nevertheless remain shared, so audit evidence has limited external validity.

## Tests and packaging

- Focused tests: `PYTHONPATH=. pytest -q tests/test_grounded_hdc_p21.py tests/test_training_artifacts_p19.py tests/test_world_grounding_p20.py` → **26 passed**, plus one expected duplicate-archive warning from a malicious archive fixture.
- Standalone installed development wheel: **300 / 300** synthetic inference and reference checks outside the source tree.
- Research wheel rebuilt with P19, P20 and P21 research code; RECORD/checksum verification passed.
- Audit and training reports include exact dataset SHA-256 digests, model SHA-256, selected hyperparameters and per-scenario test confusion matrices. The generators are deterministic and can regenerate cases. No raw training rows are in the model.

## Not yet established

1. **No learned composition, hidden interior inference, direct raw visual understanding, physical dynamics, or object permanence.** Exact structural match features are computed algorithmically before HDC receives them.
2. No demonstrated performance advantage over a deterministic evidence rule. Do not replace trusted evidence verification with HDC.
3. No real-world datasets, externally adjudicated provenance, cross-generator holdout, out-of-distribution sensor tests, or performance-quality assessment by independent experts.
4. No physical flight controller, collision-certification, acting coaching, production film generation, causal identification, or C14 estimator changes.
5. Live kernel cgroup enforcement and OS-deployed independent recovery continue to require a writable delegated Linux test environment.

## Next training milestone

**P21b:** Train HDC on *part/whole physical structure* with cross-object and cross-material generalization and hold out **entire scene generators**. Explicitly compare retrieval/abstention against a symbolic knowledge-graph baseline and against a language-model-only prediction. Preserve unknown interiors as unknown, and never promote merely because of synthetic test accuracy.  
**P22:** KAN learns bounded numerical dynamics with held-out physical parameters; compare against closed-form and conventional solvers.  
**P23:** SSM learns temporal persistence and state transition patterns from simulated object streams.  
**P24:** Human-evaluated performance direction for NVP's Acting Coach, with deterministic blocking and separate vocal/facial animation engines.
