# C07 P9 — Host-bound multi-turn context resolution

**Status:** offline Python/Protobuf reference implemented; local synthetic unit/smoke tests only; not integrated or authenticated in Lu.

## Why this matters

C07 P8 classifies explicit language but previously used a caller-supplied `prior_decision` string. That string is not proof the user made or still holds a decision. P9 adds a typed, bounded `ContextWindow` in the existing `cognitum.state.v1` Protobuf schema. It contains a canonical-turn selector, up to 16 candidate claim anchors, and an optional exact claim selector. An untrusted model, webview, or document can still suggest fields, but **no field authorizes a memory mutation or target binding**.

`resolve_host_fenced` refuses unverified source, foreign scope, unknown/duplicate claim ID, inactive anchor, invalid revision/digest, noncanonical wire encoding, and an embedded `prior_decision`/`subject_hint`. It calls a trusted host lease in order: check active; verify persisted speaker, turn and original text; verify every active current anchor and its ANSF source; separately verify the *relationship* between the user's current turn and a selected target; recheck active; publish a Protobuf `ContextResolution` **while the host still holds the lease**. Revocation before publication fails closed.

### Resolution rules

- Corrections, retractions and changes of mind can reference an existing claim only after exact target binding by Lu's authenticated host, including its expected revision and latest event ID.
- An omitted selector is **never silently inferred** from the last model answer or a lone matching word. Ambiguous references abstain; cross-conversation targets require explicit host confirmation.
- Tentative, hypothetical, quoted, attributed, and non-user text cannot mutate state. A new explicit decision remains a candidate requiring host classification; it is not assumed to supersede the selected claim.
- Output includes `requires_host_review=true`, `may_write_state_directly=false`. It is **not** a `StateEvent`, a permission grant or proof of a verified source. Any later state write must perform independent native host authorization, current-source verification and CAS under the C06 fence.

### Test scope

19 focused Python tests check genuine change, correction, retraction, new decisions, tentative plans, multiple chats, no-selection abstention, unauthorized binding, stale/foreign scope, oversized/unknown Protobuf fields, post-bind revocation, source denial, and attempted host-callback mutation. They use **synthetic** host leases; they cannot certify native Lu authority, OS isolation or model interpretation.

### Open production dependencies

Native Lu must supply verified current ANSF source hashes, authenticated persisted user-turn role/text, per-target action authority, atomic lease lifetime through disclosure, revocation/deletion fencing, and separate mutation authorization. The pending Rust bridge needs Windows x86-64 compilation and native tests. This milestone deliberately does **not** run performance benchmarks, evaluate loaded LLMs, or modify Lu/GitHub.

**Development sequencing decision (2026-10-27):** continue implementing the remaining Cognitum capabilities with bounded unit and synthetic functional smoke tests. Defer full comparative baselines, model benchmarking and kill/promotion thresholds until the planned components are implemented.
