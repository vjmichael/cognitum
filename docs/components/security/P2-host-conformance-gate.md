# C02 / P2 — Signed Host-Conformance Receipt Gate

**Implementation date:** 2026-10-26 (Arizona local; CI timestamps may be 2026-10-27 UTC)  
**Owner:** Cognitum only. Lu `vjmichael/jan_alt` is **read-only** and remains unchanged.  
**Gate state:** **BLOCKED: real OS supervisor execution and independently measured confinement are NOT available.** This milestone implements a signed, bounded offline verifier of runner **claims**, *not* OS enforcement or a production entitlement.

## Why the older C02 acceptance-plan tests were insufficient

The prior [28-probe Protobuf test plan](P1-P2-supervisor-acceptance.md) enumerates what Lu's **future trusted host supervisor** must prove, with simulated revocation and cancellation. An attacker can claim success in ordinary process output. **Even an Ed25519 signature means only that a particular key signed the receipt, not that the key belongs to a trusted/isolated process, that OS probes ran, or that the observed denial was real.**

C02 now provides a second, separately versioned Protobuf *evidence envelope* that a future, independently vetted Lu supervisor can populate. Both the signer trust anchor and a fresh nonce **must come from trusted Lu host configuration, never a worker, model tool argument, downloaded document, or the receipt itself.** Cognitum cannot self-authorize a worker from evidence messages.

## New binary Protobuf evidence model

The existing [`cognitum.security.v1` schema](../../../proto/cognitum/security/v1/supervisor_acceptance.proto) has been extended with:

- `ProbeMeasurement`: exact probe ID, typed observed outcome, attempted status, SHA-256 pointer to **independently retained host evidence**.
- `SupervisorConformanceReceipt`: schema v1, SHA-256 of the **entire frozen negative probe plan**, one-use host-generated challenge, pinned Lu/worker binary build SHA-256, OS platform, observation time, independent runner ID, and complete probe measurements.
- `SignedSupervisorReceipt`: canonical serialized receipt bytes, a **detached Ed25519 signature** (64 bytes, domain-separated message), and a key ID used **only for lookup**; the receipt cannot define its own trust key.

[`cognitum/proto/supervisor_acceptance_pb2.py`](../../../cognitum/proto/supervisor_acceptance_pb2.py) is compiled-descriptor matched on Windows/Linux CI with `grpc_tools.protoc`; no JSON or pickle wire transport is introduced.

## Fail-closed, host-pinned offline verification

[`cognitum/supervisor_conformance.py`](../../../cognitum/supervisor_conformance.py) exports `verify_signed_receipt(...)`. It requires **externally trusted** arguments, rather than reading trust decisions from the receipt:

1. Exact caller-pinned Ed25519 **public key** and approved key ID; the corresponding private key must remain under separate Lu-runner protection.
2. Exact externally issued 32-byte random challenge (64 lowercase hex chars), independently pinned Lu host and worker build hashes, independent runner ID and target OS.
3. Trusted current UTC epoch time; reject receipts older than five minutes or more than five seconds ahead.
4. Signature over **domain-separated canonical Protobuf bytes**, rejecting malformed/oversized/unknown/duplicate tags.
5. Match of full frozen plan hash and **all and only** relevant common + selected-OS probes, in known order. Every probe must report `attempted=true`, the declared expected typed observation and a nonzero SHA-256 evidence digest.
6. Refuse explicit `simulation_only=true`, stale/absent/replayed-across-challenges identity, cross-host/build mismatches, altered signatures and omitted or failed probe claims.

A correctly formatted signature + matching claims yields an `OfflineConformanceReview` with `signed_receipt_valid=true`, `reported_probes_complete=true`, but **`os_isolation_verified=false` and `production_launch_allowed=false` unconditionally**. This is deliberate: digest pointers are not evidence bytes and the verifier cannot see a real restricted process. The existing [`start_isolated_worker()`](../../../cognitum/worker_wire.py) still denies **every** call.

**Important replay limitation:** The verifier is stateless. A pinned nonce prevents *cross-challenge* replay, but the Lu host must securely record consumption and expiry to prevent *same-challenge* replay. Clock, key and expected build values are caller-supplied; if the caller is untrusted, passing verification proves nothing meaningful.

## Executable negative tests, and what they do NOT prove

[`tests/test_supervisor_conformance.py`](../../../tests/test_supervisor_conformance.py) uses **ephemeral test-only Ed25519 keys**—no production signing key or host credentials are checked into the repository. It exercises corrupted/unknown/duplicate messages, wrong signing identity, failed signature, incomplete/skipped/failing/reordered probes, different platform coverage, mismatched host/worker builds, invalid caller-pinned nonce/clock/key, stale/future receipts, simulated-only flag and inability to bypass the existing worker launch denial.

Tests also create **synthetic claims with `simulation_only=false`** to exercise the verifier's positive format path. Such tests **are NOT** real OS isolation trials; their signature is under a test-generated key, and the resulting review explicitly reports OS confinement unverified.

The `[security]` Python package extra installs `protobuf` and `cryptography` only for this optional offline verifier. Default Cognitum core stays dependency-free. CI tests on Ubuntu/Windows and Python 3.11/3.13, checks all four Protobuf sources and runs the 12-case replay.

## True production C02 gate — required next Lu-owned implementation

**Do not mark C02 secure-worker execution ready until every item below is demonstrated** using a host-independent test harness on the actual Lu worker binary under normal/non-admin desktop identities:

- **Trusted worker boot:** Host derives real principal/task/workspace identity; exact scope, effect, consent, permission expiry and module signature are checked before spawning. Unsupported sandbox configuration must refuse launch.
- **Effective OS isolation:** Prove token/profile, write/read restrictions, symlink/reparse protections, network/DNS/loopback default-deny, inherited handle and credential denial, and CPU/RAM/process quotas using actual OS observations.
- **Descendant containment:** Verify full process-tree control (including intentional breakaway attempts), kill/reap on timeout, cancellation, revocation, CE unload or host crash.
- **Lifetime races:** Re-check permission at dispatch, abort inflight calls after revocation, deny new calls and reject any late but valid Protobuf result.
- **Independent evidence:** Preserve the raw, nonsecret OS probe evidence securely, bind digest to each receipt and run; verify runner identity/key custody against a Lu-provisioned trust store and enforce single-use nonce consumption.
- **Independent security review:** Test adversarial workload against actual Windows AppContainer/LPAC + Job Object or proven equivalent; Linux/macOS counterparts require equivalent separate validation. Exercise actual Lu desktop integration, not just an isolated Python harness.

Only the **Lu development team** can implement those host requirements under the existing user rule **not to modify Lu here**. Until independently proven, leave the existing launch gate **hard-denied**.

### Acceptance status

| Scope | Status |
|---|---|
| Canonical Protobuf acceptance plan, four-schema verification | **Implemented and unit-tested** |
| Signed host-evidence receipt parsing, challenge/build/platform/probe matching | **Implemented for offline format tests** |
| Host runner actually executing kernel-isolation probes | **Not available / not tested** |
| Real process confinement, scoped authority, revocation and process-tree cleanup | **Not demonstrated** |
| Production C02 security authorization | **BLOCKED — no worker launch** |

The [Lu DLC CE Addendum Register](../../lu-dlc-ce-addenda.md) remains the authoritative place to communicate host requests without writing to Lu.
