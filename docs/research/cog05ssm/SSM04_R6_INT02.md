# COG-05-SSM-04-R6-INT-02 — Native OS custody, host revision CAS and supervised SSM

**2026-11-21 native research qualification: ACCEPTED for Windows current-user DPAPI, local revision CAS and disposable supervised SSM mathematics; 5/5 native/evidence jobs PASS, 286 tests × 4 OS/Python platforms = 1,144/1,144 passed.** The accepted original tested source is d4afcf43257c919c216be7e3cce5c072140d1679; do not confuse with the later source-unchanged closeout commit. Linux GitHub kernel-keyring protection remains **UNAVAILABLE_FAIL_CLOSED** (not qualified), and full installed privileged Lu/MEL authorization/hardware anti-rollback is not claimed.

## Native credential custody

cognitum/mel/ssm_os_credentials.py implements two actual OS APIs, not a simulated broker.

- Windows: CryptProtectData / CryptUnprotectData, CRYPTPROTECT_UI_FORBIDDEN, per-current-user DPAPI, caller-owned trusted directory and encrypted credential ciphertext. Scope, session, subject, turn, namespace and stream ID are bound into optional DPAPI entropy. No fallback to plaintext, environment variables, machine-wide DPAPI, or silent key rotation. Same-user processes retain equivalent OS access; account ACL, actual installed service identity and protected privileged broker are not established here.
- Linux: real kernel USER keyring via libkeyutils add_key, keyctl_search, keyctl_read and keyctl_revoke. UID-wide keyring custody is not per-process; kernel keyring may be restricted or absent on managed runners, and keys are not reboot durable. If unavailable, the implementation explicitly refuses instead of persisting plaintext or simulating the service.
- The HMAC key remains borrowed in trusted Python memory during work. No isolated credential-broker service, nonexportable key, or zeroization guarantee is claimed.

## Revision custody

cognitum/mel/ssm_revision_cas.py uses a separate pre-created, owner-protected SQLite DB, FULL synchronous mode, immediate write transactions, HMAC-sealed revision plus checkpoint digest records, and optimistic revision/digest compare-and-swap. It binds authority records to exact MEL scope, namespace and stream ID, checks signatures with OS-borrowed keys and refuses stale writes, data forgery and key mismatch.

**Limitation:** this is an authenticated local CAS, not an independently authoritative TPM/hardware/remote monotonic counter. A trusted account with the ability to delete/restore the entire authority DB can defeat historical anti-rollback; power-loss guarantees and whole-store deletion detection require a stronger host-protected root of trust. Do not describe the local file as production anti-rollback authority.

## Supervised compute

cognitum/mel/ssm_supervisor.py uses the preexisting cognitum.worker.execute disposable spawned process and its bounded timeout/termination path for pure R5 SSM fixed-duration advancement. The child receives only unkeyed bounded numeric state and an observation increment/watermark, not keys, DB paths, grants or authorization material. The host validates the child's model identity, output shape, causal cutoff, state progress, release count, QR covariance and memory budgets. The parent alone signs the next R6 checkpoint and coordinates the SQL event/outbox journal.

cognitum/mel/ssm_recovery.py adds optional supervised_math=SupervisedSSMCompute(...) to the existing HostSSMJournal. This preserves existing MEL Admission and Scope checks, affirmative host authorization/revocation, and signed transactional journaling. Existing direct-math journal API remains unchanged by default.

**Limitation:** a managed Python subprocess is NOT an OS sandbox, protected Windows AppContainer/Job worker, protected Linux cgroup worker or an installed approved model-facing MEL SSM operation. No new registry plugin, Lu IPC protocol, general model tool, or independent host authority is introduced here.

## Qualification and evidence

One exact-source branch-scoped native batch on genuine GitHub Windows/Ubuntu Python 3.11/3.13 runs accepted SSM and MEL admission suites plus R6-INT-01 journal tests and new R6-INT-02 native tests. Preserve original JUnit, all pinned Git blob hashes, original SHA and OS native custody probe output from every runner. A fifth independent job compares all evidence. After passing, retire the one-time automatic push trigger without changing the mathematical/OS source.

The separate research_tests/mel_ssm_r6int02/native_probe.py genuinely provisions, borrows, revokes and checks OS credentials, then verifies native-bound local revision CAS. Windows DPAPI is required to work. Linux genuine kernel keyring is qualified only if permitted by the OS; unavailable means an explicit OS_KERNEL_KEYRING_UNAVAILABLE_FAIL_CLOSED, not a successful keyring qualification.

