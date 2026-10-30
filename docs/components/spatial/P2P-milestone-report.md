# Cognitum C15 T2 P2P — C07-linked structural hypothesis revisions

**Date:** October 28, 2026 (America/Phoenix)  
**Disposition:** Offline, research-only integration checkpoint. Not an installed Lu trust boundary, model accuracy claim, or security certification.

## Implemented

Starting from the Library's frozen C15 T2 P2O source ZIP, added a new `structural_c07_bridge.proto` contract (the **65th** compiled Cognitum Protobuf schema) and a pure Python, read-only integration adapter for pairing P2O structural revision events with the existing C07 typed StateEvent ledger.

- Every P2O type/edge addition or retraction must map to a C07 event of the same ID, candidate and claim identity, with SHA-256 matching the exact deterministic Protobuf structural payload.
- The C07 event history is replayed using the existing `StateLedger` transition rules; the earlier P2O ontology engine remains unchanged. Additional verified C07 `CHALLENGE`, `CONFIRM`, `EXPIRE`, and `TEMPORAL_CORRECT` events are preserved as belief-state history without altering P2O's structural revisions.
- Research output includes event-level provenance-digest, C07 origin, uncertainty, status and revision; claim-level status and review flags; and the untouched full P2O consistency result. C07 `DISPUTED` / `EXPIRED`, explicit uncertainty or low-provenance origin triggers a review flag; it is not an automatic retraction or a hypothesis promotion.
- Requires a **host-held external lease** whose methods must authorize active read scope, event admission, historical and current source checks, and **explicit structural↔C07 source binding**. This Python protocol is a testable reference only. A caller-supplied or LLM-generated mock lease has no authority in real Lu.
- Rejects foreign conversation scope, unknown/duplicate event identity, disallowed changes, noncanonical/unknown Protobuf fields, stale C07 revisions, claim-ID collision across candidates, source refusal and content tampering. No cross-conversation import, canonical write, trusted worker, geometry or scene mutation.

## Files added or updated

- `proto/cognitum/spatial/v1/structural_c07_bridge.proto`
- `cognitum/proto/spatial_structural_c07_bridge_pb2.py`
- `cognitum/spatial_structural_c07_bridge.py`
- `tests/test_c15_t2_p2p_c07_bridge.py` (**32 passing test cases**, including adversarial parameterizations)
- `tools/run_c15_p2p_t2_c07_demo.py` (**mock-lease demo, not a real host test**)
- `docs/components/spatial/P2P-T2-C07-provenance-bridge.md`
- `docs/components/spatial/C15-T2-P2P-deferred-validation-backlog-v1.json`
- `docs/components/spatial/P2P-synthetic-bridge-demo.json`
- `tools/check_proto_descriptors.py` schema registry, `P2P_START_HERE.md` and `README.md`

## Tests and provenance

- Focused C07 revision + P2O + P2P regression: **83 passed**.
- Full C07 selected suite: **218 passed, 71 subtests passed**.
- Selected C13/C14/C15 suite: **1,217 passed, 39 skipped, 567 subtests passed, 5 existing/optional-runtime warnings**. **Not** the unrestricted repository suite.
- Independent Protobuf compiler/binding parity: **65/65 passed** using torch's installed vendored `protoc`.
- Test environment: Linux, Python 3.13, offline. **No** Windows-native actual Lu-host authority, ANSF source verification, installed cross-app connector or GPU checks were performed.
- End-to-end offline demo uses a fully labeled **simulated host lease** and a synthetic structural fixture. Reproduction does not establish genuine source authenticity.

## Source and benchmark preservation

Original P2O, P2N and P2M behavior remains intact; this milestone is additive aside from descriptor registry/README changes. Earlier benchmark backlogs are preserved in the working checkpoint; P2P adds three deferred gates: real host security/revocation, longitudinal structural sources, and explicitly authorized cross-conversation linking. No deferred gate is marked passed or canceled.

## Next validation gates

The serious next step is actual Lu-native host-held source binding with revocation/deletion and publish synchronization (a separate authorized Lu development task). Independently sourced longitudinal correction records and full OWL/reference reasoner comparisons remain deferred. No package/CI/GitHub/Windows AppData changes were made.
