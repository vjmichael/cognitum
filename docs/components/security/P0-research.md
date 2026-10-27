# C02 / P0 — Host Authority, OS Worker Isolation and Permission Design

**Started:** 2026-10-26  
**Status:** P0 in progress; **design-only** (no sandbox integration, Windows execution or security certification).  
**Component:** C02 Security / Scopes / Worker Isolation; depends on C01/C04 native contracts.  
**Source branch reviewed:** `vjmichael/jan_alt@lu/core-contracts-native-registry`, pinned audit reference `11b2e7e8c5370d512a8f8815d5aaaf9e682e04df`.  
**Main safety invariant:** Lu's trusted host, not transformer output, defines the task identity and exact permitted effects. Native tool labels, approximate retrieval and an OS process alone are not authority or isolation.

## 1. What is reusable in Lu already

| Lu source | Verified existing capability | Scope boundary |
|---|---|---|
| [`lu-core/src/policy.rs`](https://github.com/vjmichael/jan_alt/blob/lu/core-contracts-native-registry/src-tauri/lu-core/src/policy.rs) | In-memory exact tool/scope/effect grants, expiry and revocation; no wildcard scopes | No verified user authentication or persistent approval journal; default descriptor has only one `ToolEffect` |
| [`lu-core/src/privilege_guard.rs`](https://github.com/vjmichael/jan_alt/blob/lu/core-contracts-native-registry/src-tauri/lu-core/src/privilege_guard.rs) | A mandatory model-tool ceiling refuses declared `Elevated` and `DeviceControl` effects | A declared effect cannot attest a malicious implementation's actual behavior; needs independent OS isolation |
| [`lu-core/src/host_resource_authority.rs`](https://github.com/vjmichael/jan_alt/blob/lu/core-contracts-native-registry/src-tauri/lu-core/src/host_resource_authority.rs) / [`host_session.rs`](https://github.com/vjmichael/jan_alt/blob/lu/core-contracts-native-registry/src-tauri/lu-core/src/host_session.rs) | Experimental principal, owner/project/sensitivity/read-export-train decisions and trusted window binding | Not a complete authenticated desktop principal; host must derive from actual trusted window/session lifecycle |
| [`tauri-plugin-agent-tools/src/tools/appcontainer.rs`](https://github.com/vjmichael/jan_alt/blob/lu/core-contracts-native-registry/src-tauri/plugins/tauri-plugin-agent-tools/src/tools/appcontainer.rs) | Substantial Windows AppContainer implementation for Jan's **shell** confinement, including workspace scoping and opt-in network controls | **Do not assume it automatically confines a Cognitum/Python worker**, any worker's descendants or all IPC handles |
| [`tauri-plugin-agent-tools/src/tools/jail.rs`](https://github.com/vjmichael/jan_alt/blob/lu/core-contracts-native-registry/src-tauri/plugins/tauri-plugin-agent-tools/src/tools/jail.rs) | Linux bubblewrap, macOS Seatbelt and Windows AppContainer selection and shell confinement policy | Designed for **shell** operations, and host/backend checks differ. A separate worker must verify its effective policy rather than reuse a label |
| [`tauri-plugin-agent-tools/src/tools/sandbox.rs`](https://github.com/vjmichael/jan_alt/blob/lu/core-contracts-native-registry/src-tauri/plugins/tauri-plugin-agent-tools/src/tools/sandbox.rs) | Canonical path containment, symlink checks, Windows path anomaly refusal, readonly/write roots | Application path checks are **defense in depth**, not a substitute for kernel-enforced filesystem isolation |
| [Cognitum `worker.py`](../../../cognitum/worker.py) | Short-lived Python spawn, timeout/terminate and error sanitization | No OS-token confinement, memory/CPU quotas, process-tree isolation or untrusted-safe IPC; **not a sandbox** |

**P0 preference:** adapt and audit Lu's existing native OS confinement and policy mechanisms wherever they fit, before selecting a new language/framework. Design Cognitum's capability worker as a separately isolated execution target, not a trusted Jan shell process with broad credentials.

## 2. Relevant industry/platform references

| Official source | What it supports in the design | What it does NOT prove |
|---|---|---|
| [Microsoft — Launch an AppContainer](https://learn.microsoft.com/en-us/windows/win32/secauthz/implementing-an-appcontainer) | AppContainer and stricter LPAC capabilities as candidate Windows restricted tokens, limiting access to user files, processes, registry, network and credentials | That any particular Lu/AppContainer profile safely launches arbitrary Python or all optional CEs |
| [Microsoft — Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects) | Managed process trees, limits, accounting, kill-on-job-close; candidate deadline/memory/CPU and orphan cleanup mechanism | That job objects alone enforce data path/network isolation or trustworthy principal identity |
| [Microsoft — Process handle inheritance](https://learn.microsoft.com/en-us/windows/win32/procthread/inheritance) | Child-process inherited handles can preserve access; use `bInheritHandles=FALSE` or explicitly whitelist required handles using `PROC_THREAD_ATTRIBUTE_HANDLE_LIST` | That environmental variable filtering alone protects inherited file/credential handles |
| [Lu's own security ceiling design](https://github.com/vjmichael/jan_alt/blob/lu/core-contracts-native-registry/src-tauri/lu-core/SECURITY_AUTHORITY_AND_OS_CEILING.md) | Already articulates no implicit admin privileges, exact human-task lineage, protection against prompt-injection as authorization, independent worker identity and read/write/network separation | Not evidence that every planned acceptance test has already passed |

A CPU control-plane is favored, with hardware acceleration reserved for explicitly authorized domain computation. GPU/FPGA access **does not imply privileged device management**; access requires a separately reviewed resource broker if it crosses the host's physical-device prohibition. No inference about AMD/ROCm driver sandbox compatibility has been tested here.

## 3. Threat model — actors, assets and trust transitions

**Untrusted:** model output/tool arguments, retrieved documents/HTML, third-party plugins, imported checkpoints, archives and external data. They can request work but may not authenticate users or elevate authority.

**Host-owned assets:** conversation/profile/project ownership, tool grants, canonical memory, credentials, model/service keys, filesystem mounts/paths, network privileges, trusted module registry and audit logs.

**Trust boundaries:** model JSON→Lu typed codec; host session→authorized operation; Lu registry→Cognitum CE; CE wrapper→Python/research worker; worker→filesystem/network/device and canonical memory; worker result→Lu/model. Each has independent validation and failure cleanup. **No authority from approximate HDC or KAN outputs.**

**Attack tests:** cross-profile/thread IDs; prompt text that pretends to be a grant; malicious JSON/protobuf field/size manipulations; file traversal/symlinks/junctions/reparse points; inherited handles and environment leaks; unintended network/loopback/DNS egress; process fork/child survival; CPU/memory exhaustion; killed worker leaving durable partial writes; stale policy after disable/revoke; logging secrets; arbitrary code execution through Python deserialization.

## 4. Candidate worker design (proposal, not implementation)

1. Lu Rust host verifies its own signed/host-bound session and grants; checks exact `tool_id`, operation, intended data/resource scope and approved effect set **before** worker spawn.
2. Native CE declares effects and dependencies. New optional CE lifecycle must preserve default-off semantics. Bridge any disparity between Lu single-effect descriptors and Cognitum multi-effect sets by explicitly modeling all actual effects or splitting operations; do **not** label read+network as read-only.
3. Untrusted CPU process uses OS confinement appropriate to platform; on Windows evaluate **AppContainer/LPAC or restricted token + explicitly scoped broker** plus **Job Objects** for resource/process-tree limits. Make required Python runtime/dependencies readable inside the sandbox without mounting credentials or exposing the entire user profile.
4. Send bounded length-delimited *typed messages*, authenticated/scoped at the host, with finite sizes/depths. Avoid Python `pickle` or object-deserializing `multiprocessing.Pipe` when the producer is untrusted.
5. Explicitly control inherited handles, environment, temporary files, network and process descendants. Deny everything not required by the task; do not rely only on a path denylist, Python filters, or process naming.
6. On timeout, crash, cancellation, policy revocation or workspace unload: reject new admissions, terminate worker/process tree, recover/reconcile any effect journal, and avoid false success responses.
7. Result is validated typed data with provenance and explicit status/outcome. Neither a module's `health()` nor passing a smoke test gives it permanent privileges.

**Initial trusted/inert special case:** The existing bounded calculator may be executed for local diagnostic smoke testing under a narrowly accepted trusted code assumption. **No untrusted or effectful Python CE is enabled on the strength of that exception.**

## 5. P0 alternatives and hardware/OS suitability

| Option | P0 disposition |
|---|---|
| Adapt Lu's existing Windows AppContainer shell boundary | **First evaluation candidate**, only after identifying actual callable broker points and measuring access denial with a new Cognitum worker |
| AppContainer/LPAC + Job Object + handle allow-list | **Leading Windows prototype hypothesis**, subject to robust access and lifecycle verification |
| Restricted token / separate low-privilege user + broker | Alternative if Python/driver/AppContainer compatibility fails; requires credential/account lifecycle review |
| Bubblewrap (Linux) and Seatbelt (macOS) | Potential reuse from Lu native jail, with platform-specific tests and attention to real filesystem/network containment |
| WASM/WASI sandbox | Consider for portable *pure deterministic* components; not a universal substitute for Python/native libraries or memory/state access |
| Unrestricted `multiprocessing.spawn`, container-like Python libraries or a path filter alone | **Not acceptable as an untrusted plugin boundary** |

## 6. P0→P1 handoff and security gates

- [ ] Confirm the active Windows Lu native sandbox backend and actual testable API reuse point; compare AppContainer/LPAC vs restricted token options.
- [ ] Define immutable host-bound identity/provenance and exact multi-effect scope semantics in coordination with C01/C04, including signed/host-generated confirmation lineage and no model-managed grants.
- [ ] Define typed framed worker protocol (max sizes, timeouts, check fields, validation, response errors, cancellation, source hash/version).
- [ ] Freeze adversarial tests: unrelated file/credential denial; unauthorized writes; DNS/socket/loopback denial; all descendants terminated; inherited handles denied; symlink/reparse/SQLite sidecar escapes fail; malformed data rejected; revocations effective; crashing worker leaves no unauthorized effects.
- [ ] Freeze resource ceilings per operation (RAM, CPU/process count, wall time, IO/net) and performance baseline including worker startup overhead; prefer secure slower execution to insecure throughput.
- [ ] Validate on **actual Windows desktop** and representative non-admin accounts before asserting production-ready isolation; Linux sandbox dry-runs are not Windows evidence.
- [ ] Keep calculator/research worker inert until each risk is resolved. If security prerequisite fails, the operation is unavailable (honest fallback), not silently unconfined.

**Current result:** research and source inventory only. No new permissions, no worker privileges and no production CE execution were enabled.
