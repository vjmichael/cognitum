# C07 P3 — Crash-safe derived event replay and canonical-source reconciliation

**2026-10-27 · Offline implementation, NOT Lu deployment or real-model P3 promotion**

## Implementation

`cognitum/state_journal.py` implements a *rebuildable* local SQLite log for C07 typed `StateEvent` frames. It does not store ANSF messages, create user grants, authenticate a principal or replace the Lu-owned ANSF session books. A host has to authorize **every admission** under a held memory mutation lease. The log is not authority: belief/goal state is a projection reconstructed from canonical, scoped, source-referenced events.

Each `apply_host_batch` uses SQLite `BEGIN IMMEDIATE`, loads and validates the latest committed event stream, runs the existing C07 compare-and-swap event reducer and Lu-host **synthetic** source-check protocol, then writes newly admitted canonical Protobuf frames with a sequence/hash chain and advances the journal head **in the same transaction**. Failed authorization, stale revision, disk exception or failed head update rolls back the entire batch. Exact duplicate event IDs do not append another row. Independent SQLite connections serialize via write locks so two stale concurrent revisions cannot both commit. The active SQLite connection is configured for WAL and `synchronous=FULL` (subject to operating-system/filesystem guarantees).

A journal opens only for its immutable scope identity. On each restart or read, it verifies all event ordinals, per-frame canonical bytes, event IDs, SHA-256 chain, metadata head and deterministic reducer transitions. Corrupt/incomplete logs fail closed. The hashes detect accidental damage or unsynchronized changes; **unkeyed hashes do not stop a malicious actor who can rewrite the SQLite database or roll back the entire file**. Production Lu must use protected directories, capability-based filesystem access, authenticated user turns and anti-rollback state where needed.

`publish_host_fenced` and `reconcile_host_fenced` rebuild the projection inside an acquired journal write lease and require the **external Lu host lease** to verify every retained historical ANSF evidence reference and every active/current claim before publication. A different/current revision is allowed to supersede a retained ancestor; deletion of an ancestor, missing canonical bytes, changed snapshot, revoked permission, or stale active head denies publication. `reconcile_host_fenced` returns **only** event count and SHA-256 metadata from one SQLite snapshot, not original claim content. Nothing records a reusable authorized/verified flag: the next read must recheck.

### Deliberate non-goals and production caveats

- C07 reference events are **derived, rebuildable** data. They do contain bounded derived claim values, potentially sensitive; Lu must own retention, access control, safe erase, encrypted backup policy and rebuilding after ANSF deletion. This milestone does **not** physically purge values in SQLite, WAL, backups or snapshots.
- SQLite locks only serialize **C07 journal writers**. ANSF edits/deletes/revocations reside outside this SQLite file, and require Lu to hold and synchronize the **native** lease across evidence checks **and actual delivery**. A Python fake lease is never authentication.
- This is Python 3.11+ reference, NOT compiled Rust, a native Protobuf worker/CE, a model hook, or Windows end-to-end test. P3 **offline** replay slice is implemented; the real Lu+model comparative P3 validation gate remains open.
- The replay chain is not a globally ordered Lamport clock. It protects local deterministic CAS chronology and immutable event IDs, but merging independently authenticated device logs would require an explicit host merge protocol, additional ordering and conflict decisions.
- The SQLite file is an optional derived cache; if retention or correctness cannot be demonstrated, Lu must fail closed or rebuild under valid host authority, **not** trust this cache over the ANSF source.

## Executable acceptance

`tests/test_c07_journal_p3.py` checks crash/restart and source-lease behavior: exact replay, historical evidence retention, source snapshot drift and deletion, revoked access, concurrent independent connections, stale CAS, injected event/header write failures, uncommitted write rollback, corrupt event bytes/head/unknown protobuf fields, scope binding, failed reentrant callbacks and held-lease publication ordering.

`tools/benchmark_c07_p3.py` creates a deterministic synthetic fixture and measures a naive latest-write-wins dictionary (insecure/non-equivalent), pure C07 reducer and SQLite commit+restart+host-mock publication. The naive algorithm incorrectly overwrites with a stale write; C07 rejects it and preserves conflicting claims. The reported timing is **local diagnostic wall-clock only**, not normalized throughput or an efficacy comparison, and **no Lu model** runs. Full benchmark source and environment appear in `P3-test-evidence.json`.

## Remaining gates

1. Lu Rust C06 P11 native build/test on Windows x86-64; real authenticated memory mutation and revocation/deletion lease; cover all ANSF writers and source imports. No user-provided lease object may authorize model actions.
2. Native Lu adapter for C07 authorized append/replay publication. Rebuildable SQLite derived cache must be placed inside a host-protected directory with safe purge and migration controls. Close cache when scope is destroyed and enforce quotas.
3. Run C03 pinned real-Lu+model evaluation: compare naive chronological memory, verified C07 replay, and any HDC/KAN derived ranking under matched prompts, source citations, goal-change correctness, contradiction false positives, latency/RAM/storage cost and failures. Synthetic dictionary timing **cannot substitute**.
