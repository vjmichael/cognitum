# COG-LU-IPC-01D-R1 — bounded original-operation, cancellation and durable reconciliation verifier

**November 21, 2026 — source candidate; native OS qualification pending.** Cognitum repository only. Lu-owned open [#245](https://github.com/vjmichael/Lu-AI-GUI/issues/245) (installed protected Health dispatcher) and [#248](https://github.com/vjmichael/Lu-AI-GUI/issues/248) (signed Cognitum package + PURE_COMPUTE admission) already cover Core-side work. No Lu Core edits or duplicate issues.

## Source and authority

- Existing original Lu workspace v0 Protobuf Git blob: 4e01d921197fb1c58c99958479b1cede36e13c9a; native message definitions: OriginRefs, CapabilityInvoke, OperationEvent, CancelOperation, CancelAcknowledged, ReconcileOperation, ReconciledOperation, StreamCredit and OperationReceipt. Original Cognitum-owned SSM v1 Protobuf blob remains 755562254afdbea686ee33b95567c505f2f85e49.
- Accepted Cognitum lu_ssm_contract.inspect_invoke strictly pins externally trusted host Lu origin, SSM model context, checkpoint revision/checkpoint SHA-256, event cursor, sensor size and causal observation. New lu_ipc_lifecycle.DurableLuOperationVerifier accepts an already validated SsmCandidate and exact original typed CapabilityInvoke. No new invoke, model grant, mathematical worker, publisher or alternate registry.
- Immutable original scope includes Lu workspace/conversation/user turn/task/operation, original request ID, Core session and epoch. Trusted host supplies these. Lu's session_ref or source-side HMAC is NOT independent proof of an installed signed Core producer.

## Lifecycle

- StreamCredit is bounded to 64 outstanding events. Original Lu OperationEvent frames require positive contiguous sequence, original authenticated request/session/operation reference, and available credit. Progress stage/optional percentage bounded. A single terminal is accepted; duplicate/conflicting, cross-session and out-of-credit events refused.
- CancelOperation is a host-origin intent; CancelAcknowledged.signal_recorded=true is accepted only after intent and is NOT proof of OS worker termination, undo, revocation, rollback or a durable completed effect.
- Terminal APPLIED requires the exact Cognitum SSM typed result, matching the original request digest and expected checkpoint revision plus bounded release count; terminal REFUSED/FAILED/CANCELLED/UNCERTAIN carries a bounded reason and no output. A 32-byte durable_receipt_sha256 is a locator, NOT signed Core provenance.
- ReconcileOperation binds original full Lu OriginRefs. ReconciledOperation with available evidence must match the original locally held terminal byte-for-byte. Missing evidence with UNSPECIFIED/UNCERTAIN is preserved as UNKNOWN, not APPLIED. No observation, even matched, authorizes publication. Host revocation prevents later progress while allowing explicit reconciliation of original operation.

## Durable local audit and limitations

- One bounded local SQLite HMAC-chained log (256 entries max, 64-KiB frame budget), host-borrowed key, original-source replay validation, SQLite synchronous FULL and private POSIX path/mode/symlink checks. No key persisted in the journal.
- A required externally authoritative monotonic anchor read/advance must match the original durable sequence and MAC head on every read/write/reopen. An OS interruption after local commit but before independent anchor update fails closed as uncertain; no silent local recovery.
- A local SQLite file/HMAC, plus in-memory anchor used by tests, is NOT a protected OS service, independent monotonic hardware/remote revision authority, protected Windows ACL, installed signed credential broker, or genuine Core journal receipt. All remain unqualified pending R6-INT-03 and Lu #245/#248. The verifier never issues a model tool grant, dispatches, starts a worker, or publishes.

## Native acceptance

One consolidated exact-source Windows/Ubuntu Python 3.11/3.13 cohort compiles the two original pinned Lu and Cognitum native Protobuf schemas, tests 01A/01B/01C regressions plus 01D positive/negative lifecycle/restart/rollback, and archives JUnit, exact source Git SHA and 19 original pinned blobs. Fifth independent job compares original JUnits, codegen SHA, OS platforms, and fail-closed scope. Original five GitHub ZIPs externally SHA-256/CRC-verified after CI. No stacked runs and no Lu Core code modifications.

**Next:** COG-LU-IPC-01D-R2 — genuine installed Core-origin operation and receipt provenance when Core provides signed enrollment/host PURE mapping. Cognitum-side cancellation and protected worker custody can continue in parallel, but no authority is inferred from source-only receipts.
