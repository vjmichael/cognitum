# Cognitum C14 G25N — Release-gate decision (2026-11-01)

**Decision:** Research phase G25N completed; **NO PRODUCTION PROMOTION**. No Lu or Cognitum production estimator changes. GitHub is repository/documentation only; local tests are archived in the companion research ZIP.

## Scope and frozen evidence

- Frozen two cohorts at independently chosen starting seeds 97,000,101 and 98,000,101; fixed `alpha=.05`, `Gamma=.25`, 199 Monte Carlo replicates and lexicographic W/T/Y order before held-out execution.
- **14,000 distinct synthetic datasets**: 12,000 positive-support cases in 12 family/sample-size cells of 1,000 each and 2,000 structurally unsupported controls. Every source hash and receipt checked.
- Exact mathematical DKW cumulative confidence region (iid multinomial observations); conditional-ratio linear-fractional LP projection; independent pointwise Monte Carlo deviance-rank test against the **simulator-known law only**.

## Gate matrix

| Gate | Verified state |
|---|---|
| Region finite-sample mathematical basis | PASS under iid multinomial assumptions |
| DKW method completion in positive-support controls | PASS: 12,000/12,000 |
| Refusal when observed W/T arm absent | PASS: 2,000/2,000 |
| Automatic causal-confidence admissions | PASS safety: 0/14,000 |
| Full receipt structural audit | PASS: 14,000/14,000 |
| Independent Monte Carlo p-value recomputation | PASS: 14,000/14,000 |
| Exact DKW same-code numerical replays | PASS scoped: 560 |
| Independent linear-fractional ratio LP checks | PASS scoped: 24 |
| G25N tests and tamper checks | PASS: 32/32, including 15 malicious mutations rejected |
| Unchanged G25L/G25M regression tests | PASS: 42/42 |
| DKW positive-case whole-identified-set empirical containment | 12,000/12,000 (100%, too conservative for 95% nominal-calibration screen) |
| DKW true multinomial law included | 13,778/14,000 (98.41%) |
| Preregistered mean width <=0.95 * G25I CP width | **FAIL: 12/12 cells, observed ratios 1.299 to 2.504** |
| Monte Carlo pointwise true-null calibration | 708/14,000 rejects = 5.057% (pooled Wilson 95%: about 4.706%–5.433%); two individual unadjusted cell compatibility flags |
| Exact full likelihood-ratio inversion to a causal confidence interval | **OPEN / NOT IMPLEMENTED** |
| Certified numerical global optimizer with outward error guarantee | OPEN |
| Independent broad-model review, causal assumptions and Gamma justification | OPEN |
| Explicit production promotion authorization | NOT GRANTED |

The DKW result **does not prove a sharp-projection impossibility**: unlike G25M's width no-go, G25N used conservative projections of separate conditional parameter extrema. The Monte Carlo p-value at the true generator law is an oracle diagnostic and is **not a deployable confidence interval**.

## Next milestone proposal

G25O: investigate globally invertible exact-rank likelihood confidence regions and mathematically outward-certified projection of both kinked identified-set endpoints; preregister new independently generated models and retain refusal/optimization failure accounting. Do not relax existing widths based on G25N holdouts.

The full source, both frozen protocols, all 14,000 dataset receipts, audit logs, SHA-256 manifest and report are in `Cognitum_C14_G25N_DKW_And_LR_2026-11-01.zip`, SHA-256 `28cc5b3303ac64745663a28c3d4910dda67148834a87b7a439a47748fdb34d3d`.
