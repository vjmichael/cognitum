# Cognitum C14 P4E G3 — Tigramite synthetic-ground-truth evaluation and causal-worker launcher parity

**Date:** 2026-10-28  
**Status:** Genuine Tigramite 5.2.10.1 Linux source-runtime study; G3 synthetic acceptance **not** scientific validation or production release.  
**Parent:** `Cognitum_C14_P4E_G2_Genuine_Tigramite_Runtime_2026-10-28.zip` SHA-256 `980d9145637faff49fa02eb3896533a4fb1065b180fabd722425d187ee6b560c`.

## 1. Why G3 exists

G2 established a real local Tigramite runtime with two seeded fixtures and preliminary independent-noise controls. This milestone adds a **reproducible multi-seed study with known generating equations** and stress scenarios violating causal discovery assumptions. It also corrects an independently observed worker-launch bug in the older DoWhy and EconML/causal-learn dispatchers.

These are development diagnostics. P4E's externally invoked workers still require authenticated Lu authorization and actual OS containment. Test-supplied `host_isolation_attested=True` is **not** a security attestation.

## 2. Methodology

Run `tools/run_c14_p4e_g3_ground_truth.py --output <path>` under an interpreter with exactly Tigramite 5.2.10.1 installed. It requires an actual importable package, not a simulated API, and refuses other package versions.

- Two algorithms: **PCMCI + ParCorr** (FDR-BH correction), **PCMCI+ + ParCorr** (the adapter's existing *uncorrected* significance policy); `pc_alpha = 0.05`, `tau_max = 1`.
- Two regular-sampling lengths: **160 and 320 observations**; no interpolation.
- Five independent seeds: **13, 29, 43, 61, 83**.
- Four scenarios, **80 real-library runs**: 2 × 2 × 5 × 4.

**Exact data generators (after 150-sample burn-in):**

1. `direct_lag`: X(t) = 0.55 X(t−1) + εx(t), Y(t) = 0.35 Y(t−1) + 0.85 X(t−1) + εy(t). Ground-truth cross-edge **X[t−1] → Y[t]**.
2. `independent`: same autoregression without cross-effect, independent Gaussian innovations. Ground-truth cross-edge set is empty.
3. `latent_common_cause`: a persistent **unobserved** U(t) drives both X(t) and Y(t) with lags; there is no direct observed cross-effect. This violates no-hidden-confounding, so its link detection is a **stress observation**, *not* a valid estimator-specific FDR/power calculation.
4. `structural_change`: the Y-equation's lagged X coefficient changes from +0.85 to −0.85 halfway through the observed series, violating stationarity. Report candidate links but **exclude this condition from aggregate causal precision and recall**.

All observations and discovery results are generated locally. Individual synthetic input byte digests are recorded. Do not treat the tiny seeded sample or selected effect sizes as general method performance, power, false discovery rate, calibrated confidence, or real-world causal accuracy.

## 3. Actual findings

For `direct_lag`, **20/20** mode-by-size-by-seed runs recovered the one cross-variable X[t−1] → Y[t] edge, with **no reverse cross-edge** in these runs. For `independent`, **0/20** runs reported any cross-variable link at lag 1. Both are specific to these synthetic assumptions and effects.

For `latent_common_cause`, PCMCI produced reverse-direction candidate links in 3/5 of the 160-row runs and **both cross-directions in all 5** 320-row runs; PCMCI+ produced X-to-Y candidates in 1/5 320-row runs. These outputs are observational candidate relationships in a violated-assumption setting. They do **not** demonstrate that PCMCI or PCMCI+ has a universal false-positive rate, nor do they establish that the observed cross-effects are causal.

For `structural_change`, neither method reported X-to-Y lag-1 candidates on these seeds/lengths, despite a known time-varying structural influence. This illustrates a failure to recover a nonstationary mechanism, **not** a causal nonexistence proof.

Tigramite's documented PCMCI and PCMCI+ methodologies differ in whether contemporaneous edges and partial orientations are considered. **Our wrapper's p-value policies also differ**, so their rates are not a controlled head-to-head statistical comparison. Refer to: https://jakobrunge.github.io/tigramite/ .

The exact case-level evidence is `docs/components/causal/P4E-G3-ground-truth-evidence.json`, including each request's SHA-256, method, seed, row count, findings, and observed local test-harness duration. Those durations are not representative hardware benchmarks.

## 4. Corrected launcher regression

The older `causal_dowhy_backend.py` and `causal_mature_backend.py` resolved the trusted configured Python interpreter symlink and launched the *target executable path*. For a Linux venv, that can effectively invoke the **system Python**, losing installed package state. G3 preserves the **configured absolute interpreter path for invocation**, while following its target for source-executable content hashing and existence validation.

The correction does **not** freeze virtualenv installed wheel provenance, eliminate TOCTOU, certify a signed environment, or implement Windows Job Objects. Both dispatchers reject relative or traversal-containing interpreter paths. Their worker-policy host attestation remains a simulated test boolean, not a security boundary.

Tests: `tests/test_c14_p4e_g3_launcher_paths.py` (four negative cases); existing P2B/P3C process boundary suites were run in the Tigramite virtual environment to ensure launcher parity. Real DoWhy 0.14, EconML 0.17.0 and causal-learn 0.1.4.8 **remain uninstalled** and their positive runtime gates remain open.

## 5. Security, packaging, and statistical limitations

- **No Lu-host authentication, actual Windows OS containment, signed offline wheelhouse, trusted upstream commit authentication, or production kill/revocation gate has passed.**
- The user-supplied `tigramite-master.zip` was read as an external untrusted source and tested in a local Linux venv; its declared version alone does not authenticate GitHub provenance.
- Tigramite is declared **GPLv3** in the provided source. No Tigramite code/wheels are embedded in this Cognitum checkpoint. Its redistribution obligations require separate review.
- This simulator is not a population-representative benchmark; confidence bounds, additional nonlinear and multivariate systems, non-Gaussian noise, varying effect strengths, and model-misspecification studies are future work.
- The result verifier checks request binding and structure, **not independent reexecution of Tigramite** and not the truth of graph edges.

## 6. Next checks

1. Obtain/source-pin DoWhy 0.14, EconML 0.17.0 and causal-learn 0.1.4.8 with compatible dependency closures; test real adapter outputs in isolated environments.
2. Obtain real Windows x86-64 Lu host security and lifecycle verification; do not treat cross-platform source tests as a substitute.
3. Add more systems and repeated trials with pre-registered sensitivity and calibration questions before publishing method comparisons.
4. Preserve the separate quantization-controlled 10-arm Lu+Cognitum model study for later, after security and capability integration.
