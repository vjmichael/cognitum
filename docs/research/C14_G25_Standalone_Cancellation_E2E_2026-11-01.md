# Cognitum C14 G25 — standalone research cancellation and independent acceptance

**Date:** 2026-11-01  
**Status:** Research-only Linux lifecycle gate **PASS under tested conditions**, not production accepted. No Lu interaction, and no change to the default Cognitum runtime or production estimator.

## Goal

Close a previously open C14 G25 research lifecycle gap: the standalone sensitivity-reporting host was synchronously bound to stdin processing and could not accept a cancellation request while computing. This milestone adds an *independent optional supervisor* that can receive a cancel command during work, kill and reap the worker process tree on Linux POSIX, withhold late numerical results and preserve scientific refusal responses. It is **hard process cancellation**, not cooperative soft cancellation or rollback.

## Implementation

- New `integration/g25_cancellable_supervisor.py` accepts bounded v2 JSONL control frames, validates strict request identity/type, permits only one active worker, refuses duplicate IDs and enforces dual opt-in (`--research-only` and `COGNITUM_G25_RESEARCH_OPT_IN=1`).
- The worker is the unchanged pinned `integration/c14_research_host.py`; direct inputs are passed to that host with exactly the same scientific counts/Gamma/evidence. There is no arbitrary executable path in the wire protocol, no socket/network listener, and no automatic Cognitum plugin registration.
- Child environment contains only narrow research/Python runtime variables on Linux, not inherited arbitrary secrets/PYTHONPATH. Host/guard/baseline SHA-256s are independently checked before worker launch; this pins evidence, but SHA-256 is **not signed package authentication**.
- Each request gets a new POSIX process session; a cancelled/expired job is killed as a process group and reaped before a terminal `cancelled`/`failed` event. Late `result` is forbidden after accepted cancellation. Startup, timeout and worker-error paths are fail closed.
- All response receipts are checked for expected request/input hash, structural completeness, research-only flags, no certification, inner status and scientific refusal shape. Host result hash is not treated as an authority grant.
- Explicitly closes subprocess pipes on all exceptional paths.

## Independent results

| Evidence | Observed result |
|---|---:|
| Existing G25 host+guard regression tests | 45/45 pass |
| New cancellation, malformed-control, OS-tree and receipt tests | 23/23 pass |
| Total current local tests | **68/68 pass** |
| Independent subprocess E2E cases | **40/40 accounted for** |
| Successful conditional sensitivity reports | 32/32 numerically matched independent statsmodels oracle |
| Missing/sparse-arm scientific refusals | 8/8 with no intervals |
| Duplicate task-ID negative controls | 4/4 refused |
| Maximum interval/identified-set numerical discrepancy | **2.22e-16** |
| Automatic causal certifications | **0** |
| POSIX hostile descendant termination | PASS in local fixture |
| Default Cognitum runtime and Lu code modifications | **None** |

Tests run with Python 3.13, NumPy/SciPy, statsmodels, pytest and single-threaded BLAS. Black-box study time for four ten-case parts was 51.898 seconds (about **1.30 seconds per case**), largely import/process cost. The generated data are deliberately not a statistical calibration holdout: they verify the **transport does not alter existing scientific results**. They do not change G25's prior failed scientific width/coverage gates.

## Reproducibility and integrity

All four ten-case E2E parts include original requests, events, SHA-256 hashes and an immutable final source hash `1fad033b4871be412463be7b0236d98805bf003b65a5f4a5c21060812368eeb6`. `tools/audit_supervisor_parts.py` verifies every part, every accepted/terminal pair, no missing case, every refusal and all duplicate rejections. The first unchunked attempt and the later isolated supervisor cleanup fix are disclosed in `docs/Operational_Deviation.md`.

Original G25I baseline, original G25 release guard, and original C14 JSONL host remain byte-for-byte copies; no estimation algorithm changed. This is not an original statistical discovery, production package, alpha release, untrusted OS sandbox, or Lu DLC.

## Release-gate decision and next work

**PASS (scoped):** Linux research hard cancellation+descendant cleanup; independent supervised E2E numerical equivalence; strict opt-in; receipt and refusal preservation.

**OPEN:** true *cooperative* soft cancellation, Windows process tree (Job Object) and OS isolation, installed standalone Cognitum distribution acceptance, resource-consumption bounds before pipe capture for unexpected hostile worker output, multi-worker scheduling/throughput.

**FAIL unchanged:** broad G25 conditional confidence-interval width/calibration, unverified analyst Γ, false causal security from hidden confounding; remain research-only. External Firth-equivalence and independent scientific review also open.

**Next Cognitum engineering task:** after this lifecycle gate, work on installed standalone Cognitum development-distribution smoke tests and native capability routing, independent of any Lu branch or Lu extension system. Use Cognitum's own host/registry. Scientific algorithm promotion still requires separate evidence and user authorization.
