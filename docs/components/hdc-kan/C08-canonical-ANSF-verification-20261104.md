# C08 — canonical ANSF candidate verification (2026-11-04)

## Implemented P2 reference boundary

The existing C08 BSC/HDC adapter computes *candidate identifiers* only. It is
not a fact store, a source of truth, or a tool permission system. The new
`cognitum/research/hdc_canonical.py` independent verifier:

- Requires an explicitly pinned host-provided snapshot identifier and revision.
- Decodes both request and candidate response with strict deterministic
  Protobuf parsing and rejects unknown or duplicate wire fields.
- Recomputes the HDC ranking and Hamming distances instead of trusting an
  arbitrary worker/model response.
- Resolves the latest canonical revision for each source before applying
  scope, tombstone, and relation matching.
- Rejects a prior source if its current revision was deleted, reassigned to
  another scope, or changed relation.
- Emits only **exact-matching authorized** source IDs, canonical revisions,
  and opaque host citation handles; no candidate is a citation by itself.
- Keeps false/approximate HDC matches out of the verified result.

## Lu ownership

Lu Rust ANSF/SQLite FTS5 is the canonical owner. PR #21 in Lu introduces a
host-authorized FTS5 read bridge for existing ANSF message revision chains.
The bridge is not yet a typed relation extraction API. Until a host-approved,
version-pinned and access-scoped `CanonicalRelation` snapshot provider is
available, this C08 implementation is an isolated reference component.

Cognitum must not parse arbitrary model text into "trusted relations", mint
permissions, create a second persistent canonical SQLite database, or
return HDC scores as if they established that a relation is factually true.

## Release gates still open

1. Verify the dedicated Windows/Linux Python 3.11/3.13 acceptance matrix,
   including existing C08/C09 regression compatibility.
2. Implement an actual Lu Rust authenticated canonical relation snapshot
   provider binding workspace/session access checks and current ANSF revisions
   to the C08 typed protocol, with crash/restart and stale snapshot negatives.
3. Initial synthetic 32-record BSC/canonical verification latency and false-positive/recall accounting is added in `tools/run_c08_candidate_benchmark.py`; still run full baselines against host FTS5/BM25 and exact relation lookup
   with held-out data, false positives, latency/memory and model task outcomes.
4. Verify through Lu's native model tool registry only after C02 policy
   authorization, host trust receipts and C06/C07 evidence semantics are
   accepted.

**Status: C08 candidate verification implemented; host integration and
production gates remain open.**
