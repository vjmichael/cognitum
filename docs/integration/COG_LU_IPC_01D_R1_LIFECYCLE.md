# COG-LU-IPC-01D-R1 — bounded original-operation, cancellation and durable reconciliation verifier

**November 21, 2026 — scoped native source ACCEPTED.** Original tested SHA 01e327791aef09d36150b4b50470a753177a2b73; [CI run #44925223484](https://github.com/vjmichael/cognitum/actions/runs/44925223484) all five original jobs PASS, 135/135 tests per genuine Windows/Ubuntu Python 3.11/3.13 = 540/540 tests, no error/failure/skip. Fifth independent original job and external five original ZIP SHA-256/CRC/JUnit/source identity audit PASS. No installed Lu Core producer, OS-backed signing, authoritative hardware monotonic anchor or output permission qualified. Cognitum repository only. Lu-owned open [#245](https://github.com/vjmichael/Lu-AI-GUI/issues/245) (installed protected Health dispatcher) and [#248](https://github.com/vjmichael/Lu-AI-GUI/issues/248) (signed Cognitum package + PURE_COMPUTE admission) already cover Core-side work. No Lu Core edits or duplicate issues.

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

## Accepted original exact-SHA evidence

Original accepted source: 01e327791aef09d36150b4b50470a753177a2b73. [Native original 5/5-job run #44925223484](https://github.com/vjmichael/cognitum/actions/runs/44925223484). Ubuntu Python 3.11 135/135, Ubuntu Python 3.13 135/135, Windows Python 3.11 135/135, Windows Python 3.13 135/135: **540/540 tests PASS**, including the original accepted IPC-01A/B/C suites and 35 new bounded durable operation/cancellation/reconciliation tests per platform. No errors, failures or skips.

Native grpcio-tools compiled unchanged Lu workspace v0 original source Git blob 4e01d921197fb1c58c99958479b1cede36e13c9a and Cognitum SSM v1 original source Git blob 755562254afdbea686ee33b95567c505f2f85e49. Composite descriptor SHA-256: d2cf48e33c80837ac99f2a080ba16996617020c84482f690b8ea1e5f089e79f0; generated Lu module SHA-256: 3757c3adcd357d57a353a29490c60e687eedb32f6a4d78ea8759378a15e2d22b; generated SSM module SHA-256: 4aa6463da1775f93ada551f172ac3a69f5f2e261ca0955089fd4d345b51cef40.

The fifth original job independently confirmed identical four 135-case JUnit identities, exact original SHA, all 18 Git source/test locks and generated native binaries. Status PASS_ORIGINAL_NATIVE_LIFECYCLE_AND_SOURCE. In a separate verification outside CI, all five original ZIP archives were downloaded and compared against GitHub SHA-256 metadata, ZIP CRC checked, JUnit pass/skip/error results parsed, 18 source pins rechecked and compiled Protobuf outputs compared. [Manifest](COG_LU_IPC_01D_R1_NATIVE_ARTIFACTS.json).

**Limitations:** The local SQLite HMAC chain and injected test key/anchor are not privileged service credentials, independent authoritative TPM/remote anti-rollback, signed Lu Core provenance or original Lu journal. The native tests do not qualify worker termination, real Core per-turn grant, live mathematical execution or external result publication. The Core-owned endpoints and enrollment remain tracked in Lu #245 and #248; no Core repository files were changed. Original R1 source had no compiler or test failure. The later documentation and workflow-only closeout does not requalify a different source SHA. The one-time CI push trigger is retired to manual only.

**Next:** Cognitum-side COG-LU-IPC-01E-R1 host/domain replay, revocation and outbox reconciliation source assurance, alongside installed SSM R6-INT-03. COG-LU-IPC-01D-R2 genuine installed Core-source and receipt admission remains externally blocked on #245/#248.
