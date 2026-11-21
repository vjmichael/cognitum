# COG-05-SSM-04-R6-INT-01 — MEL host-scoped SSM checkpoint and journal integration

**2026-11-21 state: host-only candidate committed; native exact-source acceptance pending.** Accepted R3/R4/R5/R6 mathematical source and original tests are unchanged. This does not install an SSM tool in the MEL registry or claim Lu model-facing approval or OS credential-broker custody.

## Architecture and authority boundary

New module: cognitum/mel/ssm_recovery.py. HostSSMJournal requires an existing, live Cognitum MEL Admission instance and the exact trusted MEL Scope of session, workspace, subject and turn. A trusted host supplies an approved model-context blob (including the initial prior), stable stream ID, externally held HMAC credential broker, protected monotonic revision/digest trust anchor, affirmative revocable per-operation authorization callback, and an absolute SQLite path in a previously provisioned trusted directory.

The existing Admission scope/session and host callback are checked at open, restore, process, commit, inspect, pending output and acknowledgment. This is *host coordination*, not a separate runtime, scheduler, Protobuf RPC, model tool, MEL registration or actual SSM worker. It cannot issue grants or convert a source hash into execution authorization.

**Credential broker:** credential_broker.borrow_key(scope, stream_id) is called for each sensitive action. HMAC key bytes are validated, not written to checkpoints, SQLite, receipts or logs, and are not retained as an adapter attribute. The interface requires an installed host to provide actual protected Windows CNG/DPAPI/SCM or Linux keyring/broker custody. The current implementation does not do so and cannot guarantee in-process zeroization.

**Trusted anti-rollback store:** revision_anchor.read(scope, stream_id) returns (revision, exact checkpoint SHA-256 digest). advance(scope, stream_id, prior_revision, prior_digest, new_revision, new_digest) provides an external atomic CAS. R6 serialized checkpoints are HMAC authenticated and bound to the approved model and MEL scope. An older SQLite snapshot than the external floor, an equal revision with a different digest, wrong scope/model identity, or a bad HMAC is refused.

## Durable input/output semantics

SQLite WAL and FULL synchronous mode are used with a BEGIN IMMEDIATE transaction for each accepted input. It co-commits an incremented authenticated R6 checkpoint, canonical input request digest and immutable event identity, signed journal head and HMAC-tagged pending output rows.

A matching duplicate event ID and request yields an idempotent no-op. Different input under the same ID is refused. The original R5 filter enforces causal time and watermark order. The protected host calls process with bounded input; this method returns metadata with publish_authorized=False and never publishes results. The host retrieves verified pending_outputs, delivers to the approved destination, then records acknowledge with the exact output ID and SHA-256. Unacknowledged rows survive restart; acknowledgment is idempotent.

The integration implements *at-least-once recoverable pending outputs*, NOT automatically exactly-once external side effects: the installed host/destination needs its own deduplication and transactional delivery/ack contract. On external anchor-CAS failure *after* durable SQLite commit, the adapter fails closed until restart; a new instance reauthenticates the committed checkpoint and advances the trusted anchor. A stale or mismatched anchor refuses instead of guessing. No protected OS-level rollback guarantee exists until the host provides and qualifies that service. The journal is durable, not unbounded-memory: the pending outbox refuses excess capacity and journal retention/compaction is a separate lifecycle.

The checkpoint and outbox are authenticated, NOT encrypted. The directory and SQLite database must be protected by host OS ACL/custody. Individual output HMAC and latest event-head MAC do not independently prove the absence of arbitrary deletion of older SQLite records or wholesale file rollback during an external-CAS gap. Windows power-loss durability, SCM protection and Linux broker installation remain unqualified.

## API and original test plan

HostSSMJournal(..., initial_engine=...) creates a stream only with a fresh trusted anchor. Restart uses initial_engine=None; attempts to replace a previously authenticated stream are refused. Methods: process(event_id, kind, end_time, increment), pending_outputs(limit), acknowledge(output_id, expected_body_sha), status(), close(). All inputs and values have bounded, non-model-authoritative semantics.

Research test suite: research_tests/mel_ssm_r6int01/test_journal.py. Tests exercise a real existing MEL Admission/Runtime session, with explicit fake broker and monotonic anchor (not falsely described as installed security). Cases cover scoped host authorization, deterministic R5 recovery, missing increments, watermark release, key absence from DB, CAS failure/reconciliation, replay/idempotency and conflict refusal, tampering of snapshots/event heads/outbox, checkpoint revocations, symlink, payload limits and six randomized restart traces.

Native acceptance: one controlled branch-scoped GitHub Actions batch on Windows/Ubuntu Python 3.11/3.13 runs original SSM and MEL admission tests with new journal tests, followed by a fifth original-JUnit/source-blob reconciliation job. Preserve and independently rehash original evidence. Retire the temporary trigger only after successful native acceptance.

**Pending after acceptance:** genuinely installed OS key custody, independently protected revision CAS, full journal deletion/rollback audit, durable destination delivery guarantees, actual supervised MEL SSM worker/Protobuf route and its installed authorization. These are not fulfilled by a host-only adapter.
