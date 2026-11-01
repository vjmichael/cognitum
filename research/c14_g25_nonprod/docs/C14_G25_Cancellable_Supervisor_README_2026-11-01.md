# Cognitum C14 G25 — standalone cancellable research supervisor

**Date:** November 1, 2026. **Scope:** Cognitum-only research. **No Lu integration. No Cognitum production registration or release authorization.**

This package introduces a research-only process supervisor around the **unchanged** G25 sensitivity reporter, guard and G25I statistical baseline. It is **disabled by default**. It adds local worker cancellation, hard timeouts, group cleanup and explicit result/refusal semantics; it does **not** change a single statistical estimator or make its confidence intervals generally calibrated.

## Start and message protocol

Requires Python 3.13, NumPy, SciPy and pytest; statsmodels is used for independent acceptance. Launch from the extracted root:

```bash
COGNITUM_G25_RESEARCH_OPT_IN=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python integration/g25_cancellable_supervisor.py --research-only
```

Input: UTF-8 JSON Lines. The supervisor accepts **exactly one active run** at once; each submitted request is passed to the existing v1 research host in a separate subprocess. For example:

```json
{"protocol_version":2,"type":"run","request_id":"case1","request":{"schema_version":1,"request_id":"case1","action":"c14.g25.sensitivity.report","counts":[[[67,35],[45,31]],[[75,30],[48,39]]],"gamma":0.25,"assumption_evidence":{"sampling_iid_supported":true,"consistency_supported":true,"measurement_validity_supported":true,"gamma_justification":"Pre-specified externally justified selection-difference limit"}}}
{"protocol_version":2,"type":"cancel","request_id":"case1"}
```

Output events: `accepted`, `result`, `cancellation_requested`, `cancelled`, `failed`, or `rejected`. `cancelled` is terminal and is emitted **after** the worker is reaped and the POSIX process group is killed. A request that already finished cannot be retroactively cancelled; late cancellation is rejected. Every event carries `research_only=true`, `automatic_causal_certification=false`, and `production_estimator_promotion=false`.

**Scientific distinction:** `result` means *the worker returned a verified host receipt*. The nested `response.host_status` is separately `completed`, `refused`, `invalid_request` or `internal_failure`. A scientific refusal carries no identified-set intervals; callers must inspect the nested status. A receipt SHA-256 checks accidental or adversarial mutation **only if the expected digest is secured independently**; it is not a MAC, executable identity certificate or permission grant.

## Run local verification

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python -m pytest -q tests/test_nonprod_host.py tests/test_g25_release_guard.py tests/test_cancellable_supervisor.py

# Each independent black-box batch has ten prespecified synthetic datasets;
# run separately to avoid container per-command timeouts.
for p in 0 1 2 3; do
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
    python tools/independent_supervisor_acceptance.py --part "$p"
done
python tools/audit_supervisor_parts.py
```

The independent harness **does not import the G25 baseline, candidate host, guard or supervisor implementation**. It runs the supervisor as a subprocess and computes candidate identified-set intervals using a separate formula with statsmodels exact beta-binomial confidence bounds. It checks every event and refusal, duplicate-ID rejection and hash. `results/` contains original synthetic requests and responses for all 40 cases, four part reports and aggregated audit.

## Isolation and limitations

- **Linux verified:** host-controlled new POSIX session/process group; killed/reaped stalled worker **and spawned descendant** in hostile-fixture test; bounded one-task admission, no late report after cancellation, timeouts, stream refusal, pinned source SHA-256 checks, explicit opt-in.
- **Not an OS sandbox:** subprocesses run as the parent user. No cgroup, Bubblewrap, seccomp, admin isolation or default-deny network security is claimed. The supervisor is a research lifecycle tool, not a safe executor of arbitrary third-party code.
- **Windows NOT verified:** `CREATE_NEW_PROCESS_GROUP` alone does **not** guarantee descendant termination or AppContainer isolation. Windows native Job Object containment remains an open gate for any distribution that needs it. No Windows executable or installer is included.
- **Not soft cancellation:** the mechanism is a bounded, hard worker termination. Cooperative in-flight checkpoint/rollback remains open. Possible effects must never be replayed as if they were cancelled before execution.
- **Performance:** spawning Python+SciPy afresh for every request incurred about 1.30 seconds/request in this local 40-case study. Suitable for research, not a low-latency service. No production throughput claim.
- **Scientific limitations:** prior G25J–N confidence-interval calibration/width gates failed and remain failed. Γ remains analyst-supplied; hidden confounding may be observationally untestable. No automatic causal certification.
- **Project independence:** no Lu files or Lu-Linux branches touched. The frozen G25 reporter/guard and default Cognitum registry/CLI remain unchanged. This is not a Cognitum-to-Lu bridge.

See `C14_G25_Standalone_Supervisor_Report.md` and `C14_G25_Standalone_Supervisor_Gates.json` for evidence and next Cognitum-only work.
