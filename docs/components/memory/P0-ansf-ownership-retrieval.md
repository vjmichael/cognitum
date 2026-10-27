# C06 / P0 — ANSF-backed canonical memory and retrieval ownership audit

**Date:** 2026-10-27  
**Phase:** P0 in progress; design and read-only source audit, not a shipped memory component  
**Cognitum base:** main at 62101f2fa350d3c8c7e779797cc609e4408c7ad0  
**Lu inspection:** vjmichael/jan_alt branch lu/ce-broker-revocation-fence (moving reference, independently pinned by the referenced source files at review time). Lu repository is read-only in this effort.

## 1. Concrete Lu+transformer task and falsifiable claim

The loaded transformer should answer a user's cross-chat factual question from **authorized current source evidence**, distinguish historical/superseded text, and cite the originating exact passage. Examples include: “What did I decide most recently about native Protobuf?”, “Which project had a different decision?”, or “What did I say before correcting it?”. The model remains responsible for understanding the question; retrieval does not make the claim true or confer any tool permission.

Hypothesis for C03 P3: Lu + C06 evidence selection can improve citation correctness and current-revision answer quality relative to (A) Lu alone and (B) Lu's existing ANSF exact lookup/FTS5-BM25, on held-out real or consented synthetic tasks. Compare (C) Cognitum-derived retrieval and (D) an independently justified composition only after it actually exists. No accuracy, recall or cost benefit is asserted here.

## 2. Ownership decision: reuse Lu rather than fork a ledger

**P0 recommendation requiring Lu-owner confirmation:** Lu-host-owned ANSF conversation books and its global ANSF library are the canonical transcript and revision source. Cognitum may receive Lu-authorized, bounded read-only evidence and build **disposable derived indexes only** after security and reconciliation gates are approved. No Cognitum-authored canonical user-memory SQLite DB, duplicate ANSF writers, independent identity database, model-visible memory tool or independent LLM loop.

