# COG-LU-IPC-01E-R2-INSTALLED-R3 — Installed-host prerequisite source closeout

Date: 2026-11-21. **PASS_NATIVE_PREREQUISITES_SOURCE_ONLY / BLOCKED_REAL_INSTALLED_HEALTH_AND_WORKER.**

## Exact source and independent evidence

- Cognitum accepted source: `6f6cff40c4f8c3fb46dc65ce04e30d943b262c00` on existing `integration/cog-lu-ipc01e-r2-custody-20261121`. Original [native run 44931910090](https://github.com/vjmichael/cognitum/actions/runs/44931910090): four independently hosted Windows/Ubuntu Python 3.11/3.13 suites, **209 tests each, 836 total, zero failures/skips; all 5 jobs PASS**, including the independently reconciled JUnit identities and original three source Git blob hashes.
- Original [C01–C19 integration run 44931910018](https://github.com/vjmichael/cognitum/actions/runs/44931910018): **8/8 jobs PASS**, Windows and Ubuntu, Python 3.11/3.13; baseline combined-tree regressions and full optional dependencies.
- Source-only follow-on documentation/CI trigger removal does NOT requalify any newer commit. Retain the original SHA in evidence, not the later branch head.
- Detailed artifact IDs and SHA256 digests: `COG_LU_IPC_01E_R2_INSTALLED_R3_EVIDENCE.json`.

## Cognitum-owned changes

1. `lu_ipc_install_host.probe_enrolled_core_health`: strict native `OSCredentialBroker` and original MEL `Scope`, precheck pinned Windows process/pipe identity or Linux UID/UDS path, then borrow a *preexisting* Win32 DPAPI or Linux kernel-keyring key. No auto-provision, environment key, model decision, prompt, IPC-sourced key, initial PIN inference, HTTP/TCP or hidden Core fixture. The existing authentic Protobuf HMAC Health client remains the only call. This function continues to refuse any `PASS_INSTALLED` or unauthorized release/ACK/model tool grant returned by a source-only responder.
2. `lu_ipc_windows_job_probe.WindowsFixedJobProbe`: actual Win32 CreateProcessW `CREATE_SUSPENDED`, fixed vetted Python diagnostic executable hash, private kill-on-close/active-process-limited Job, Job assignment and OS `IsProcessInJob` check *before resume*, kernel wait/termination and Job accounting emptiness verification on positive and timeout paths. The diagnostic only runs two fixed sleep commands and is **not** a model/SSM production worker, SCM-installed service or a signer/publisher witness. No arbitrary command input and no success fallback to an uncontained process.
3. Linux reuses existing verified `cgroup2_contract.preflight`, reporting real delegation refusal without creating or pretending to install a cgroup. The earlier fixed alpha worker/watchkeeper experiment is NOT yet connected to installed MEL SSM operation custody. No root/daemon or CI fixture establishes production Linux service custody.
4. New tests cover no broker/no implicit enrollment, bad OS peer pin refusing before key borrow, real native OS credential lending when available, failure to promote a mock Health to installed authority, Linux kernel cgroup readiness without SSM admission, and actual Win32 Job lifecycle, timeout/reaping, wrong-publisher-image digest and fixed-command refusal.

## What has NOT been accepted

- Lu Core #245: an actual separately installed, Core-owned, signer/OS peer-attested Health endpoint and Cognitum service enrollment are **still missing**. No real installed Core Health response was observed.
- Lu Core #248: no accepted Cognitum Core-issued original signed terminal receipt/issuer format, original per-turn PURE_COMPUTE SSM grant, revocation/outbox release and authenticated recipient ACK.
- Cognitum: no signed installed package/SCM service with OS-held enrollment, no verified installed **SSM** worker creation under Windows Job/cgroup *with durable independent stop receipt*, no independent hardware/remote revision floor and no protected output delivery.
- Win32 DPAPI-current-user and Linux UID-owned user keyring are native host-local custody, not full installed signer/credential-isolated service proofs. Linux keyring denial remains legitimate fail-closed behavior. The Windows diagnostic Job is real kernel lifetime control but is not an AppContainer or per-worker filesystem/network sandbox.
- A test-side fake Core Health report, local HMAC or Ed25519 provisional issuer key must NEVER become production authority or an installed PASS flag. No live tool, model, effect, delivery or ACK was enabled.

## Next engineering task

**COG-LU-IPC-01E-R2-INSTALLED-R4 — Connect the native OS-protected Windows Job and delegated Linux cgroup worker custody to Cognitum's fixed SSM MEL operation, with installed package/SCM/service enrollment, exact-original operation binding, durable terminal kill/restart proof and fail-closed host authorization.** Qualify genuine Core Health only after #245's supported installed endpoint and #248's reviewed enrollment/issuer contract are published. Avoid launching a second Core server or stacking CI before one consolidated accepted candidate.
