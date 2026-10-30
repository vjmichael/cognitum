# C15 T2 P2P — C07-linked structural evidence (research contract)

## Purpose

P2O can replay multiple structural hypotheses and explicitly retire caller claims, but its labels and sources are not authenticated. C07 already implements a typed, revisioned, source-aware *derived* belief projection. P2P builds an additive, read-only bridge so an authenticated host can correlate those two independent audit logs **without** allowing a P2O hypothesis to write C07 or become a physical-world fact.

This reference implementation cannot authenticate anything itself. Lu is **not modified**. An actual Lu native host would need to acquire/hold a lease under its own Windows OS and ANSF trust boundaries; **never** accept a Python `HostT2C07Lease` object from an LLM, external worker, document, MCP server, or frontend.

## Contract

- `proto/cognitum/spatial/v1/structural_c07_bridge.proto`: P2O request + canonical C07 event bytes; output contains the unchanged P2O audit and C07-linked event/claim summaries.
- `cognitum/spatial_structural_c07_bridge.py`: finite `publish_host_fenced` reference call. It calls the existing C07 `StateLedger` reducer in a disposable in-memory projection, requires strict `True` for `ensure_active`, `admit_event`, `verify_source` for every historical source and every currently active/disputed source, and `bind_structural_event` for every matched P2O change.
- Caller-supplied event bytes, source names, origin labels, hash receipts, `research_only`, and `grants_authority` **never constitute a credential**; the actual host verifies action provenance and bound source/current revision. Source deletion or revocation denies publication. A successful result is **not permission to write anything**.
- Each P2O event ID is paired with an identical C07 event ID. The C07 claim ID is the P2O claim ID (unique across all candidates in this bridge), C07 subject is the candidate, C07 predicate is `spatial.<claim_id>` and C07 TEXT is SHA-256 of the deterministic Protobuf type/edge payload. Retraction refers to the identical C07 claim ID and original payload. The host must additionally verify source and meaning via `bind_structural_event`; simple matching hashes and IDs alone are not sufficient.
- Extra C07 CHALLENGE, CONFIRM, EXPIRE, and TEMPORAL_CORRECT events may appear in the same ledger, but are **not** interpreted as structural changes. P2O may not silently supersede an earlier structural addition. Rejected: missing binding, duplicate event, foreign scope, malformed wire, payload mismatch, stale C07 revision, host refusal, and a second candidate reusing the same global C07 claim ID.
- C07 uncertainty/origin/status are reported separately from P2O's current hypothesis state. DISPUTED/EXPIRED labels, lower-provenance origins or explicit uncertainty cause `requires_review`; they do **not** retract or promote a structural hypothesis.
- P2P v1 rejects cross-conversation evidence imports. It requires the same scope/active conversation ID for the P2O journal and C07 ledger. Linking other conversations needs a separate, explicit Lu-host-verifiable read/consent/scope contract in the future.
- Bounded to 512 C07 canonical event frames, P2O's own eight candidates and 128 events, and 1.4 MB total request. No external model/worker, file I/O, persistent database, network access, geometry, or scene mutation.

## Limitations

This is **integration-interface readiness**, not real Lu trust integration. Synthetic host leases used by tests are *mocks*, not security validations. SHA-256 digests and source references provide audit consistency, **not** source authenticity. C07's state cache remains derived; Lu ANSF would be the canonical source if integrated. No canonical C07 event or structural source is authored by this adapter, no forced winner is chosen, and inherited structural types remain uncertain hypotheses. No new real-world performance or OWL 2 results were measured.

## Tests and next gate

Run `PYTHONPATH=. python -m pytest -q tests/test_c15_t2_p2p_c07_bridge.py`, `PYTHONPATH=. python tools/verify_protobuf_schemas.py --require`, then the C07 and C15 regressions. Deferred host integration should verify actual source ownership/revision, deletion/revocation across the callback, concurrent host fencing and Windows-native worker isolation; real longitudinal structural evidence and independent ontology semantics remain open.
