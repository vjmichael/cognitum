# Cognitum C15 T2 P2O — Structural Hypothesis Reconciliation

**Date:** 2026-10-28  
**Disposition:** Offline implementation and smoke-test checkpoint accepted as research-only; external scientific and production/host validation gates remain open.

## Summary

Continued from the saved C15 T2 P2N source ZIP. Implemented an additive, independently compiled Protobuf request/result schema and a bounded, deterministic revision ledger for comparing competing *claimed* structural explanations. No Lu, GitHub, Windows, or benchmark dataset files were changed.

Each candidate holds a separate, research-only hypothesis ledger. Additions of node-type or part–whole edge claims and explicit caller-requested retractions are validated against the unchanged P2N ontology subset. Every revision re-audits the current hypothesis, reports introduced/resolved disjoint-type contradictions and supporting sources, and returns content-addressed request/snapshot/ontology hashes plus append-stable chained revision receipts. There is no probabilistic selection of a winning hypothesis or autonomous truth admission.

**Examples of supported behavior:** an object classified as `Mechanical` (subclass `Solid`) plus `Void` produces a disjoint contradiction; retracting the disputed `Void` claim produces an explicit conflict-resolution transition; a declared relation-type rule can introduce the same contradiction through a part/assembly claim, and retracting the edge removes its rule-derived supporting source references.

## Source artifacts

- `proto/cognitum/spatial/v1/structural_reconciliation.proto`
- `cognitum/proto/spatial_structural_reconciliation_pb2.py`
- `cognitum/spatial_structural_reconciliation.py`
- `tests/test_c15_t2_p2o_reconciliation.py`
- `tools/run_c15_p2o_t2_reconciliation.py`
- `docs/components/spatial/P2O-T2-hypothesis-reconciliation-and-retraction.md`
- `docs/components/spatial/C15-T2-P2O-reconciliation-backlog-v1.json`
- `P2O_START_HERE.md`, `P2O_SHA256SUMS.json`
- Compiler registry change in `tools/check_proto_descriptors.py`; no changes to canonical P2N ontology or C15 structural composition implementation.

## Tests executed in this environment

- Python **3.13.5**, Linux x86-64, Protobuf **6.33.6**.
- Focused P2N + P2O suite: **46 passed, 5 subtests passed**.
- Selected C13/C14/C15 suite: **1,185 passed, 39 skipped, 567 subtests passed, 5 warnings** (not the unrestricted repository suite). Warnings were from existing optional statistical packages and duplicate-archive negative tests, not from new P2O test failures.
- Independent Protobuf compilation: **64/64 schemas matched generated binding descriptors**.
- Randomized retractions: **120 seeded scenarios** with direct P2N snapshot replay and a separate class-closure/disjointness oracle.
- Clean extraction: **723/723 SHA-256 file entries** verified from a 724-file archive; focused tests and 64 schema comparisons repeated successfully, and the sample CLI output hash was identical to the archived version.
- Original tracking benchmark backlog: SHA-256 `4d117d91114dc2ca401d493319f293528fccddce3fe2ecddf2b46b5783702390` — unchanged.
- Original T2 external reasoner backlog: SHA-256 `389709eea052ed3342d1a6918dcbbfb72ce56f8c9ba4d1567d502baee10f7ec1` — unchanged.

## Safety and interpretive boundaries

- All data remains caller-declared and unauthenticated. Even a field labeled `EVIDENCE_OBSERVED` is not a verified sensor record.
- An output marked `CLAIMS_CONSISTENT` is simply **consistent with the current explicit claim set under the finite P2N subclass/disjoint/edge-signature rules**. It is not physically verified, a complete OWL 2 finding, a Bayesian posterior, or an instruction to adopt that hypothesis.
- Zero implicit authority or canonical scene mutation. Image-space hypotheses are not physical structure, occupancy rays or 3D observations.
- Retractions are ephemeral within the request replay; there is no durable event store, source permission, atomic host journal, Windows native worker security, or Lu integration.
- The SHA-256 receipt chain is an integrity checksum, **not a cryptographic signature or a claim of verified publisher identity**.

## Deferred evaluation backlog

The six pre-existing tracking/appearance experiments and three pre-existing ontology comparisons have been preserved byte-for-byte. Three new separately listed P2O gates remain open: independent truth-maintenance parity, real longitudinal corrected structural claims, and secure durable journal/restart integration. These were not run or silently marked as passed.

## Next research milestone

A useful P2P direction is conservative cross-conversation revision integration with Cognitum's existing C07 typed belief-state work, including explicit source/revision trust boundaries and no authority elevation. Independently validated truth-maintenance and real structural datasets should precede claims of scientific benefit. T3 calibrated geometry remains an independent future workstream.