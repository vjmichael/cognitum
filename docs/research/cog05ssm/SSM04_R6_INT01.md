# COG-05-SSM-04-R6-INT-01 — MEL host-scoped SSM checkpoint and journal integration

**2026-11-21 state: HOST-ONLY MEL INTEGRATION ACCEPTED at exact-source native testing scope — 5/5 GitHub native/evidence jobs PASS; 274/274 tests per Windows/Ubuntu Python 3.11/3.13 platform, 1,096/1,096 total.** Original qualified commit: 3a2c1ba6eaac51ed9934f0cbbcaeb3ba993dbc4d. Accepted R3–R6 mathematical source and tests remain byte-for-byte unchanged. This does NOT install an SSM tool in the MEL registry or qualify Lu model-facing admission, OS credential-broker custody, or physical exactly-once delivery.

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

## R6-INT-01 exact-source native acceptance and original artifact custody

- **Original accepted run:** [#44914658450](https://github.com/vjmichael/cognitum/actions/runs/44914658450), first successful consolidated successor, at exact SHA 3a2c1ba6eaac51ed9934f0cbbcaeb3ba993dbc4d. All **five original GitHub Actions jobs passed**.
- Ubuntu Python 3.11 **274/274**, Ubuntu Python 3.13 **274/274**, Windows Python 3.11 **274/274**, Windows Python 3.13 **274/274**. Aggregate **1,096/1,096**, with zero native failures, errors or skips; **23** new MEL–SSM host-journal tests passed in each environment.
- The fifth original CI job independently matched all four original native JUnit (classname, name) identities and 15 unchanged/integration Git blob IDs, together with their exact original commit SHA, and produced PASS_HOST_MEL_JOURNAL_MATH_RECOVERY_AND_ORIGINAL_SOURCES.
- **Separate outside-CI verification:** independently downloaded the five original GitHub Actions ZIP artifacts, compared their SHA-256 digests to the original GitHub metadata, verified ZIP CRC integrity, parsed all four original JUnit XML records and all 15 Git source/test hashes, confirmed identical original test identities and read the independent fifth-job receipt. Inventory: [SSM04_R6_INT01_NATIVE_ARTIFACTS.json](SSM04_R6_INT01_NATIVE_ARTIFACTS.json).
- **Initial unsuccessful workflow #44914500386:** all four native systems executed 274 tests, with **273 passed and one incorrect test expectation**. The test wrongly expected the checkpoint scope-binding denial, while the existing MEL authorization correctly denied the foreign scope earlier. Repaired only that test and its pinned workflow hash; no journal implementation or preexisting mathematical source changes were required. One controlled consolidated successor produced the successful run.
- **CI trigger retirement:** after acceptance, change the temporary branch-scoped push trigger to manual-only in a non-forced documentation/CI-control-only [skip ci] closeout commit. Original exact-SHA qualification remains anchored at 3a2c1ba6eaac51ed9934f0cbbcaeb3ba993dbc4d; the subsequent closeout commit is NOT presented as tested.
- **Explicit installed-security exclusions:** the credential hook does not itself implement protected OS key storage; the monotonic anchor and model approval must be supplied by a trusted host; external downstream exactly-once delivery, full SQLite deletion/rollback audit, end-to-end protected MEL SSM worker route, filesystem ACL and Windows power-loss behavior remain unqualified.

**R6-INT-01 host-only native integration: PASS at the specified mathematical/journal/scope test boundary.**

**Pending after acceptance:** genuinely installed OS key custody, independently protected revision CAS, full journal deletion/rollback audit, durable destination delivery guarantees, actual supervised MEL SSM worker/Protobuf route and its installed authorization. These are not fulfilled by a host-only adapter.
