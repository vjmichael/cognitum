# Alpha P3 — Standalone SQLite request journal and crash recovery

**Status:** portable reference implementation with local tests; NOT Lu-integrated or OS-isolation certified.

The new `cognitum.alpha_durable.DurableRequestLedger` records a caller-declared host approval and a unique `(conversation_id, request_id)` idempotency key in an SQLite database. It uses `BEGIN IMMEDIATE` transactions to serialize updates across processes and persists terminal revocation. `PENDING → RUNNING → DELIVERED/FAILED` is one-way; opening a new ledger instance changes any prior `RUNNING` records to `ABORTED`. On process crash or restarted host, the same request ID cannot replay an external sink. An exception in the result sink permanently consumes the attempt, rather than claiming exactly-once delivery.

`run_journalled(...)` connects this durable state to the **existing actual standalone subprocess** and P2 in-memory cancellation/lease board. The result must pass the existing typed Protobuf re-verification and live in-memory lease check before the persistent journal will publish. The journal takes the SQLite writer lock through the trusted sink callback, preventing a simultaneous journal revocation from interleaving with delivery. Terminal revocation does not retract results published *before* it.

**Security limits:** The provided `local_host_approval=True` argument is NOT an authenticated grant. Any Python caller with write access to the DB can alter authority state. There is no external high-water or TPM witness, immutable journal, cross-host locking, OS job-object/descendant termination, host signed task identity, verified Windows execution, or atomic transaction with remote/network sinks. Only a future trusted Lu supervisor may own the path and call site. Do not advertise to a model or install as a Core Extension.

**Test gate:** tests cover reject-by-default, duplicate IDs across restart, crash transition, terminal revocation, invalid epoch, sink failure, race serialization, actual subprocess callback, and refusing a real worker launch after journal revocation. CI matrix is Linux/Windows × Python 3.11/3.13; pending independent GitHub result.