New tests verify actual subprocess execution and deterministic R5 result agreement, forced supervisor timeout, forged child response refusal, local CAS transaction/restart/forgery/stale revision checks, actual OS-backed key lifetime and revocation where available, native Windows DPAPI ciphertext tamper denial, and host journaling with a real MEL Admission and supervised numeric worker. The accepted original test suites must remain green.

## Production security gates still open

1. Actual Windows service account/ACL and physical DPAPI credential test, installed Job/AppContainer protected subprocess, restart/power-loss.
2. Linux privileged service/keyring rules, fail-closed kernel refusals and reboot-safe provisioning, actual cgroup/LSM custody.
3. Independent hardware/remote monotonic revision authority, whole-DB deletion and rollback auditing, external delivery idempotency.
4. Reviewed typed SSM MEL Protobuf route under existing Runtime and installed Lu authorization; no model-facing authority before genuine admission.
5. Verified protected installed cancellation, revocation, recovery and output custody.

## Accepted original exact-source native and independent evidence — 2026-11-21

- **Original fully passing GitHub Actions run:** [#44916524626](https://github.com/vjmichael/cognitum/actions/runs/44916524626), head SHA d4afcf43257c919c216be7e3cce5c072140d1679, attempt 1; **five original jobs succeeded**.
- Ubuntu Python 3.11 **286/286**, Ubuntu Python 3.13 **286/286**, Windows Python 3.11 **286/286**, Windows Python 3.13 **286/286**; aggregate **1,144 passing tests**. Original R3/R4/R5/R6 and R6-INT-01 regressions were retained. Every native JUnit includes exactly **12 new R6-INT-02 cases**, zero failed/errored/skipped.
- **Real OS credential native evidence:** BOTH original Windows jobs actually provisioned/decrypted/revoked secrets via the Windows DPAPI current-user API, then round-tripped the HMAC-authenticated independent local revision CAS. BOTH Ubuntu jobs observed a Linux kernel keyring read/provision refusal: no usable kernel-held key or native CAS; explicit OS_KERNEL_KEYRING_UNAVAILABLE_FAIL_CLOSED with no software fallback. This is a known **partial OS custody** result, not a Linux security PASS.
- **Original fifth CI job:** independently compared four exact original commit SHA receipts, all 22 pinned prior/new source/test/worker Git blobs, 286 identical original (classname,testname) pairs and native OS probe identities; it emitted PASS_SUPERVISED_SSM_AND_OS_NATIVE_CUSTODY_DISPOSITIONS.
- **Further separate outside-CI audit:** downloaded all five original GitHub Actions artifact ZIPs through the connector; independently checked their ZIP SHA-256 against original GitHub metadata, ZIP CRCs, four JUnit contents and unique case IDs, original source Git blob and commit identity, the Windows/Linux native OS disposition records and original independent job JSON. Evidence inventory: [SSM04_R6_INT02_NATIVE_ARTIFACTS.json](SSM04_R6_INT02_NATIVE_ARTIFACTS.json).
- **First unsuccessful run #44916310428:** original Ubuntu key creation could succeed while key reading was refused, but provisioning had not yet enforced a read-back check; original Windows DPAPI ciphertext test mutated ignored/noncritical bytes. Corrected in ONE consolidated successor by requiring Linux provision/read verification with revocation/refusal on failure, adding a versioned SHA-256 whole-file integrity envelope around protected DPAPI ciphertext, and updating the exact source hash. No Python mathematics or accepted MEL admission/grant code changed.
- **Retired one-time CI:** the R6-INT-02 branch-scoped push trigger was converted to manual-only workflow_dispatch in a single documentation/evidence/CI-control-only [skip ci] closeout commit. The green accepted source remains the immutable exact SHA above. No automatic replacement workflow or branch merge.

### Acceptance limit

The host integration is only qualified for actual Windows DPAPI current-user OS protection and authenticated local revision CAS, and for research disposable subprocess computation on Windows/Linux. **Not accepted:** protected installed Windows service/SCM/AppContainer/Job custody; Linux kernel-keyring custody on those CI runners; physical Linux kernel-policy provisioning; independently authoritative hardware/remote monotonic anti-rollback; full SQLite deletion/restore resistance; external exactly-once delivery; installed typed MEL Protobuf route; Lu broker grants or production authorization.

**Next engineering task:** COG-05-SSM-04-R6-INT-03 — qualify installed OS service custody and independent trusted revision authority; finish Windows protected worker and provision/qualify Linux keyring on a real installed host; then implement a reviewed MEL SSM Protobuf route under Lu-owned authorization.
