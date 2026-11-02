# CH-C14-01 — C14 Causal Component Revisit and Scientific Gate Inventory

**2026-11-02 | Status: DOCUMENT REVIEW COMPLETE, fresh code execution NOT YET PERFORMED.** Linux-only, research. No production estimator changes.

## Repositories/documents read on 2026-11-02

- `docs/research/C14_G25N_DKW_And_Pointwise_MC_2026-11-01.md`
- `docs/research/C14_G25N_Release_Gates_2026-11-01.md`
- `docs/research/C14_G25_Scientific_Release_Gates_Status_2026-11-01.md`
- `docs/research/C14_G25I_Causal_Identification_Sensitivity_2026-11-01.md`
- `docs/research/C14_G25_Engineering_Gate_Closure_2026-11-01.md`

## Revisited evidence

1. **Partial identification, not automatic causal discovery.** G25I's Gamma is a user/analyst assumption bounding counterfactual risk differences, not a fitted guarantee; hidden confounding remains unknowable from observational overlap and solver convergence alone. Gamma=0 may misidentify an effect if exchangeability fails.
2. **Finite-sample interval validity versus usefulness.** G25N's DKW iid multinomial region has a defensible >=95% theoretical law-coverage argument. However, its projected intervals were too conservative: **12/12 positive-support cells failed** the preregistered <=0.95× G25I width requirement, with observed width ratios **1.299–2.504×**. Whole-identified-set coverage observed 12,000/12,000 under the simulated adequate condition is not nominal calibration.
3. **Pointwise rank is not causal interval certification.** The G25N Monte Carlo likelihood-ratio test rejected 708/14,000 oracle-known true nulls (5.057%), but it was evaluated at simulator-known q and **global inversion and certified projection remain unimplemented**. Do not present the diagnostic as deployed confidence intervals.
4. **Structural support and numerical integrity.** G25N recorded 2,000/2,000 missing-arm refusals and 0/14,000 automatic causal-confidence admissions. Its documented fresh tests passed 32 new and 42 unchanged regression checks. The later engineering guard documented 96 passed tests, 560 stratified replays and additional independent LP / Clopper–Pearson comparisons; still research-only and **not integrated with production runtime**.
5. **No mathematical overclaims.** G25M's sharpness/width no-go applies to the frozen G25L hybrid confidence region. It does not prove that all future confidence constructions are too wide. Likewise G25N's conservative ratio projection is not proven globally sharp.
6. **Existing engineering research integration:** a nonproduction C14 host/supervisor adapter is present under `research/c14_g25_nonprod`. Its existence is not equivalent to scientific acceptance, live Linux OS worker containment, or readiness for film causal inference.

## Release-gate inventory (document evidence, not new test results)

| Gate | Review disposition |
|---|---|
| Input and receipt validation | Substantial previous research PASS; rerun needed on current target |
| Structural-zero refusal | Prior research PASS; preserve |
| Causal-identification assumptions / hidden confounding | OPEN; cannot be inferred automatically |
| Uncertainty coverage + width on held-out varied SCMs | FAIL in G25N; new scientific work necessary |
| Full likelihood-ratio inversion and certified outward interval projection | OPEN |
| Nuisance/misspecification and sparse-outcome scientific reliability | OPEN |
| Independent R Firth comparison | OPEN |
| Independent external statistical review | OPEN |
| Production runtime integration, cancellation and live kernel supervision | OPEN/PARTIAL |
| Production estimator promotion | **NO-GO**; explicit future approval required |

## Next engineering actions (in order)

1. Inspect existing C14 nonproduction contract and guard for all input/output paths, source/provenance, and cancellation. Rerun exact existing tests locally, without modifying the locked estimator.
2. Make a fail-closed **noncausal reporting mode** the first integration target: explicit observational association vs causally identified effect; analyst-supplied assumptions; completeness/positivity/sparsity warnings; refusal status and computational uncertainty.
3. Predeclare out-of-family SCMs with nonlinear/continuous covariates, rare events, measurement error and hidden common causes. Compare against sound standard methods on matched data, with all attempted trials counted.
4. Validate interval estimators and coverage **per family**, width, computational costs, numerical failures and abstentions; do not retune after accessing test oracles.
5. Obtain expert scientific review and independent implementations before claiming production-ready causal inference. If current region is irreparably too wide, consider fundamentally different preregistered inference—not cosmetic parameter tuning.

**Immediate disposition:** C14 research is operational enough for a guarded nonproduction capability evaluation, but **not scientifically qualified to interpret NVP character motivations as verified causal facts**. A script can specify motivations as authoritative narrative data; C14 cannot infer them from actor observations as established causal truth.

## Traceability

This checkpoint is a source/document audit, **not a fresh benchmark run**. Previous measured outcomes are cited by their original repository reports and must not be advertised as CH-C14-01 test results. No changes to Lu or production C14.
