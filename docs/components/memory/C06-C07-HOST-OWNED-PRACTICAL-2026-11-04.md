# C06 + C07 practical foundation — Lu-owned ANSF memory and claim revisions

**Date:** 2026-11-04. **Status:** bounded Cognitum specialist implementation submitted; cross-platform verification and Lu host integration pending.

## Decision: only Lu owns canonical memory

Lu ANSF/SQLite is the sole owner of durable records, user identity, workspace access grants, revision chains, tombstones, consent, session truth and effect journaling. Cognitum does not own a competing persistent memory store, cannot initiate canonical mutations, cannot generate grants or claim user authority, and must not turn model hypotheses into verified facts. The string `Lu_ANSF` inside a typed snapshot is a claimed origin, **not** authentication. The real Lu host must supply the snapshot from its authenticated owner channel and independently enforce permissions.

### C06 — bounded retrieval

`cognitum/memory_derived.py` builds a **disposable in-memory** SQLite FTS5 derived index over a host-supplied `Snapshot`. Each `Evidence` has scope, source ID/revision, subject, bounded untrusted text, citation handle, validity interval and tombstone. Index construction accepts an explicit host-authorized scope, filtering out all other workspaces before indexing. Search performs parameter-bound FTS5 token matching, BM25 ranking, optional time/subject filtering, source-ID exact lookup and caller-requested max evidence count. Requests bind to snapshot ID and owner revision and fail on stale versions. Tombstoned evidence is excluded from both FTS and exact lookup; revised or deleted results only become visible after an explicitly rebuilt host snapshot.

No source content is executed; instruction-like text is returned solely as untrusted quoted evidence. `host_authorized_scope` supplied by a model must **not** substitute for a real host-issued grant. The index is rebuildable and not a second canonical store. No embedding models or HDC indexes are installed by default: a competent native FTS/BM25 incumbent comes first.

### C07 — typed proposed revisions only

`cognitum/belief_proposals.py` defines a typed `StateEvent` and `EventSnapshot` with source/authority type (`user_decision`, `imported_claim`, `model_hypothesis`), expected owner revision, event ID, entity, predicate, canonical scalar value, effective and recorded times, action (ASSERT, CONFIRM, CHALLENGE, SUPERSEDE, RETRACT, EXPIRE, MERGE), and exact target event for revisions. Deterministic event replay produces `Belief` views and explicit competing-claim notices without silently choosing a winner. The component refuses duplicate event identifiers, wrong workspace, stale owner revision, cross-subject edits, unknown target, invalid values and imported/model attempts to supersede or retract user decisions.

`propose` returns `HOST_COMMIT_REQUIRED` plus an SHA-256 digest of the proposed event. It **does not write, lock, reserve a transaction, grant authority, or advance the canonical revision**. The Lu host must independently authenticate actor authority, reject duplicate mutation IDs, commit a single atomic expected-revision append, and publish a new snapshot. Revision history, deletion and crash recovery remain under Lu's existing durable ANSF implementation. Claim status is a local interpretation of the supplied event record, not verified world truth.

### Native typed interfaces and acceptance

`proto/cognitum/memory/v1/host_owned.proto`, `cognitum/proto/host_owned_memory_pb2.py` and `cognitum/host_owned_memory_wire.py` expose canonical typed *read-only* Search and *proposal-only* Belief endpoints. They have strict frame caps, source-bound hashes, unknown-field refusal and recomputation of outputs from the request. The typed schema has **no mutation or host-authorization operation**.

`tests/test_c06_derived_memory.py` and `tests/test_c07_belief_proposals.py` exercise actual SQLite search, scoped exact lookup, stale revisions, index rebuild, tombstones, quote/query input, correction history, concurrent expected-revision conflict, competing assertions, challenge without automatic overwrite, retraction, and user-vs-model authority. `tests/test_c06_c07_wire.py` exercises genuine FTS through Protobuf, forged results, noncanonical frames, malformed input and cross-scope denial.

`.github/workflows/c06-c07-memory.yml` installs Protobuf and runs native FTS5 and compiled descriptor parity plus C06/C07 adversarial suites on **Windows/Linux Python 3.11/3.13**. CI success establishes component-level reference behavior, not that Lu's real authenticated ANSF host was exercised.

### Remaining host and task-level acceptance

1. Lu must supply a real authorized `Lu_ANSF` snapshot with atomic revision, tombstone and scope, not merely a caller-supplied string; validate worker permission scoping, lifetime and cancellation.
2. Host CAS/idempotency must commit proposals exactly once, with restart/recovery of interrupted writes and no partial cross-chat decisions.
3. Benchmark against Lu's existing retrieval, exact IDs, FTS/BM25 and graph/semantic indexes on independently held-out real tasks: citation correctness, current-revision accuracy, negative evidence, multi-hop recall, deletion leakage, privacy, p95 latency, and index rebuild costs.
4. Ensure previous answer history and corrected beliefs remain inspectable while revoked or deleted evidence is not redisplayed.
5. Keep C06/C07 specialist code independent from C17's predictive state-space analysis. Temporal forecasting is not canonical belief revision.

**No merge until required current-head native CI and applicable repository regressions pass.**
