# C06/P1 — Offline Protobuf Memory Evidence Verification

**Date:** 2026-10-27  
**Development location:** ChatGPT Library `/Cognitum/Development` (versioned ZIP checkpoints; GitHub milestones only on request)  
**Status:** Executable bounded **synthetic reference**, NOT Lu-integrated read access or host-approved CE.

## Delivered

- `proto/cognitum/memory/v1/evidence.proto`: source reference, literal query, index candidate, host snapshot, canonical record, typed result status, citation and current/historical revision schemas. There is **no arbitrary JSON**, `Any` request, SQL, path, permission token, model-facing tool registration or mutation operation.
- `cognitum/proto/memory_pb2.py`: matching descriptor-backed native Protobuf Python message implementation. Existing CI schema comparison now includes this ninth schema; **local independent compiler verification awaits `grpcio-tools` availability**.
- `cognitum/memory_evidence.py`: pure deterministic offline candidate verifier with explicit host-injected synthetic snapshot and `TrustedReadContext`. Frames are strictly bounded and canonicalized; unknown fields/noncanonical binary are rejected. Each candidate must match the host-supplied scope, authorized session, snapshot/index/authorization epochs, live undeleted record, current revision or expressly permitted historical revision, and exact full-record SHA-256. UTF-8 excerpt bytes come only from canonical host text. A failed candidate invalidates the entire batch, not just its own result; no rejected excerpt is echoed in replies.
- `tests/test_c06_memory_evidence.py`: 17 adversarial synthetic unit tests for scope guessing, revocation, deletion, stale catalog/snapshot/revision, historical grants, corrupted digest, unknown fields, duplicate entries, size ceilings, Unicode boundaries, synthetic prompt injection, canonical citation and no-partial-leak responses.

## Invocation and security boundary

```
query_frame       -> MemoryQuery (untrusted caller; no identity/grant fields)
index_frame       -> CandidateBatch (untrusted derived index; NO text payload)
host_snapshot     -> CanonicalSnapshot (host-authorized data in synthetic tests)
trusted_context   -> TrustedReadContext (host-bound injection, NOT user/model input)
                     | strict checks |
                     v
                    RetrievalReply (VERIFIED / DENIED / UNAVAILABLE /
                                    STALE / DELETED / INVALID / LIMIT / UNSUPPORTED)
```

A constructed `TrustedReadContext` or serialized `CanonicalSnapshot` is **not cryptographic host authentication**. These are injected synthetic test fixtures until Lu supplies a real authenticated read grant, authoritative source snapshots, lock/epoch-bound rechecks and effective revocation/deletion policy. Only the eventual Lu host may establish that provenance. A citation handle is a stable non-secret **locator**, not a bearer credential: the Lu host must reauthorize each citation expansion using current ownership, revision, deletion and digest. This reference verifier does **not** prevent a host from using stale context; the real host must recheck immediately before delivery, including concurrent revocation. It makes no secure deletion claims for ANSF/FTS/WAL/backups.

`CanonicalSnapshot.records` are bounded to 64 records, each canonical text to 16 KiB; untrusted candidate frames to 16 KiB / 64 candidates, queries to 4 KiB, returned excerpts to 1024 UTF-8 bytes each and replies to 32 KiB; requests allow at most 20 evidence results. Query terms remain **literal opaque strings** in this slice: there is **no lexical search, semantic indexing or ranking** and no query execution, so this isn't a recall improvement demonstration. Candidate order is preserved. Historical revisions require both an explicit request flag and an independent host-context allowance. Cross-session/profile denial and deletion are hard failures with empty evidence arrays.

## Validation evidence / constraints

Run in an extracted repository root:

```
PYTHONPATH="$PWD" python -m unittest discover -s tests -p 'test_*.py' -q
PYTHONPATH="$PWD" python -m cognitum --calculator replay evals/smoke.json
PYTHONPATH="$PWD" python tools/run_c03_smoke.py --check
python -m compileall -q cognitum tests
```

The CLI script path requires PYTHONPATH or an editable package installation. `grpcio-tools` is not present in the current offline execution container, so independent `protoc` source/binding comparison is **pending** here. The existing GitHub CI workflow includes the ninth schema compiler check for **a future user-requested milestone push**, but this Library checkpoint is not represented as having passed it.

## Next decisions / exit gates

1. **Lu-owned authority:** approve memory profile/session grant semantics, concurrent revocation and host snapshot read locking, epoch capture, current revisions and canonical text digests. Reject arbitrary `CanonicalSnapshot` from any model, UI field, CE or provider.
2. **Lu-owned deletion lifecycle:** define tombstone semantics, imported historical edits, FTS cache invalidation, and removal from WAL/backup derived stores; this Python reference can only reject host-declared deletion.
3. **P2 host adapter in a separate gated change:** implement native authorized read-only snapshot ABI in Lu's own Rust host, scope fence, path confinement, final source recheck and cancellation; do **not** link this reference verifier directly to ANSF disk. Block CE/model tool advertising until C02/C04 host security gates close.
4. **P3:** compare Lu+model only, existing ANSF FTS5/BM25, and eventual verified C06 derived retrieval on the preregistered C03 plan with real host receipts. **No P3 model benchmark has been run.**

This is a narrow P1 implementation, **not** completion of C06 or production memory.
