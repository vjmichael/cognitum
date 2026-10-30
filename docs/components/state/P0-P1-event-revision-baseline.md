# C07 P0–P1 — Deterministic typed state and belief revision baseline

Date: 2026-10-27. **Code exists and passes offline unit tests; this is not Lu-integrated production memory.**

## Exact task

Given an authorized, persisted stream of user decisions, imported observations and model hypotheses, derive a deterministic current view that does not silently lose old revisions or treat a hypothesis as a verified user decision. Expose competing claims on the same subject/predicate when their typed values differ, rather than fabricate confidence or select a winner.

## Implemented

* `proto/cognitum/state/v1/events.proto` and `cognitum/proto/state_pb2.py`: native binary Protobuf StateEvent, SourceEvidence, ClaimView, ConflictEdge, StateProjection with explicit value kind, origin, action, scope, expected revision and snapshot/content provenance.
* `cognitum/state_revision.py`: bounded deterministic `StateLedger` with canonical Protobuf rejection, source-reference shape checks, event-ID idempotency, compare-and-swap claim revisions, append-only in-memory replay history, atomic batch publication, derived claim views, exact-value conflicts and terminal retraction/expiry.
* Tests cover stale revisions, duplicate IDs, unauthorized provenance promotions, challenge/confirm workflow, multiple conflicting claims, topic changes, chronology, bounded decoding, mixed-provenance history and source evidence shape.
* Independent `protoc` source-vs-checked-in-binding descriptor verification, alongside all existing Cognitum schemas.

## Deliberate semantics

`USER_VERIFIED`, `HOST_OBSERVED`, `IMPORT_OBSERVED`, `MODEL_HYPOTHESIS` are *provenance labels*, not measures of objective truth or grants. A model hypothesis or imported observation cannot confirm, supersede, expire or retract an existing user/host-confirmed claim. Model challenges mark dispute while preserving the original confirmed provenance and canonical evidence. Contradictions across separate claim IDs coexist as explicit ConflictEdges. User/host supersession creates a new immutable event and replays consistently; source edits elsewhere in ANSF must be rechecked by Lu before host admission.

## P0 research questions and baselines

* Recommended incumbent: exact event-sourced compare-and-swap reducer + Lu ANSF-backed source verification. Compare against latest-message-wins and a naive mutable dictionary in P3, scoring updates, contradiction handling, abstentions, latency, memory, and source revision correctness.
* Later: persistent Lu-owned event log, deletion/retention propagation, cross-session consent/authorization, typed value ontology, conflicting source evidence, time windows, hierarchical goals, and user-visible revision trails.
* SSM/HDC are challengers, not substitutes for authoritative provenance or exact state management.

## Open blocking gates

* This standalone reducer does **not authenticate** event provenance, grant authority, persist canonical claims, check source freshness, or provide a model-facing memory-write tool. A model can forge a `USER_VERIFIED` enum if the host fails to authenticate the origin; Lu must admit only verified events and resolve scope + C06 source reference under the read lease before treating output as trusted.
* The state view is *derived*, never a second authoritative memory store. No Rust/Windows native runtime test, no live Lu C06 read/write integration, no full deletion/purge integration, and no real Lu+model benchmark have run.
* No inference of semantic contradiction from text: conflict detection is exact typed-value inequality for an identical subject/predicate. It is a conservative baseline, not arbitrary commonsense belief resolution.
