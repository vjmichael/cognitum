# C02 / P1–P2 — Native Protobuf OS Supervisor Acceptance Specification

**Scope:** Cognitum-owned development only. Lu `vjmichael/jan_alt` stays **read-only**.  
**Reference Lu contract:** [`CoreExtensionHost` in `lu/independent-branding-ce-foundation`](https://github.com/vjmichael/jan_alt/blob/lu/independent-branding-ce-foundation/src-tauri/lu-core/src/core_extension.rs) explicitly lacks signed installer trust, worker isolation and cancellation of in-flight calls.  
**Status:** **Protobuf test-plan implementation and offline synthetic lifecycle checks**, *not* a process supervisor, cryptographic signature, permission grant, operating-system confinement or security certification.

## Purpose

After C02 implemented bounded [Protobuf worker IPC](P1-P2-protobuf-worker-boundary.md), the next dependency is a precise, portable and reviewable **host-run negative acceptance suite**. This milestone freezes what Lu's future *trusted host supervisor* must demonstrate before Cognitum will allow untrusted or effectful workers.

**Authoritative rule:** The model, an external document, a worker-generated response or a test-plan Protobuf cannot claim to have passed host-security tests. Lu's real native supervisor and independent OS-level harness must supply evidence. The production launch gate in `cognitum/worker_wire.py` **continues to deny all callers**, including those supplying a fabricated `sandbox_verified=True`.

## Binary contract

[`proto/cognitum/security/v1/supervisor_acceptance.proto`](../../../proto/cognitum/security/v1/supervisor_acceptance.proto) defines `cognitum.security.v1.SupervisorAcceptancePlan`: version, CE ID, exact worker `cognitum.worker.v1.WorkerCall` type URL, required `SupervisorProbe` records, and `production_launch_enabled=false`.

Each probe has a stable ID, typed `ProbeKind`, `Platform` and `Expected` outcome. There are no model prompts, raw credentials, granting tokens, sandbox attestations, file paths or JSON payloads. The checked-in Python bindings are real `google.protobuf` messages and checked against `grpc_tools.protoc` on Windows/Linux CI, including enum identities, field numbers and reserved ranges. `encode_acceptance_plan()` emits deterministic Protobuf bytes; `decode_acceptance_plan()` rejects unknown/duplicate fields, malformed or oversized frames, version drift, deleted probes, altered expectations and any `production_launch_enabled=true` flag.

**Do not mistake matching bytes for authenticity.** The decoder only checks that a proposal equals the fixed reviewed plan, not that it came from an authenticated Lu build, nor that any real probe has executed.

## Required negative-test matrix

| Domain | Required host observation | Scope |
|---|---|---|
| Subject/task/workspace grants and expiry | Deny missing, cross-profile, forged or replayed authority | All |
| CE registration and scoped effects | Reject unknown tool, incorrect effect or unavailable sandbox | All |
| Private reads and unapproved writes | Host-isolated worker denied access, including symlinks/reparse paths | Windows, Linux, macOS |
| DNS, loopback and external network | No default egress for isolated worker | Windows, Linux, macOS |
| Inherited handles or environment secrets | No leaked credentials or inherited privileged descriptors | Windows, Linux, macOS |
| Process-tree escape and orphan survival | Supervisor terminates and reaps all descendants | Windows, Linux, macOS |
| RAM/CPU/process/wall-time overrun | Effective, independently measured resource ceiling | Windows, Linux, macOS |
| Timeout, cancellation, midflight grant revocation | New calls blocked, descendants killed/reaped | All |
| Workspace/CE unload | Drain/reap its own workers, leave Lu Core and unrelated DLCs operational | All |
| Late reply after revocation | Host rejects stale result even if bytes/shape are valid | All |
| Tracing | Approved metadata only, never prompts/tokens/secrets | All |

**Windows-specific implementation hypotheses**, to be proven by the separate Lu team: restricted token/AppContainer or LPAC, a Job Object covering the entire process tree with breakaway restrictions, exact handle inheritance allowlist and denied network. Linux could involve user/mount/network namespaces, seccomp, cgroups and dedicated broker. macOS could involve Seatbelt and resource/process supervision. Merely selecting a backend name is not evidence that restrictions were actually applied.

## Offline lifecycle test model

[`cognitum/supervisor_acceptance.py`](../../../cognitum/supervisor_acceptance.py) includes `check_synthetic_shutdown()`, a **pure seven-event state-sequence validator**:

```text
synthetic_admission
  → synthetic_worker_started
  → cancel_requested | grant_revoked | ce_unloaded | timed_out
  → new_call_denied
  → descendant_tree_terminated
  → descendant_tree_reaped
  → late_reply_rejected
```

Tests reject "new call allowed", termination after reaping, orphan descendants, late successful output, missing completion of cleanup, forged admission and extra activity after shutdown. A consistent simulated sequence returns `OfflineLifecycleCheck(sequence_valid=True, os_confinement_verified=False, launch_permitted=False)`. This is a **model check**, not proof of real native process handling.

## P2 verification versus remaining production gates

New [unit tests](../../../tests/test_supervisor_acceptance.py) check Protobuf roundtrips, full probe coverage, three-platform negative cases, immutable expectation fields, tamper/version/unknown-wire rejection and simulated revocation/cancel/unload/timeout sequences. GitHub CI compiles four Protobuf schemas and runs the entire existing unit/replay suite across Windows and Linux, Python 3.11 and 3.13. Source/binding equivalence is checked in CI.

**P2 pass is only an offline contract and simulation result.** Before production use, the **Lu team** must implement real host-bound principal/grant attestation, test harness identity, OS-enforced file/network/handle restrictions, child-process survival checks, revocation/cancel races, crash recovery, resource limits and actual Windows desktop execution in a non-admin environment. Data provenance, signed plugin packages, CE enable/disable and multi-effect scopes also remain open.

**No Lu repository edits, executable installers, Windows AppData access, or untrusted worker launches are part of this Cognitum milestone.**
