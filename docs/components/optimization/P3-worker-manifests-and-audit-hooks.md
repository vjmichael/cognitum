# C11 P3 — Capability manifests, OS-process deadlines, experimental slots and benchmark-ready receipts

**Milestone:** C11 P3, 2026-10-27 (offline Python/Linux reference, not installed in Lu).

## Standards and library inventory

C11 P1–P2 already use SciPy/HiGHS for integer-linear optimization, assignment, packing and scheduling; NetworkX for min-cost flow and feasible routing; and an optional, unexecuted Google OR-Tools CP-SAT adapter. This phase reuses those mature implementations, does not rewrite an optimizer, and adds runtime infrastructure. Official upstream references: [HiGHS](https://highs.dev/), [OR-Tools CP-SAT](https://developers.google.com/optimization/cp), [OR-Tools scheduling](https://github.com/google/or-tools/blob/stable/ortools/sat/docs/scheduling.md), [SciPy milp](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html), [NetworkX simplex](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.flow.network_simplex.html). Verify license and redistributable dependency closure per Windows bundle before shipping.

## Implemented interfaces

- `proto/cognitum/optimization/v1/runtime.proto` contains `CapabilityManifest`, `BackendCapability`, `ExecutionRecord` and `ExecutionEnvelope`, compiled into checked-in `cognitum.proto.optimization_runtime_pb2` and independently compared with `protoc`. Protobuf only, no JSON on native invocation boundaries.
- `cognitum/optimization_runtime.py` advertises mature capabilities with fixed workflow-kind and backend-ID mappings. The two research entries are **metadata-only, not runnable**: neighborhood search and learned branching. They do not claim results, efficacy or a validated implementation, and require future DOI/source, host review, explicit opt-in and separate benchmarks.
- The host-configured `WorkerPolicy` binds the worker script path and expected SHA-256 digest; request Protobuf cannot supply executable paths, scripts, shell strings, opt-in or authorization. `OptimizationWorkerRuntime` starts a fresh Python `-I` subprocess for a single workflow. Only the fixed native worker entrypoint `tools/c11_worker.py` is expected in the baseline. Its code must be pinned in a trusted install manifest; `fixed_worker_policy()` computes a local digest for development convenience, **not an authenticated trust root**.
- A monotonic host-observed deadline and manual cancellation stop the worker; `disable()` rejects future work and kills active subprocesses. Linux/POSIX attempts to kill the entire spawned process group. Windows presently calls `proc.kill()` on the immediate process: native Lu **Job Object** enforcement and security supervisor are still required for descendant-process trees and OS resource ceilings.
- The worker can return only the original bounded `WorkflowResult` frame. Parent independently revalidates it with the P2 `verify_workflow_frame` checker; any forged SAT/optimality assurance fails closed. Receipt and result digests, checked backend and observed wall time are placed in a data-minimized `ExecutionRecord` without raw user data. `verify_execution_shape` checks message consistency and re-runs the P2 verifier. **The record does not authenticate the host**, prove a machine actually executed work, or represent an externally signed audit log.
- This Protobuf envelope is *benchmark-hook-ready* for Lu's separate host-runner design; it exposes correlatable `trace_id`, request/result/receipt hashes, backend/version, operation kind, wall time, cancellation/deadline and outcome. No actual Lu benchmark schema wire adapter, model benchmark run, hardware/energy measurement or production collector is implemented or implied.

## Threat model, safety and known gaps

- **No authenticated Lu host grant.** `host_authorized=True` is a synthetic test flag, not an OS or Lu credential. Run only behind a trusted native Lu permission/service broker when integrated.
- **Not an OS sandbox.** `python -I` isolates environment import paths, but does not confine files/network or system calls. POSIX process groups provide coarse kill behavior; on Windows use Job Objects and locked-down restricted tokens. Current worker loads third-party native libraries inside a child process, and resource limits are only deadlines, not memory/CPU ceilings.
- Worker digest is checked just before spawn, not atomically bound to the executed handle (TOCTOU). Future trusted launch must pin and verify the immutable bundle/runtime, block writable worker paths, attest expected library dependencies, and manage descendant processes. A hash alone is not a signature.
- The legacy P2 solver uses synchronous numerical libraries. Cancellation kills the **subprocess** instead of interrupting unsafe in-process code; a timeout cannot certify infeasibility or optimality.
- `execution_shape` verification is purely structural, not signed evidence and not proof of wall times. SHA-256 digests are identifiers, not confidentiality protections. Raw request/result frames may be sensitive; do not persist the envelope itself without Lu retention policy.
- SciPy/NetworkX exercised on Linux. OR-Tools not installed here, Windows x86-64 package and native Rust/C02 admission not tested. Host-pinned research backends are *not installed*. No major benchmark campaign, learned-solver comparison or production promotion.

## Functional smoke and verification

```bash
PYTHONPATH=. python tools/verify_protobuf_schemas.py --require
PYTHONPATH=. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python tools/run_c11_p3_smoke.py
PYTHONPATH=.:tests OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python -m unittest -q tests.test_c11_p3_runtime
```

Unit tests cover model-controlled backends rejected by fixed catalog, metadata-only research names, modified worker hashes, missing grants, disabled registry, real 5-family child executions, external cancellation, deadline kill, in-flight `disable()`, nonzero exit, invalid result, forged receipts and assurance claims. The exact evidence is in `P3-functional-test-evidence.json`.

## Later Lu integration and full benchmark phase

Lu's native host must issue the real grant, pin an immutable Windows x86-64 executable bundle, enforce Job Objects, resource/memory quotas, policy-scoped data access, stdout frame bounds, cancellation and retention, and sign/version any durable collector records. At the final benchmark phase, pair C11's established baseline and installed experimental backends using the same typed cases, objective semantics and budgets. Compare feasible/optimal quality and independent proof level separately from runtime/resources, with explicit failure/kill criteria. No such comparison has been run in P3.

**Next active component:** C12 Planning and Search; C08/C09 remain archived/deferred.
