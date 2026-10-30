# C07 P5 — Bitemporal historical state, bounded intervals and explicit uncertainty

**Status: implemented in Cognitum's offline Python/SQLite reference, 2026-10-27. Not authenticated by Lu and not enabled in a CE.**

## Two independent clocks

`cognitum.state.v1.AsOfQuery` carries `valid_at_ms` (when the assertion is claimed to hold) and `known_at_ms` (cutoff for events actually recorded). `HistoricalProjection.historical_only = true` is *mandatory*. These are **historical interpretations of retained evidence**, not current state or the truth of a statement. We don't force `valid_at_ms <= known_at_ms`: a source can express future effective dates. A historical query cannot be used to request a tool grant or to establish current beliefs.

`ASSERT` and `SUPERSEDE` create claim-value segments; their `valid_until_ms` is an **exclusive** positive end bound or zero for open-ended. A newer `SUPERSEDE` selects a newer segment from its effective timestamp, but the old segment remains queryable at earlier effective times. `CHALLENGE`, `CONFIRM`, `RETRACT` and `EXPIRE` affect status only from the marker's effective timestamp; their recording cutoff independently determines when that change was known. `TEMPORAL_CORRECT` must still name the immediately preceding event, satisfy host-reviewed provenance/CAS and can explicitly change a segment start and (if provided) its end; no old event bytes are modified. An omitted end on a correction inherits the previous end—**clearing an existing bound is not currently supported**. Overlapping *different* claims remain separate with explicit conflict edges when both are active at the requested time; no winner is inferred.

The reducer's ordinary `StateProjection` remains event-derived and **does not auto-expire against wall-clock time**. Use the bitemporal query for time-valid views, and never silently feed a historical projection to the model as current memory.

## Uncertainty is declared, not scored

`UncertaintyKind` is `UNCERTAINTY_UNSPECIFIED`, `EXPLICITLY_UNCERTAIN`, `CONDITIONAL`, or `OPEN_QUESTION`. The enum is not an ordinal confidence score. **Unspecified does not mean certain**. Non-default labels require a short, nonempty note supplied by the source event and retained in the immutable Protobuf history. Only value assertions (`ASSERT`, `SUPERSEDE`) can establish or change that label. `CONFIRM`, `CHALLENGE`, retraction, expiry, and temporal correction retain the prior qualifier; neither a model challenge nor a host observation can silently transform a source's uncertainty into an implied certainty. Qualifier text is untrusted data and must not be executed or treated as instructions.

## Fenced disclosure and deletion

Offline diagnostics: `project_as_of(ledger, query)` is intentionally refused for host-only ledgers and provides **no authorization**. Production-shaped API: `StateLedger.publish_host_as_of` and `StateJournal.publish_host_as_of` freeze/validate the Protobuf query and publish only synchronously under an **already-held Lu host lease**. Before disclosure they recheck *every* retained source in the journal, even events outside the recording cutoff, and recheck lease liveness. A deleted ancestor, revoked principal, changed snapshot or denied evidence stops publication. Historical evidence checks use `require_current=False` to allow legitimate superseded-but-retained historical revisions; **this is not a current-state grant**. The journal also holds a SQLite transaction through reconstruction and publication; the host lease, not SQLite alone, must synchronize ANSF modification/deletion and revocation. No raw credentials or model-generated IDs count as a lease.

`StateJournal` replays the same canonical event wire bytes after restart. The C07 journal stays a **rebuildable derived cache**; Lu ANSF alone owns canonical session memory. P4's source-deletion reconciliation removes affected claim histories; P5 historical disclosure fails closed if such reconciliation has not happened. P4's retired-ID/generation rules still apply. SQLite journal logical deletion is **not** physical erasure of WAL/free pages, backups or canonical ANSF.

## Remaining gates and acceptance evidence

`tests/test_c07_p5_bitemporal_uncertainty.py` covers two clocks, exclusive boundaries and gaps, superseded historical values, temporal backdating, corrections to end bounds, marker/status transitions, uncertainty preservation and malformed qualifiers, conflict overlap, replay, restart, scope isolation, stale/revoked/deleted evidence, and reentrancy. Independent `protoc` checks compare all ten `.proto` source descriptors to the checked-in Python bindings. Results are recorded in `P5-test-evidence.json` (not a Windows Rust or live-model benchmark).

**Still required before production:** native Lu authenticated host/read lease; Rust compilation and Windows x86-64 integration; proper physical derived-cache purge/retention policy; all ANSF write/import and deletion paths fenced; live Lu+model memory-accuracy and resource benchmarks; anti-rollback/durable keying if trusted threat model requires it. Do not advertise C07 as a production memory authority until these are met.