Verified from Lu's active branch (read-only):
- [ansf.rs](https://github.com/vjmichael/jan_alt/blob/lu/ce-broker-revocation-fence/src-tauri/lu-core/src/ansf.rs) holds SQLite session/chapter/entry records, host-supplied IDs, immutable original messages, FTS5 and cursor pagination. The module itself warns that callers must authenticate ownership.
- [ansf_revisions.rs](https://github.com/vjmichael/jan_alt/blob/lu/ce-broker-revocation-fence/src-tauri/lu-core/src/ansf_revisions.rs) appends immutable revisions, resolves current_message and distinguishes verified user edits from later discovered imported changes. An observed import timestamp is **not** proof of when the human made the edit.
- [ansf_library.rs](https://github.com/vjmichael/jan_alt/blob/lu/ce-broker-revocation-fence/src-tauri/lu-core/src/ansf_library.rs) stores a global index of books and chapter summaries, **not copies of messages**, and requires host authentication and path confinement before following source references.
- [ansf_sync.rs](https://github.com/vjmichael/jan_alt/blob/lu/ce-broker-revocation-fence/src-tauri/lu-core/src/ansf_sync.rs) reconciles non-atomic book/catalog writes through replay; catalog membership is not a grant.
- [luMemorySync.ts](https://github.com/vjmichael/jan_alt/blob/lu/ce-broker-revocation-fence/web-app/src/lib/luMemorySync.ts) exposes explicit desktop manual sync, inspection and human checkpoint operations. These are **not model-callable**. A UI call taking a thread ID is not itself sufficient authority for a CE.
- [MEMORY_AND_MEDIA_ROADMAP](https://github.com/vjmichael/jan_alt/blob/lu/ce-broker-revocation-fence/src-tauri/lu-core/MEMORY_AND_MEDIA_ROADMAP.md) explicitly leaves host-authenticated ownership, retention/purge, semantic memory, context relevance and model/tool retrieval APIs incomplete. Do not assume these are production services.

Canonical identities must remain **host-issued**: profile/owner, conversation/session, chapter, original message and immutable entry/revision. An index candidate is merely a hint; the Lu host must confirm current ownership, active revision, deletion status and exact source content **at read time**, not at index-build time. A stale catalog cannot prove access.

**Not decided:** ANSF storage root/profile enrollment ABI, actual CE read grant model, whether workspace documents get an independent Lu-authorized canonical owner, deletion policy including source revisions/backups and secure storage, which Lu host service exposes authenticated read-only snapshots, and snapshot/version guarantees. Until approved, C06 is NOT authorized to read real ANSF files or persist user-derived content.

## 3. Proposed native Protobuf contract (not yet implemented)

All fields below are conceptual **typed message fields**, not JSON exchanged between Lu and Cognitum. Host-only authorization metadata is **not** a model argument, and no caller-created user/session identity authorizes a read.

| Proposed message | Semantics / mandatory checks |
| --- | --- |
| MemoryQuery | request_id; optional host-issued opaque scope token; literal bounded query (1–256 UTF-8 bytes); optional immutable source references and time range; 1–20 evidence limit; fixed query/snapshot schema revisions. No arbitrary SQL, filesystem paths, wildcards, grants or executable filters |
| MemoryEvidence | opaque source locator (session + chapter + original entry + selected revision), current vs historic flag, canonical source digest, optional valid/effective timestamps, bounded excerpt, source revision, scope-bound citation handle and provenance/assurance. No privilege or trusted instruction embedded in excerpt |
| RetrievalReply | oneof verified evidence batch / typed error (DENIED, UNAVAILABLE, STALE, DELETED, INVALID, LIMIT, UNSUPPORTED); never return a partial unauthorized batch |
| IndexStatus | canonical snapshot ID/revision, derived-index revision, reconciliation state and explicit STALE/REBUILD_REQUIRED status; never treated as a source record or a permission grant |
| MutationProposal (deferred) | host-review-only proposal with expected canonical revision and idempotency key; **not** a writer or executable action. Actual C07 mutations remain with Lu-authorized writer after explicit approval |

A future native Lu adapter may use fixed generated Protobuf request/result type URLs, a strict versioned schema, deterministic serialization where required, type/size/presence validation, bounded batch frame (< Lu's current wire budget), and explicit semantic checks. Provider-facing JSON appears only at the external transformer boundary if Lu elects to advertise an approved operation. **There is presently no C06 CE, registry entry, model tool or executable handler.**

First implementation candidate after approval: a deterministic **read-only source-reference verifier** with injected host-authorized snapshot fixtures. It can check a returned candidate's scope, current revision, source digest and deletion marker against a trusted host-supplied record; it must never open database paths or decide identity itself. Actual disk retrieval belongs in a separate Lu-owned adapter with demonstrated authorization.

## 4. Source correctness and lifecycle rules

1. Resolve from an authenticated host-controlled canonical snapshot. Reject missing/ambiguous ownership and scopes; never widen from a conversation to a profile or workspace because a query asks.
2. Prefer exact source-ID lookup for explicit references. Run scoped lexical FTS5/BM25 against Lu's existing index for textual candidates. Normalize user phrases into literal FTS arguments, not caller-provided FTS query syntax; parameterized SQL is necessary but **not** sufficient to contain FTS operators.
3. Recheck each candidate against the current authorized ANSF record and revision before disclosure. Historical revisions must be explicitly labeled; default answer-oriented lookup should not return a superseded revision as current.
4. Citations bind a stable opaque source locator, selected revision, and source-content digest. The host resolves citations and must deny stale/forbidden handles rather than reuse cached excerpts.
5. Deletion/revocation/tombstone takes effect **before response assembly**. Invalidate every cached excerpt, derived index entry, binary vector, trace and cross-session projection for that source; no stale candidate can bypass source recheck. Full physical erasure from immutable ANSF revisions, FTS segments, WAL, backups and artifacts is **not yet specified or validated** by Lu.
6. Restart/reindex after a partial book/catalog update must return STALE or UNAVAILABLE rather than claim a complete index. Derived indexes must be rebuildable without creating new facts.
7. Retrieved chat, documents and “system”-styled text are **untrusted evidence**. They cannot create tasks, rewrite grants, dispatch tools or override host policy.
8. Disabled Cognitum, unsupported schema, untrusted collector or blocked C02 worker returns explicit unavailable/denied; Lu's existing memory remains intact.

## 5. Mature baselines, standards, dependencies and tradeoffs

| Candidate | Immediate role | Cost/security and maintenance judgment |
| --- | --- | --- |
| Existing Lu ANSF via Rust rusqlite, SQLite and FTS5 | **Incumbent and probable canonical owner**. Exact IDs, WAL, indexed lexical retrieval, BM25, immutable revision history | Reuse instead of parallel SQLite; current ownership and deletion lifecycle still need hardening |
| SQLite FTS5 unicode61 / BM25, existing global catalog | Lexical baseline with configurable tokenization and rank | Evaluate homonyms/phrases/diacritics, FTS query injection, stale external-content index, tokenization compatibility, secure deletion and rebuild behavior |
| Python stdlib sqlite3 against *synthetic fixtures only* | Offline P2 differential control for ranking/transaction/recovery | Not an authorized connector to Lu's ANSF and should never get arbitrary host paths |
| Dense embeddings or binary-quantized candidates + exact rerank | Optional **derived** index challenger after real baseline | Model download/license, cold-start, extra disk/RAM and stale embeddings; never canonical facts; no claimed recall win |
| HDC C08 | Later typed relational challenger | Requires canonical C06/C07 revisions, false-hit measurements and negative archived baseline preservation |
| SQLite vec1 / other native ANN extension | Study later if retrieval scale warrants | Additional binary/runtime and portability review; no dependency until measured and approved |

Sources: [SQLite FTS5 and BM25](https://www.sqlite.org/fts5.html), including lexical query syntax, external-content consistency, integrity-check, and separate FTS/core secure-delete controls; [SQLite WAL](https://www.sqlite.org/wal.html); [SQLite transaction semantics](https://www.sqlite.org/lang_transaction.html); [Protobuf field presence](https://protobuf.dev/programming-guides/field_presence/); [SQLite vec1 extension](https://sqlite.org/vec1.html). These document capabilities, **not** proof of Cognitum's future production setup, license compatibility or deletion compliance. At P1 lock the deployed SQLite version/build flags and full dependency/license inventory (SQLite is public domain; rusqlite and optional ANN/binary packages require their own direct review).

## 6. Hardware selection and measurement

| Backend | P0 disposition | Reason |
| --- | --- | --- |
| CPU + local SSD, SQLite FTS5 | **Reference incumbent** | Small/medium ANSF corpora, transactional consistency, predictable install and no GPU contention with Lu's transformer |
| CPU SIMD binarized retrieval | Optional derived candidate | Measure encode/index build, candidate recall and exact rerank cost; confirm relevant instruction availability |
| GPU embedding/batch rerank | Later opt-in experiment | Only if batch/corpus throughput offsets VRAM residency, transfer, power, model startup and contention |
| FPGA/NPU/ASIC | Research only | No hardware access or measured task-scale advantage; not a P1 prerequisite |

Device selection is a workload/result, not a general claim. Offline, non-network operation is the default; recording an index should not trigger hidden cloud embedding APIs.

## 7. P2 negative gates and P3 preregistration

**Functional test matrix (synthetic, no user data):** exact passage with same-name collisions; source ID lookup; cross-conversation same phrase; cross-profile denial; wrong scope/token, revoked grant, guessed session ID and malicious retrieved instructions; previous/current edited wording, observed-import date distinction and stale snapshot; deletion across FTS, HDC-style cache, embeddings and quotation cache; restart between book and library updates; injected corrupt FTS metadata; oversized query/results and adversarial FTS operators; idempotent reindex; unavailable host/CE; inspect historical quote only when explicitly authorized. Failure means **no unauthorized bytes** in success/error payload, logs or citation expansion.

**P3 frozen controls:** A Lu+model only; B Lu+model with existing exact ANSF + FTS5/BM25; C Lu+model with one approved C06 improvement; D bounded composition only when real. Run matched selected model/backend/quantization, tool budget, seeds and contexts using the C03 plan/capture and C04 signed collector gates when available. Measure Recall@k and MRR **plus** evidence citation validity, present-decision accuracy, temporal revision fidelity, false current-claim rate, denied/deleted leakage, explicit abstention, p50/p95 wall latency, memory/VRAM/storage/energy where measured, reindex duration and whole-answer grading. Freeze train/dev/held-out splits and tokenization controls first; benchmark on consented or fully synthetic corpora, avoid identifiable raw-text CI fixtures. Do not call synthetic passage retrieval a model P3 success.

**Hard-stop gates:** no read until Lu-specific host identity, scope and per-candidate source recheck exist; zero tolerance for cross-owner/deleted-content leakage; no mutation without trusted writer/consent; no C02 isolated worker claims absent OS proof; no data exfiltration across read-only CE or provider-edge boundaries. No backdoor generic JSON handler.

## 8. Decisions and next deliverables

**Recorded Cognitum architectural recommendation:** C06 will integrate as a read-only, typed **derived retrieval service over Lu-owned ANSF**, not as a competing memory manager. Formal Lu approval, source-read protocol and retention behavior are **OPEN**. This P0 source audit and test plan are real deliverables; P0 exit is not claimed while permissions, deletion semantics, dependency/license audit and test fixtures remain unapproved.

Next: in a separate narrow C06 P1 slice, build an **inert Protobuf evidence-reference contract with strict validator + synthetic fixture tests only**, no ANSF files or service access. Then request a Lu-owned read-only snapshot/authorization adapter under the proposed addendum; do not wire a model tool or activate Cognitum memory until host C02/C04 gates close.

**Status:** P0 started; no new executable C06 code, benchmark, Lu change or access to personal memory.
