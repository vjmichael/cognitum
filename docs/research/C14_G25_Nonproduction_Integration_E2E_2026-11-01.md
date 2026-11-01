# Cognitum C14 G25 — Nonproduction integration and independent E2E acceptance

**Date:** 2026-11-01. **Outcome:** Nonproduction engineering acceptance **PASSED**; overall C14 G25 scientific/production promotion **NOT APPROVED**.

## Delivered integration

The existing pinned G25I conservative sensitivity bounds and pinned G25 research guard were reused **without changing their bytes**. Source SHA-256s:

- G25I `baseline/g25i_core.py`: `f881ae12bdae90fa4acec0bae9046e5580f5ddad80a1794006c3da5a3f6621e4`.
- Guard `tools/g25_release_guard.py`: `3480952a031d17061615eaa92597e7b2f0df22495954d5656aeeb6b51322f64c`.

A new disabled-by-default local JSON Lines capability process accepts an analyst-supplied binary W,T,Y table or strictly validated binary observations, Gamma and assumption documentation. It produces a conditional sensitivity report or explicit refusal, never a certified causal-effect claim. The protocol rejects duplicate keys and request IDs, unknown actions, malformed counts and Gamma, nonbinary observations, unbounded counts, malformed JSON and oversized lines. Each reply carries SHA-256-based replay evidence; it does not claim signature/authentication semantics.

A second adapter implements the real Cognitum `Registry`/`Runtime` research plugin contract. It is **not registered in `cognitum.__main__`**. Research operations require a trusted enabled registry entry, research-specific nomination and a host context with `allow_research=True`. It declares no effects, no causal assurance and no production routing. The native trial exercised **six unmodified Cognitum runtime source files, byte-for-byte checked against GitHub blob IDs**; the trial did not alter that production source or Lu.

## End-to-end acceptance (independent black-box harness)

The acceptance protocol was frozen before its held-out run (SHA-256 `8fee77828ee869d2dc20ab88bed8d65b1e3048099902113898707e08b730ad07`). Its independent harness imports **neither the candidate guard nor G25I**, launches the process under test, feeds original JSON input bytes, verifies request/semantic receipt SHA-256s and compares all successful intervals to independent SciPy HiGHS and statsmodels references.

| Metric | Verified outcome |
|---|---:|
| End-to-end JSONL exchanges | **980/980** |
| Archived G25N cases, 20 x 28 cells | **560/560** |
| Fresh synthetic cases (independent seed) | **420/420** |
| Conditional sensitivity reports | **650** |
| Observed missing-arm refusals | **151** |
| Sparse-arm policy refusals | **167** |
| Missing-assumption-evidence refusals | **12** |
| Total safety refusals | **330** |
| Invalid/duplicate-key/replay adversarial controls | **16/16 rejected** |
| Maximum difference vs independent LP+exact-beta math | **2.78e-16** |
| Automatic causal certifications | **0** |
| Production estimator promotions | **0** |

The native Cognitum research-route acceptance passed **8/8** scenarios: disabled registry, research admission denied, workspace identity mismatch denied, valid conditional report, nested scientific refusal, invalid schema rejection, dry run with no computation, and worker timeout with process cleanup on Linux. All six comparison module Git blob hashes match upstream exactly. Trace records contained only the existing closed metadata schema and no raw records.

The new integration/guard unit tests passed **45/45**. The unchanged G25L, G25M and G25N suites passed **22/22, 20/20 and 32/32**, respectively: **119 total local unit/regression tests passed**, plus independent black-box acceptance.

## Safety and limits

- An observed arm containing fewer than 25 cases is withheld under a conservative **research reporting policy**; it is not a structural positivity proof.
- The analyst's supporting evidence flags are external declarations, **not checked as scientific truth**. Hidden confounding can still produce superficially valid observations.
- The returned identified set is conditional on Gamma. Conservative outer confidence bands remain unsuitable for promotion under the previously failed precision/calibration gates.
- Runtime `execution_status=completed` means the research plugin process ran; always inspect its nested `host_status` and guard `status` to distinguish refused inference.
- No machine or OS sandbox is newly introduced by this adapter. The original Cognitum Worker uses disposable Python spawned processes. Linux timeout cleanup passed; **Windows process containment and in-flight soft cancellation are not yet verified**.
- The plugin was **not** attached to the installed/default Cognitum CLI. No Cognitum production code was modified and Lu was untouched.
- External R `logistf`/`brglm2` parity and independent scientific review remain unperformed. Neither this acceptance nor an exact-beta comparison closes those scientific gates.

## Gate decision

**PASS: isolated nonproduction process integration, native research capability interface against unchanged runtime modules, fail-closed input/refusal policies, replay receipts, 980-case independent black-box end-to-end acceptance, 8-scenario native route acceptance and local regressions.**

**OPEN/FAIL: actual installed distribution default-path integration (deliberately disabled), Windows Job Object containment, in-flight soft cancellation, confidence-interval scientific calibration/precision, external Firth equivalence, broad causal-model generalization, independent scientific review and explicit production authorization.**

No promotion of experimental G25J–N estimators; no production algorithm/behavior changes. This package is a **reviewable, executable research integration** awaiting broader validation, not a production release.

## Operational notes

During strengthened post-holdout adversarial testing, one test harness fixture meant to submit an invalid request ID accidentally overwrote that ID with a well-formed identifier. The mistake was discovered by requiring the exact expected refusal reason, repaired in the **test harness only**, and the full 980-case black-box evaluation rerun unchanged with **16/16** adversarial controls passing. A native acceptance harness also originally attempted to mutate a frozen `Request` dataclass; the harness was corrected to use `dataclasses.replace` before its successful run. Neither issue caused a candidate host/guard algorithm change. All original output receipts and the updated verification are archived.