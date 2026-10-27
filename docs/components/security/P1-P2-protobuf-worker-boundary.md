# C02 / P1–P2 — Strict Protobuf Worker Boundary (Inactive by Design)

**Date:** 2026-10-26  
**Component:** C02 security, host authority and OS worker isolation  
**Scope:** Cognitum only. The Lu fork was inspected read-only and **not changed**.  
**Implementation status:** **P1 bounded Protobuf IPC implemented, P2 adversarial tests added. OS-isolated execution not implemented or certified; launch always denied.**  
**Depends on:** [C01 Protobuf native results](../core-runtime/P1-P2-protobuf-native.md), [canonical Protobuf CE handoff](../core-runtime/P1-P2-lu-ce-discovery-handoff.md), [C02 threat analysis](P0-research.md), [Lu addenda](../../lu-dlc-ce-addenda.md).

## Why this phase exists

Cognitum already has a trusted-code **diagnostic** `cognitum/worker.py` using `multiprocessing.spawn` and `Pipe.send/recv`. Python documents that `Connection.recv` unpickles received data; this must not be used to decode worker replies across an untrusted boundary. Spawning another Python process, sending a Protobuf message or validating a host-supplied grant **does not create operating-system confinement**.

C02 therefore isolates the **wire protocol** and **admission decision** from the future Lu-owned OS worker supervisor. The new code does *not* replace the legacy calculator smoke worker, install a DLC Core Extension, start a child process, or allow effectful/untrusted plugins.

## Typed worker protocol

The native [`cognitum.worker.v1` schema](../../../proto/cognitum/worker/v1/worker.proto) defines:

- `WorkerCall`: fixed protocol version, opaque call ID, approved native tool/operation, operation schema version, **exact Protobuf input/output type URLs**, input bytes and 1–10,000 ms deadline ceiling. Does **not** contain user IDs, authorization tokens, sandbox status or model-generated grants.
- `WorkerReply`: fixed protocol version, matching call ID and a Protobuf `oneof outcome`: `WorkerSuccess` (exact output type URL and Protobuf bytes), **or** `WorkerFailure` (sanitized known code and validated retryability). No free-form error messages, stack traces, credentials or results returned on denial.
- Removed/reserved field number blocks; no unknown future fields accepted until an explicit versioned migration.

The checked-in [descriptor-backed classes](../../../cognitum/proto/worker_pb2.py) are compared with `grpc_tools.protoc` using [the descriptor checker](../../../tools/check_proto_descriptors.py). Compiler comparisons include wire field numbers/types, `oneof` identity and reserved ranges. The Protobuf wire **has no JSON or pickle serialization**.

[`cognitum/worker_wire.py`](../../../cognitum/worker_wire.py) implements bounded deterministic (16 KiB maximum) binary encode/decode and closed semantic validation. It currently maps only the **reviewed, inert** `cognitum.calc.rational` operation using existing `cognitum.v1.CalculateRationalRequest` and `CalculateRationalResult`. An unknown type URL, operation version, malformed frame, duplicate scalar tag, shadowed `oneof`, absent result, mismatched call ID, oversize input, unknown error or invalid permission assertion is rejected. Pure exact results require the existing evidence and `intent_not_verified` limitation.

**No security decision is represented as a Protobuf field:** discovery metadata and worker messages are data. Lu must derive and enforce authenticated subject, capability grant, effect scopes, target workspace, consent and package provenance from its own trusted host before any invocation. An HDC candidate or model tool argument never grants filesystem, network or canonical memory access.

## Secure execution gate is deliberately closed

`admission_status()` returns `admitted=False` with five explicit missing controls, and `start_isolated_worker(...)` unconditionally raises `PermissionError`. In particular, a caller cannot pass `authenticated=True` or `sandbox="appcontainer"` to override this guard.

This is intentionally **not** a security attestation implementation or a production worker. Enabling execution requires all of the following to be separately built and **verified** by Lu's trusted native Rust/Tauri host:

1. Host-derived user/task/profile identity and exact permission/effect scopes; revocation and default-off CE enablement.
2. Windows AppContainer/LPAC restricted token **actually applied to the worker**, filesystem and credentials denied unless broker-approved; Linux sandbox/macOS equivalent proof.
3. Network/loopback/DNS denied by default, inherited handles/resources whitelisted and tested.
4. Job Object process-tree containment with breakaway blocked, kill-on-job-close, time/memory/process quotas, cancellation and all descendant reaping; Linux/macOS equivalent.
5. Trusted, authenticated/peer-verified IPC, bounded length-delimited Protobuf frames, no untrusted pickle, independent output validation, provenance/audit, bounded restarts.

**A Protobuf type URL and a passing CI test are not proof of OS isolation.** Windows AppContainer is designed to isolate files, process, network and credentials, while Windows Job Objects can manage resource limits and process trees. Both require properly configured native APIs and negative tests under the actual application account; one is not a substitute for the other.

## Test plan and evidence

[`tests/test_worker_wire.py`](../../../tests/test_worker_wire.py) covers protocol field/oneof consistency; binary typed roundtrips; 16 KiB frame and 10-second ceiling; malformed and unknown wire fields; duplicate fields and shadowed success/failure arms; tool/type URL and call ID mismatch; forged operation/identity-like claims; denied, timed-out and error results that do not masquerade as success; and failure of any attempt to launch without OS verification.

Run the entire Cognitum Python suite on **Linux and Windows**, versions 3.11/3.13; compile all three Protobuf schemas from source and verify their descriptors; repeat the existing 12-case calculator synthetic replay. **Do not count these as OS isolation, end-to-end Lu integration or actual untrusted worker penetration tests**. Keep future adversarial Windows tests as a separate gate.

## Security P0/P1/P2 limits and next host request

- **P0 partly advanced:** IPC sizes, type IDs, failure states, source/descriptor checking, negative cases and explicit OS gates are concrete. Actual threat review, permission broker and platform design still open.
- **P1:** inert protocol and fail-closed admission only, *not* worker process isolation; no source code written to Lu.
- **P2:** source and behavioral cross-platform test results recorded when GitHub Actions succeeds; no actual AppContainer/Job Object or real desktop tests performed.
- **P3:** production security tests and end-to-end task efficacy do **not** exist; do not promote this CE.

Lu team proposals remain [LU-CE-002, LU-CE-005, LU-CE-006 and LU-CE-007](../../lu-dlc-ce-addenda.md). Cognitum's optional CE identity, native Protobuf messages and future typed worker are still subject to Lu's host approval.

**Official platform references:**
- [Python multiprocessing connection documentation](https://docs.python.org/3/library/multiprocessing.html#connection-objects): `send`/`recv` pickle, `send_bytes`/`recv_bytes` operate on bytes.
- [Microsoft AppContainer isolation](https://learn.microsoft.com/en-us/windows/win32/secauthz/appcontainer-isolation).
- [Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects).
