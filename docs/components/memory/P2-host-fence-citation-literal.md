# C06 / P2 — Host-held publication fence, citation revalidation and literal baseline

**Date:** 2026-10-27  
**Delivery:** Offline Cognitum Python reference + native Protobuf contract extension. Not a Lu adapter, production authorization grant, installed CE, memory migration, nor a real-model benchmark.  
**Development home:** ChatGPT Library `/Cognitum/Development`; publish milestone snapshots to GitHub only on user's direction.

## Executable changes

1. `proto/cognitum/memory/v1/evidence.proto` adds `CitationLookup` and `CitationResolution` (native Protobuf), preserving all P1 field numbers. `cognitum/proto/memory_pb2.py` includes the corresponding descriptor-backed Python messages. Lookup is a **locator**, not a grant: source, digest, byte range, snapshot identifier and hash handle are all untrusted claims.
2. `cognitum/memory_host_gate.py` defines `HostMemoryGateway` / `HostHeldRead` host-injection protocols and `dispatch_host_fenced`. Each request acquires a host-controlled read lease, verifies candidate evidence or a citation, makes a **fresh** host-owned `recheck()`, and `publish()`es the typed result **synchronously under the same lease**. Its `DeliveryReceipt` never contains text, candidate hints or source content. A failed/revoked/deleted/stale/cancelled check replaces the *entire* earlier result with a status-only reply.
3. Citation expansion internally constructs a one-source P1 candidate, rechecks the canonical bytes, content hash, version, scope, deletion, historical policy and offsets, and computes the handle again. It uses constant-time handle comparison; possession of a handle is never authorization. A stale handle yields no evidence.
4. `cognitum/memory_literal.py` gives a deterministic, **case-sensitive exact substring** linear-scan comparator over a **host-injected synthetic snapshot**, generating native candidate hints only (source IDs, snapshot/scope IDs, full-text digest, bounded UTF-8-aligned excerpt ranges). It never writes another transcript database or SQLite index. The same P1 verifier remains the mandatory evidence gate. It is not semantic search, BM25/FTS5, or an accuracy improvement claim.
5. `tests/test_c06_host_gate.py` covers strict native Protobuf, revocation/generation/index/cancellation race overrides, deletion, tampered citations, Unicode offsets, exact-source filtering, null/indexed query failures, host exception concealment, fail-closed replies, 160 deterministic fuzzed inputs and synthetic lock serialization.

## Non-negotiable Lu integration conditions (still open)

The typed Python protocols **cannot authenticate a process or caller**. Any Python object can mimic them; tests use an explicitly synthetic mock. The eventual Lu-owned Rust host would have to implement these obligations before model/CE exposure:

- Bind each request to a host-authenticated local profile and active session membership; build `TrustedReadContext` itself. Do not accept the context, grant, source path, snapshot or session list from a model, index, provider, MCP boundary, or UI-supplied file path.
- Keep the authorizing grant, record-read consistency, current revision, deletion/tombstone state, and index/snapshot epoch fenced until *after* synchronous output publication. `recheck()` must consider revocation, cancellation, lease expiration, deletion, source generation, and ownership. A transaction/lock protocol must prevent revocation being acknowledged before an in-flight unauthorized publication, and publish must never queue bytes for a later, unlocked delivery. If publish fails, host must guarantee atomic non-publication.
- Reauthorize citation expansion in the **same way as original retrieval**; index membership or handle knowledge must not widen access. No persistent citation cache without an independent invalidation and scope policy. Never allow output of memory contents through logs, trace receipts or Python exceptions.
- Constrain canonical SQLite book ownership/path on the host side; do not treat a global ANSF catalog path or FTS hit as access authority. ANSF mutations, FTS invalidation, WAL/backups and deletion/retention semantics are Lu-owned and unresolved. The reference does not assert physical erasure.
- Constrain or prohibit historical revisions unless current host grants and the requested query explicitly allow them. Provenance must distinguish user-verified edits from imported/observed revisions.
- Gate any production model-facing CE/tool on resolved C02 security controls, C04 host collector integration, Lu-host security review and live end-to-end tests. Lu's repository was **not** modified by this checkpoint.

## Verified boundaries and next phase

Python Protobuf runtime and existing descriptor-vs-source sanity tests pass. Independent `protoc` comparison in this **local offline environment** remains pending because `grpcio-tools` is unavailable; the CI pipeline already knows to compare schemas when a future milestone is published.

A future P2/P3 integration must (1) implement the native Rust ANSF guarded read source on the Lu side, including cancellation/revocation/delete contract tests, (2) reuse existing ANSF FTS5/BM25 as the comparator, (3) measure real matched Lu+model trials under C03 versioned configuration, and (4) include privacy/purge/OS-host security acceptance. This P2 checkpoint advances self-contained, tested contracts and a small literal baseline only.
