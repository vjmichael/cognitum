# Cognitum C15 T2 P2O — Structural hypothesis reconciliation

**Date:** 2026-10-28. **Scope:** Independent Cognitum research-only implementation. Lu, GitHub and real datasets unchanged.

## Added contract and executable reference

- `proto/cognitum/spatial/v1/structural_reconciliation.proto`: Protobuf-native bounded alternative claims + sequenced evidence changes, compiler-derived Python bindings; serialized unknown fields fail closed.
- `cognitum/spatial_structural_reconciliation.py`: immutable ontology template, deterministic replay of type/edge additions and explicit retractions; every intermediate candidate state re-audited with the existing P2N ontology and mereology rules.
- `tools/run_c15_p2o_t2_reconciliation.py`: reproducible two-candidate example demonstrating conflict introduction and caller-declared retirement; no real-world evidence or efficacy claim.

## Reconciliation semantics

Every candidate is independent (max 8, max 128 events globally, max 64 per candidate, max 128 active claims per candidate). Input events are contiguous and one-indexed **within** each candidate, and globally unique by event ID; source IDs, rationale and claim IDs are mandatory. A candidate can add a scoped type or edge claim, or retract an *active* same-candidate claim. Claim IDs cannot be reused. P2N rejects self/unknown nodes, invalid types, contradictory observed/hypothetical promotions, duplicate entailed claims, cycles or multiple structural parents. Bad revisions reject the whole request; there are no partial writes.

After each revision the output records introduced and resolved contradiction IDs, current active claim IDs, supporting source references, the original change's stated rationale/source, stable snapshot digest, and append-stable chained journal checksum. The output also includes a per-candidate final status and typed findings. The journal digest is an integrity checksum, **not** a signature or authenticated authority. Source refs and `EVIDENCE_OBSERVED` labels are supplied by callers, **not authenticated**.

**Interpretation rule:** `CLAIMS_CONSISTENT` means no contradiction found by the **finite supported P2N rules on the current claims**. It is *not* evidence of truth, verified object recognition, automatic selection among alternatives, high confidence, full OWL reasoning or valid scene mutation. An arbitrary correction may remove a contradiction but does not prove the remaining claim. `NO_ACTIVE_CLAIMS` is a distinct final state. Open-world absence does not imply a negative claim.

Hypothetical T1/P2M object candidates stay hypothetical. No camera appearance claim is promoted to a physical pose; T3 occupancy/projection, Lu host authority, security scope changes, and canonical persistence are excluded. Source revisions are hypothetical caller requests, not a revocation of sensor facts or a host policy change.

## Focused verification

- A mechanical vs void classification produces a disjoint contradiction; retiring the void claim records a resolved contradiction without selecting a true explanation.
- Alternative candidates remain isolated; attempted cross-candidate retirement fails.
- Typed part edges can generate contradiction through P2N declared relation signatures; retracting an edge reverses its derived source support.
- Unknown/malformed Protobuf fields, revision gaps, duplicate IDs, source/scope mismatches, invalid edges, false authority and observed/hypothetical conflation reject the full request.
- Deterministic replays match hashes, and older receipts remain stable when events append. An independent class-closure + disjointness oracle checks the randomized retraction cases (separate from comparing per-revision P2N audits).
- Historical datasets and learned tracking benchmark records are preserved; new experimental benchmark dependencies recorded in `C15-T2-P2O-reconciliation-backlog-v1.json`.

## Reproduce

```bash
PYTHONPATH=. python tools/run_c15_p2o_t2_reconciliation.py --out /tmp/c15-p2o-example.json
PYTHONPATH=. python -m pytest -q tests/test_c15_t2_p2o_reconciliation.py tests/test_c15_t2_p2n_ontology.py
PYTHONPATH=. python tools/verify_protobuf_schemas.py --require
PYTHONPATH=. python -m pytest -q tests/test_c15* tests/test_c13* tests/test_c14*
```

**Open gates:** external OWL-RL/independent truth maintenance and longitudinal multi-source real structural datasets, authenticated permissions/revocation, durable host journal/restart, Windows-native sandbox, calibrated T2/T3 sensor observations, real Lu-model evaluation. None is implicitly passed by the P2O offline reference.
