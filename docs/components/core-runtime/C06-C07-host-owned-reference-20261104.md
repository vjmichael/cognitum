# C06/C07 host-owned reference checkpoint — 2026-11-04

## Implemented on PR #78

- C06 `memory_retrieval.py`: host-provided ANSF canonical snapshot input,
  exact-scope and temporal checks, bounded latest-revision processing,
  tombstone and scope-change suppression, query-literalization and ephemeral
  SQLite FTS5/BM25 ranking; exact-token comparator for deterministic controls.
  FTS5 indexes are ephemeral derived structures, **not** competing memory
  stores and **not** asserted to be connected to Lu's actual ANSF database.
- C07 `state_revision.py`: deterministic typed scalar (string/int64/bool)
  event replay with origin separation, expected revisions, idempotency,
  challenge/conflict provenance, supersession, retraction, expiration and
  fail-closed transitions.
- C07 `host_event_adapter.py`: injected host SQLite connection, required
  host authorization callback, `BEGIN IMMEDIATE` atomic append, canonical
  SHA256 payload digests, optimistic revision conflicts and persisted replay.
  Its isolated `HOST_TEST_SCHEMA` is a **reference test schema only**:
  production must use existing Lu ANSF/effect-journal schema.
- `proto/cognitum/memory/v1/memory_state.proto` and
  `memory_state_wire.py`: versioned typed native messages, snapshot pins,
  host scope matching, canonical deterministic encoding and unknown/duplicate
  field rejection, bounded payloads, presence-aware scalar union.
- Dedicated C06/C07 acceptance workflow tests genuine SQLite FTS5 and
  durability on Windows/Linux Python 3.11/3.13, native Proto descriptor
  compiler parity and adversarial boundary cases.

## Non-negotiable trust boundary

Lu remains the sole authority for canonical SQLite/ANSF data, identity,
scope, authorization and effect journaling. Cognitum must **never** mint
host grants or import its reference test table as a production canonical
store. Host authorization precedes all state writes; the event's opaque
`actor_authority` text is not a capability. C06 query scope checks remain
defense in depth and cannot replace host-enforced filtering.

## Remaining engineering gates (NOT completed)

1. Port the host adapter to real Lu ANSF read/snapshot and durable
   transaction APIs; prove cancellation/recovery, concurrent writers,
   restart, tombstone compaction and scope-reassignment safety.
2. Add host-side cryptographic/opaque validated authorization receipt
   at the Lu native boundary and negative OS-process boundary tests.
3. Implement a refreshable derived FTS5/BM25 index with canonical revision
   reconciliation and permission-filtered persistent host reads; benchmark
   end-answer accuracy and index update costs against direct exact lookup.
4. Confirm real Protobuf tool dispatch by Lu with request/result/effect
   journals, and independent decoded-result revalidation where applicable.
5. Human policy for consequential merge/conflict revision and cross-chat
   consistency reconciler; provenance-rich belief views with effective
   validity intervals and negative evidence.
6. Run real matched Lu model tasks and independently measured memory,
   latency, power/energy if available, correctness and ablation baselines.

**No C06/C07 production or Lu integration gate is claimed closed.** CI
green alone means the isolated reference acceptance passes, not deployment.
