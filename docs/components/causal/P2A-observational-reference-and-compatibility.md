# C14 P2A — Typed Observational Reference Estimation & P0 Compatibility

**Date:** 2026-10-27  
**State:** Implemented bounded mathematical reference, **not complete C14 P2**, not DoWhy runtime, not verified real-world causal identification, not production Lu host capability.
**Source basis:** C14 P1 checked archival baseline, P0 Architecture Addendum v1.1.

## 1. Backward compatible schema migration matrix

| P0 demanded semantics | P1 existing contract | P2A action | Deferred / prohibited shortcut |
|---|---|---|---|
| Exact finite SCM, DAG, shared exogenous | `cognitum.causal.v1/scm.proto`, fixed tables | Preserve original source and binding byte-for-byte | Do not reinterpret P1 exact labels for statistical claims |
| Observational/`do`/counterfactual separation | `CausalOperation` and `CausalResult` | Untouched; dedicated `estimation.proto` operation | Never turn conditioning into intervention |
| Graph backdoor sufficient check | `CausalRequest` BACKDOOR_CHECK, `CausalReceipt` | Require and independently reconfirm before observational adjustment | Failed backdoor is not universal proof of nonidentifiability |
| Dataset representation | None | New typed `FrequencyRow` and `EstimationRequest` | Missingness/mixed continuous/external dataset handles require v2 design |
| Effect estimation | None | Bounded exact-rational empirical standardized binary risk difference | Not frontdoor, IV, general ID, matching or DML |
| Statistical uncertainty | None | Labeled approximate 95% normal plug-in interval | No coverage guarantee or Bayesian credible interval |
| Sensitivity/refutation | None | Deterministic leave-one-stratum-out range (fragility only) | Not DoWhy placebo test, negative control, hidden-confounder sensitivity |
| Experimental model families | P1 finite tables only | Reserve unchanged existing exact fallback | Graph discovery, CPDAG/PAG, temporal/neural/Bayesian SCM need versioned future contracts |
| Runtime backend selection | P1 fixed enumerator | New backend enum; optional DoWhy selected as explicitly unavailable | No import, execution, shell/script or false fallback to DoWhy |
| Security and provenance | P1 host flags, digests, audit | Distinct defaults-off host flags, digest-bound verified computation, metadata-only audit | No authenticated Lu, OS confinement or user-action authority |
| Benchmark & research readiness | C03 planned hooks | 24 mathematical/negative tests; independent effect reweighting, replay-proof receipts | No comparative benchmarks/real-data validation |

`estimation.proto` **adds** messages/enums under `cognitum.causal.v1` without changing field/tag numbering in `scm.proto`. Existing P1 consumers remain valid. Future incompatible model families shall use a versioned schema and feature negotiation.

## 2. Exact implemented estimand and assumptions

For binary treatment T, binary outcome Y, and user-supplied observed adjustment set Z passing the *sufficient* backdoor criterion in the **supplied** graph, the reference estimates the empirical standardized risk difference:

    RD_hat = sum_z P_hat(Z=z) [ P_hat(Y=1 | T=1,Z=z) - P_hat(Y=1 | T=0,Z=z) ]

All probabilities are exact rational expressions of aggregate counts. This is a sample statistic. Interpreting it as a causal ATE requires a justified graph plus exchangeability given Z, consistency, positivity, correct measurement/sampling, and other application-specific assumptions. Passing the graph criterion **does not establish** those assumptions in reality.

Implemented support: binary T/Y, finite observed covariates in a static finite graph; fully observed fixed-width endogenous state rows aggregated as frequencies; 1–384 distinct input rows, <=200,000 total occurrences, <=128 observed adjustment strata; at least 2 observations per treatment arm/stratum and bounded maximum request/time. Duplicated row tuples are rejected to prevent accidental double counting. No raw personal information is included in audit records; raw source is never logged there.

Identification and estimation are separate: a passed graph criterion is an assumption-bound graph result; overlap checked from counts is observed sample support; the exact rational risk difference is empirical estimation. The independent verifier reproduces the effect via a separately formulated inverse-probability reweighting calculation, and validates all typed outputs. This independently verifies *arithmetic and receipt consistency*, not underlying causal truth.

## 3. Uncertainty and robustness

- `standard_error`: normal approximation with empirical Bernoulli plug-in variance, weighted over strata; `ci95_*` are *approximate*, not causal or Bayesian guarantees. Coverage is unreliable in tiny samples or certain extreme probabilities; no exact binomial confidence coverage is claimed.
- `leave_one_stratum_out_min/max`: recomputed effects with each covariate stratum removed and the remaining sample distribution re-standardized. This indicates one form of sensitivity to sample composition, **not** a test of confounding or a causal refutation.
- Strict empirical overlap checks fail with `POSITIVITY_NOT_MET`, without silently dropping or smoothing unsupported strata. The minimum per-arm count is explicit in each request.
- DoWhy is not installed/executed in this checkpoint. `DOWHY_OPTIONAL_WORKER` always yields `ESTIMATION_BACKEND_UNAVAILABLE` with `DOWHY_WORKER_NOT_INTEGRATED` rather than making an estimate.

## 4. Mature backend P2B integration research dossier

- DoWhy public 0.14 documentation separates graph identification, treatment-effect estimation, and robustness/refutation (https://www.pywhy.org/dowhy/); PyPI 0.14 was released 2025-11-08, license MIT, Python >=3.9,<3.14 (https://pypi.org/project/dowhy/0.14/). DoWhy is a candidate optional host-isolated pinned implementation; packaging, transitive licenses, Windows x86-64 process restrictions, and exact API pin require runtime verification.
- P2B shall implement an **actual DoWhy process worker** only after host-side executable and worker hashes, interpreter version and dependency pin, no-network/FS policy, memory/time kill, cancellation, and return-channel validation are in place. Unavailable workers remain unavailable. Observational identification, estimation and refutation must be reported as distinct typed evidence with separately checked limits.
- Frontdoor and instrumental-variable support require method-specific identification assumptions and independent witness fixtures; do not back-fill those operations through a backdoor-only reference.
- `C13` posterior interface, `C03` benchmark wire bridge, and `C02` host OS gates are design requirements only here: no wire interop, real-model bench, Windows installer, or authenticated Lu test has passed.

## 5. Verification and limitations

To test: `PYTHONPATH=.:tests python -m unittest tests.test_c14_estimation tests.test_c14_causal -q`, `PYTHONPATH=. python tools/run_c14_smoke.py` and `PYTHONPATH=. python tools/verify_protobuf_schemas.py --require`. Counts and environment captured in P2A-functional-test-evidence.json. Legacy full-suite execution can be slow/stall and is never summarized as passed without completion.

**Next engineering milestone: C14 P2B** — actual DoWhy pinned isolated worker; frontdoor/IV and ID where genuinely supported; policy/assumption and overlap diagnostics; statistical estimation/refutation; controlled data provenance; cross-checks and hard-fail cases. Preserve this bounded P2A oracle and all P1 tests.
