# Cognitum P21b — Frozen HDC adversarial unfamiliar-structure evaluation

**Date:** 2026-11-01 (Phoenix). Linux-only; no retraining, Lu changes, Windows work, or production promotion.

## Actual local test

The frozen P21 trained classifier (`hdc_evidence_classifier_p21.npz`, SHA-256 `585fe8d1e4e1c16e1ef5bc3a009db6889887e81036f29713ae6509215808e0c8`) was verified and evaluated on 2,400 new **synthetic** query/evidence cases: twelve structured scenario types across ten disjoint named scene families (spacecraft, organisms, film sets, drones, alien artifacts, and more). No model updates or held-out tuning.

| Method | Correct / 2400 | Accuracy | Incorrect factual assertions |
|---|---:|---:|---:|
| HDC alone | 1,400 | 58.33% | 400 |
| P21 exact-evidence policy | 2,000 | 83.33% | 0 |
| HDC + original admission guard | 1,400 | 58.33% | 0 |
| Symbolic transitive `part_of` reference | 2,400 | 100% **by construction** | 0 |

HDC got 0/400 transitive two-/three-hop support queries right, 0/200 untrusted-photo-first support queries right, 0/200 distractor-negative-first support queries right and 0/200 distractor-positive-first refutation queries right. These included 400 raw incorrect factual assertions; the original exact-evidence guard prevented all of them but also rejected legitimate support. HDC correctly abstained for 200/200 unknown-interior examples, 200/200 unverified photos, 200/200 reverse-role queries, 200/200 conflicts and 200/200 unrelated facts.

**Evidence permutation:** 400/400 matched pairs changed the raw model prediction when the same two records were reversed; underlying verified facts and oracle decisions were unchanged. Root cause: P21's deterministic feature extractor consults the **first fact's** source and polarity even if a later fact matches the query.

**Structural caveat:** P21's preprocessor removes object identities and does not parse images/material properties. Novel object *names* were not sufficient to test genuine unfamiliar-world reasoning. The graph reference **defines the target labels**; its 100% is not independent generalization evidence. Synthetic scenario counts are uniform, not natural frequency.

## Verification

- P21b isolated adversarial tests **7/7 passed**.
- Existing P19/P20/P21 tests rerun on the full inherited P21 tree **26/26 passed** (one expected duplicate-entry warning from a deliberately invalid archive test).
- Standalone P21b ZIP extracted, SHA-256 manifest verified, and 7/7 tests passed again.
- The standalone archive contains frozen checkpoint, minimal source snapshot, 2,400 individual decisions, 400 evidence-order pair decisions, source, assertions, reproducibility report and checksum manifest.
- Archive SHA-256: `850ec8786bc80d16545d43f2832743658353110dae24a6078cf5ddb77b333669`.

## Gate decision

**NO-GO** for trained HDC as autonomous object-structure/causal-physical reasoner. **GO** for using HDC as a strictly bounded approximate retrieval/triage candidate, with independent graph and provenance checks authoritative.

Next iteration should canonicalize all evidence records, encode roles and relation composition explicitly, hold out complete scene generators, measure abstention/error under evidence permutations, and compare against symbolic and retrieval baselines. Do not relax the P21 assertion guard. Real perception, world grounding and physics remain untested. Windows tasks are deferred. GitHub is documentation/repository only; tested code and artifacts remain in the local ZIP.
