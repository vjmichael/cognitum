# CH-C14-03 — Pinned G25 source restored and retested on Linux

**Date:** 2026-11-02  
**Status:** **NONPRODUCTION ENGINEERING RETEST PASS; scientific production promotion NOT APPROVED.**  
**Scope:** Cognitum G25 research only. No Lu, Windows, or production causal estimator changes.

## Restored original source

Recovered the original archived source from two Library release archives:

- `Cognitum_C14_G25_Nonproduction_E2E_2026-11-01.zip`: **35/35 original manifest entries matched**.
- `Cognitum_C14_G25_Standalone_Cancellation_E2E_2026-11-01.zip`: **28/28 original manifest entries matched**.

Source contents match both the connected repository and the supervisor's frozen whitelist:

| Source file under `research/c14_g25_nonprod/` | SHA-256 |
|---|---|
| `baseline/g25i_core.py` | `f881ae12bdae90fa4acec0bae9046e5580f5ddad80a1794006c3da5a3f6621e4` |
| `tools/g25_release_guard.py` | `3480952a031d17061615eaa92597e7b2f0df22495954d5656aeeb6b51322f64c` |
| `integration/c14_research_host.py` | `74a717da88139c1a894e7d754a1dc702f5e328337ee2109017313c6a3aa2681c` |
| `integration/g25_cancellable_supervisor.py` | `1fad033b4871be412463be7b0236d98805bf003b65a5f4a5c21060812368eeb6` |

The supervisor hash matches the earlier G25 standalone report; the first three are its pinned dependencies. Archived README and manifests are not interchangeable and were verified separately.

## Fresh local tests

| Suite | Result |
|---|---:|
| Original guard tests | **22/22 PASS** |
| Original JSONL host tests | **23/23 PASS** |
| Original cancellable supervisor tests | **23/23 PASS** |
| **Original G25 unit tests subtotal** | **68/68 PASS** |
| New CH-C14-03 independent fault-injection cases | **8/8 PASS** |
| Four-part independent black-box supervisor E2E | **40/40 accounted for** |
| Independent receipt and numerical audit | **PASS** |
| Previous P17/P18 tests (different component, not G25) | **16/16 PASS** |
| New replay-driver integrity self-tests (not G25) | **4/4 PASS** |

The original full black-box replay was broken into four 10-case parts because the aggregated launcher exceeded this local command execution limit. The completed replay gave **32/32 matched conditional numerical reports, 8/8 proper scientific refusals, four duplicate task ID rejections, zero automatic causal certifications**, and a maximum independent statistical-oracle difference of **2.22e-16**. The original `tools/audit_supervisor_parts.py` independently verified **all receipts**, request coverage and source hashes.

## Explicit negative tests

- **Cancellation:** valid POSIX in-flight process-group and descendant cleanup, timeout reaping, no late response, cancel-before-launch, busy and duplicate denial (original supervisor suite).
- **Assumptions:** missing Gamma, unsupported consistency or measurement assumptions, missing evidence => refusal or invalid request, never a certification.
- **Missing/malformed data:** empty arm, sparse arm, malformed binary observations/counts and JSON => fail closed; no interval on refusal.
- **Numerical failure:** injected backend exception => `internal_failure`, no numerical result and no leaked exception.
- **Provenance:** source SHA pins, archive manifests, receipt replay and tamper/rehashed-forgery rejection. SHA receipts are **not** MACs or authorization.

## Still-open engineering/scientific gates

- The supervisor's `communicate()` can buffer more worker stdout than `MAX_WORKER_OUTPUT=65536` before the response cap is checked. This **unbounded pipe buffering remains open**; no resource-budget guarantee claimed.
- Linux POSIX group cancellation is not cgroup v2 kernel containment or cooperative soft cancellation/rollback; Windows Job Object containment remains deferred.
- G25N **failed 12/12** scientific interval-width/calibration cells. Analyst Gamma cannot prove causal identifiability; full LR inversion, externally validated Firth equivalence, numerical certification and independent scientific review remain open.
- **No production algorithm promotion or Lu changes**.

## Reproducibility artifact

Local artifact `Cognitum_CH_C14_03_Pinned_G25_Restored_Retest_2026-11-02.zip` contains the pinned reconstructed-by-extraction (not rewritten) research source, tests, black-box request/result receipts, independent audit, SHA-256 manifests, replay driver, and full engineering report. All 66 artifact payload hashes were independently checked after packaging.

The result is a scoped **engineering acceptance**, not a causal-inference scientific release.
