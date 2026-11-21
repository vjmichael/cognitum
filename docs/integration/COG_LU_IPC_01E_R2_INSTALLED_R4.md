# COG-LU-IPC-01E-R2-INSTALLED-R4 — Fixed SSM native worker custody and durable hold

Date: 2026-11-21. **PASS_SOURCE_NATIVE_FIXED_SSM / INSTALLED CORE and SERVICE acceptance BLOCKED.**

## Exact immutable evidence

- Original source: `fad39fb0e29fe83f2483f8106c3bf8fd66ae72aa` on existing `integration/cog-lu-ipc01e-r2-custody-20261121`.
- [R4 native run #44933418268](https://github.com/vjmichael/cognitum/actions/runs/44933418268): **5 of 5 jobs PASS** (Windows and Ubuntu, CPython 3.11/3.13 plus independent evidence job). Each OS/Python environment passed 215 tests: **860/860 total**, no failed/error/skipped cases.
- Independent fifth job: 4/4 original source SHA matches, 4/4 original Git blob lists for changed files, all original JUnit test identities identical, pinned Lu/Cognitum generated Protobuf verification, explicit no installed authority.
- [C01-C19 integration run #44933418142](https://github.com/vjmichael/cognitum/actions/runs/44933418142): **8 of 8 jobs PASS**, Windows/Ubuntu, Python 3.11/3.13, combined tree and all optional extras.
- `COG_LU_IPC_01E_R2_INSTALLED_R4_EVIDENCE.json` records source, run IDs, original artifact hashes and exact scope limitations. This documentation-and-CI-trigger closeout is **not** an independent test of its own follow-on SHA.

## Cognitum-owned work integrated

1. `cognitum/mel/ssm_r4_protected.py` introduces a **fixed one-event SSM process executor**, not a new Lu tool or permission service. The only child operation is the existing `ssm_supervisor.SSMComputeFactory.handle(OP,payload)` and only unkeyed numerical JSON enters a child; the parent retains all scope, user-turn, HMAC, SQLite/outbox and authorization custody.
2. The existing `SupervisedSSMCompute` accepts an optional **exact reviewed `ProtectedFixedSSMExecutor` object**; the existing `HostSSMJournal.process` supplies the trusted original MEL scope, stream and event. Wrong origin, workspace, turn, Core session, event, stream, backend or repeated operation is refused before releasing a child request. Normal preexisting disposable-worker path remains available for local research but remains **not installed OS-custody-qualified**.
3. Windows: actual `multiprocessing.spawn` **trusted fixed process** starts blocked on a private Pipe; host creates a private kernel `JobObject`, configures kill-on-close and active-process limit, requires real kernel `AssignProcessToJobObject` and `IsProcessInJob` **before releasing numerical input**, observes exit and `QueryInformationJobObject` empty accounting after Job termination. The trusted Python bootstrap starts **before** Job assignment (unlike fully suspended CREATE_SUSPENDED placement); thus this is **not protected worker-from-birth, hostile-code sandbox, installed SCM custody, AppContainer or publisher proof**.
4. Linux: reuse existing kernel cgroup-v2 `FixtureCgroupScope`, `arm_watchkeeper`, pidfd/start-ticks check, durable `host_recovery.record_before_worker_release`, attach-before-numerical-release, watchkeeper kill and scope-empty cleanup, then `mark_closed_after_verified_cleanup`. No Linux worker is spawned if real delegated cgroup preflight refuses. **CI Linux tested the explicit refusal branch**, not a genuinely delegated cgroup positive. Independently delegated Linux/QEMU acceptance remains necessary.
5. Durable one-use `DurableOriginalWorkerClaim`: strict original Protobuf OriginRefs + MEL Scope/Core session and fixed stream/event identity; borrow a genuinely OS-held credential from `OSCredentialBroker` in trusted host, write HMAC-bound prelaunch JSON once with fsync and O_EXCL in an existing private host directory, withhold the result if kernel stop is unobserved. Local stop record is written only after native cleanup. On restart, absent stop stays **UNCERTAIN requiring independent stop reconciliation**; even present local stop does not allow automatic reexecution, effect permission, result release or ACK.
6. Existing R6 journal alone owns authenticated next checkpoint, monotonic local CAS, duplicate request detection, output outbox and commit. R4 tests exercise actual Windows fixed numerical worker and R6 restart duplicate refusal with no publication; Linux tests expose unavailable delegation without silently falling back to unconstrained spawning.

## Limits / still blocked

- Lu Core issues [#245](https://github.com/vjmichael/Lu-AI-GUI/issues/245) and [#248](https://github.com/vjmichael/Lu-AI-GUI/issues/248) remain upstream issuer/enrollment/installed endpoint prerequisites. This is not a real Lu Core-supplied typed/authorized PURE_COMPUTE operation or real installed Health response.
- No separately signed and installed Cognitum package, Windows SCM broker-owned worker-from-birth, installed Linux service manager/delegation, externally managed independent stop receipt, independently anchored monotonic antirollback counter, or physical machine's crash/power-loss restart acceptance.
- HMAC local launch records and Linux watchkeeper JSON cannot provide independently signed OS authority; privileged local file rollback or same-account compromise remains outside the proven trust boundary.
- Windows OS Job kill and Linux cgroup kill are process containment of **fixed trusted math**, not user-code filesystem/network sandbox. There is no permission to operate as a model tool, publish R6 outputs or acknowledge a recipient.
- Native acceptance is limited to the tested exact original source. No claim that Windows/Linus installed publisher identity has been admitted.

## Next engineering task

**COG-LU-IPC-01E-R2-INSTALLED-R5 — Qualify physical/installed Windows SCM worker-from-birth and Linux delegated-cgroup/host-watchkeeper recovery, establish independently signed stop and antirollback receipts, then perform the first authenticated real Lu Core Health exchange once #245/#248 publish Cognitum endpoint/enrollment.** Keep source test and installed authority distinct and do not stack CI.
