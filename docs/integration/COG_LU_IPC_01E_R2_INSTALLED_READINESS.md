# COG-LU-IPC-01E-R2-INSTALLED — Genuine installed handoff acceptance gate

Date: 2026-11-21. **Status: BLOCKED / NOT INSTALLED-ACCEPTED.** Scope: Cognitum-owned client, receipt verification, durable outbox and worker custody only. Do not change Lu Core or allow a source-only fixture to satisfy this gate.

## Source provenance and fixed starting point

- Cognitum reviewed branch `integration/cog-lu-ipc01e-r2-custody-20261121` had source-only native acceptance commit `b74f07df64496aec68ebede855ca82d214b4700b`. Original five-job [native run 44928333271](https://github.com/vjmichael/cognitum/actions/runs/44928333271): Ubuntu and Windows, Python 3.11/3.13, 196 per platform, **784/784** tests, zero skips/failures. Original artifact hashes are in `COG_LU_IPC_01E_R2_NATIVE_ARTIFACTS.json`.
- Subsequent branch doc-only closeout `4deaebedb54225c5bb8c52ed6449892fccd932ba` is **not** the tested source SHA. Pin file-level source identities before comparing it with any installed package.
- Lu Core draft [PR 244](https://github.com/vjmichael/Lu-AI-GUI/pull/244) observed head `29ed9621be4a879afd80cf231f84f67235ffb989` on 2026-11-21. It does not establish a Cognitum production publisher, approved signed Cognitum receipt envelope, or installed acceptance just because it contains IDE Windows admission source.
- Core-owned [#245](https://github.com/vjmichael/Lu-AI-GUI/issues/245) and [#248](https://github.com/vjmichael/Lu-AI-GUI/issues/248) were **OPEN** during this readiness check. Core workspace v0 proto blob `4e01d921197fb1c58c99958479b1cede36e13c9a` defines receipt *digest*, not issuer signing proof.

## Blocked preconditions — do not synthesize or self-certify

1. Lu Core accepts and publishes the **actual versioned Cognitum receipt contract** and signer verification semantics (or reviewed authenticated transport alternative); an R2 Ed25519 **proposed** envelope is not an accepted Core wire product. Bind original Lu package/publisher, OS peer, service epoch, exact OriginRefs, source SHA, typed capability `cognitum.ssm.fixed_duration.advance.v1`, PURE_COMPUTE user-turn grant, original durable terminal receipt, and original R6 outbox inventory.
2. Independently installed Lu Core **Health** endpoint with OS-native admission and publisher-key enrollment from #245. Windows must use signed installer/SCM broker and named-pipe peer evidence; Linux must use supervised service account, OS-local UDS and SO_PEERCRED, restrictive file modes, and durable credential-enrollment handoff. No HTTP/TCP, local test server, in-process signer, or caller-supplied package/signer pin accepted as production proof.
3. Cognitum **separately installed** service/worker supervisor, protected package and user identity, bound OS credential broker, protected R6 journal, OS-enforced revocation/cancellation, and independent monotonic revision root (TPM/remote/supervisor accepted by a reviewed threat model). DPAPI or Linux user keyring plus local authenticated SQLite CAS alone does not close rollback, publisher or service custody.
4. Independently protected **output-release authority** specifying recipient, one-use authorization, immutable output IDs/digests, nonce consumption, exact ack semantics, and post-crash uncertain-outcome reconciliation. No delivery or ack is allowed merely by a mathematically valid Ed25519 claim, local HMAC outbox snapshot, terminal status, or human-readable flag.

## Installed verification sequence (run only on independent physical/VM installed hosts)

| Stage | Genuine positive evidence | Mandatory refusal / negative controls |
| --- | --- | --- |
| A. Binary and peer ownership | Identify exact immutable Core and Cognitum package digests, signer/certificate or OS publisher proof, installed service identity, process birth/epoch, endpoint ACL, package-enrolled credentials. Log source commit and exact native binary hashes. | Unsigned/foreign package, installer swap/rollback, wrong UID/SID, stale PID, replaced path, untrusted endpoint, missing service, same-user test fixture. |
| B. Core-owned health | Separately installed Cognitum client performs OS-peer validated original native named-pipe/UDS HMAC challenge and real Core-owned HealthRequest/HealthReport; Core epoch is observed, not client-generated. | Wrong session, malformed/oversized/slow frames, wrong Core epoch, replay, revoked/expired credential, restart, pipe/socket substitution, unbounded queues. |
| C. Original per-turn admission | Independently authorized *real original* Lu user turn accepts only reviewed PURE_COMPUTE typed SSM capability. Record Core durable grant, descriptor/type URL, cancel and revocation authority. | Read/execute/network effect downgrade, invented grant from Cognitum receipt, foreign turn/workspace, fake typed request, unknown codec, cancellation after admission. |
| D. Terminal/origin receipt | Exact original Core terminal APPLIED receipt and matched reconciliation, accepted signed issuer/enrollment or authenticated equivalent, digest bound to prior original user-turn grant. R6 verifies original checkpoint and every pending row. | Unsigned synthetic proposer key, wrong/expired grant, stale issuer epoch, original receipt mismatch, forged signature/nonce, missing reconciliation, cancel/revoke/uncertain state. |
| E. Independent revision protection | Original local journal and truly independent monotonic authority agree after cold restart and process kill. | Restore BOTH SQLite/journal files, replay consumed nonce, replace or roll back independent authority, terminate worker while output pending. |
| F. Release & durable acknowledgment | Only an independently authorized release broker consumes one immutable output-id/nonce and delivers once under the approved recipient/ACK contract. Record receipt/ack from the real recipient and Core reconciliation. | Crash before send, after send before ACK, duplicate ACK, recipient timeout, unknown outcome, offline recipient; no automatic retry, no silent ACK/release, no false exactly-once claim. |

## Gate classification and receipts

- `PASS_NATIVE_SOURCE_ONLY`: previous bounded transport, Protobuf, original R6 and proposed Ed25519 tests only. This is already established for the **original** SHA, not installed production.
- `BLOCKED_CORE_CONTRACT`: #245 or #248 lacks independently accepted installed endpoint, signed Cognitum publisher, format or original-turn grant. **Current status.**
- `BLOCKED_COGNITUM_INSTALL`: Core ready but Cognitum OS service/publisher enrollment, worker custody or independent revision authority missing.
- `BLOCKED_RELEASE_AUTHORITY`: Core and Cognitum installed, but recipient/nonce/ACK, revocation, uncertainty and recovery authority not qualified.
- `PASS_INSTALLED`: allowed **only** after independent inspector has verifiable original source+binary hash, signer/publisher authority, real native peer transcript, authorized Core user-turn and protected operation receipts, R6 original output evidence, independent antirollback receipts, authenticated one-use release/ACK/negative-case receipts. A JSON flag, manually typed checkbox, loopback signer, local SQLite file, or CI success cannot assert this status.

Required evidence manifest is a *reference/index of independently verifiable receipts*, not a source of trust. Retain exact platform/host installer pin, Core and Cognitum build SHAs/hashes, publisher chain, native OS service observations, issued grant identity, original Health and operation frame digests, signed receipt protocol version, Core issuer enrollment, R6 journal and external antirollback revision, original outbox IDs/digests, release-broker single-use consume and recipient ACK, crash/rollback/cancellation negative logs and independent reviewer signature. Redact keys/user content. Any missing, untrusted or uncertain event stays BLOCKED/UNKNOWN. No external output allowed.

## Next engineering handoff

**Core-owned:** #245 and #248 must publish an actual Core-maintained endpoint/enrollment and cryptographically or authenticated-host accepted original operation receipt proof format; include accepted publisher pins, typed SSM admission/effect mapping, epoch/turn grant, revocation, external release broker contract and independently produced receipts. Update existing issues, not a duplicate.

**Cognitum-owned:** adapt the existing `lu_ipc_native`, `lu_ipc_receipt_attestation`, `lu_ipc_lifecycle`, `lu_ipc_outbox`, and real R6 supervisor **only** against the accepted Core contract. Then run the six installed stages and native regression with one exact-source cohort. Do not publish/acknowledge or implicitly retry before authorization. This readiness document itself is not an installed test, and does not assert a production handshake occurred.
