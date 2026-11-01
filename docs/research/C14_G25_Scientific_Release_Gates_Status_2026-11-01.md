# Cognitum C14 G25 — Consolidated scientific release-gate status (2026-11-01)

**Overall: NOT ACCEPTED. No production promotion.** Local-first development; GitHub is the repository/provenance record. No Cognitum production estimator, Lu source, DLC, or automatic causal authorization changed.

## Completed research evidence

G25I delivered conditional sensitivity bounds with conservative widths. G25J shorter asymptotic intervals undercovered or refused kink cases. G25K subsampling improved completion but undercovered selected whole identified sets. G25L joint/conditional Clopper–Pearson confidence-region projections were conservatively valid but wider than the G25I reference.

G25M took the next scientific step: two independently validated, attainable probability laws inside the frozen hybrid confidence region yield a lower bound on the *sharpest possible* confidence-set width. Across 12,000 fresh positive datasets in twelve 1,000-case cells, **every case** produced a lower bound exceeding 95% of the G25I reference width. Across cells, mean lower-bound/reference ratios ranged from **100.86% to 102.20%**. The precision requirement is **at most 95%**. Therefore no globally sharper numerical solver operating on this same region can pass the width requirement.

Full independent G25M audit regenerated **14,000** distinct synthetic fixtures, including **2,000 structural-zero refusals**; every receipt and feasible witness was validated. All **12 adversarial receipt mutations** were rejected. Unchanged G25I–L regression suites and new G25M unit tests passed **130/130**. Independent checks passed 96 joint Gamma=1 closed-form comparisons, 96 hybrid LP witnesses, 960 endpoint function comparisons and 60 branch outer-bound checks. Ten of twelve capped nonlinear branch searches did not reach the selected numerical gap tolerance, but the width no-go proof does **not** depend on optimizer convergence.

## Release-gate matrix

| Gate | Status | Outstanding work |
|---|---|---|
| Frozen holdouts, immutable method/seed hashes and complete receipts | PASS for G25M | Preserve all original evidence |
| Exact four-mass reduction and feasibility of identified-set width witnesses | PASS for G25M | No action needed for no-go proof |
| Missing-arm support refusal and no automatic causal admission | PASS under tested conditions | Preserve conditional assumption labels |
| Required narrow, calibrated 95% full-set intervals across every family/size/Gamma cell | **FAIL** | New region/inference construction; width no-go for frozen hybrid |
| Universal sharp nonlinear projection | OPEN | Nonzero gaps in ten of twelve bounded search examples; never claim sharpness |
| Generality to continuous/nonlinear covariates, effect heterogeneity, rare outcomes, measurement errors and hidden confounding | OPEN | Additional preregistered models and negative-control reviews |
| Nuisance-estimation variance under misspecification | OPEN | G25G/H diagnosed bias and calibration; estimator-specific proof required |
| Independent R Firth equivalence (logistf / brglm2) | OPEN | External library environment and comparison |
| Independent scientific code review and separate holdout replication | OPEN | Independent reviewer and rollback plan |
| Explicit production algorithm authorization | NOT GRANTED | User authorization required only after all scientific gates pass |

The mathematical negative result is **specific to the existing conservative confidence region**. It is not a proof that every possible method is too wide or that unidentified confounding can be detected from observed data.

## Correct next research milestone: G25N

Preregister a **different** finite-sample confidence-region family or a fundamentally distinct inference procedure, with an independently checked coverage derivation and a new frozen holdout. Do not tune previous alpha allocations, Gamma, thresholds or evaluation seeds after inspecting G25M. Compare whole-identified-set coverage, width, all refusals, runtime and hidden-confounding safety. No G25 production algorithm may be promoted without external scientific review and separate explicit user approval.

The complete G25M source, two frozen cohorts and receipt archive are attached in the original conversation; the detailed research report and predeclaration are on this dedicated branch.
