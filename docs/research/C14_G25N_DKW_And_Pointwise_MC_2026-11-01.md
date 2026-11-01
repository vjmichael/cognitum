# Cognitum C14 G25N — New multinomial confidence-region and exact-rank inversion research

**Date:** November 1, 2026 (America/Phoenix).  
**Status:** Two frozen, disjoint cohorts executed and independently audited. **G25N precision gate FAILED; NO PRODUCTION PROMOTION**.  
**Scope:** Research-only Cognitum C14; no production estimator modifications, no changes to Lu, no automatic causal certification.

## Executive conclusion

G25M showed a *specific* mathematical no-go for the previously frozen G25L hybrid CP region. G25N therefore replaced that region with a genuinely distinct finite-sample **DKW cumulative-multinomial confidence polytope**, and separately screened a **pointwise Monte Carlo likelihood-ratio inversion** candidate. Both methods were fixed before evaluation.

The DKW method is distribution-free under iid observations and can provide conservative confidence regions for the eight ordered probabilities. All 12,000 positive-support cases yielded intervals containing the simulator-known full Gamma-identified set at Gamma=0.25, but each of the twelve 1,000-case positive cells failed the preregistered precision requirement: the new intervals are **1.299–2.504 times as wide as** the matched G25I CP reference, whereas the acceptance ceiling is **0.95 times** the reference. The DKW method is mathematically defensible as a region but not scientifically competitive as an estimator in these tested families. Unlike the prior G25M no-go, this is **not a proof that the globally sharp projection of the DKW region cannot pass**: the current method projects separate conditional ratio ranges, losing dependence. Do not claim an impossibility result that has not been shown.

The independent Monte Carlo likelihood-ratio test has a pointwise rank-validity argument and rejected 708/14,000 true synthetic nulls (5.057%). However, this evaluation uses the generator-known law q, which an operational tool does not know. The *global inversion/projection across all candidate probability vectors* has not been implemented or numerically certified. Thus the likelihood-ratio result cannot justify issuing causal confidence intervals in production.

## Frozen study and statistical methods

- Two cohorts: A seeds start at 97,000,101, B at 98,000,101; six positive families and structural-zero negative controls, n=900 and 1,800, 500 datasets per cohort/family/size. **14,000 total distinct datasets; 12,000 positive, 2,000 negative.** Prior G25I–M holdout seeds and the G25N pilot seeds are excluded.
- DKW region: for fixed category order 0–7 (W,T,Y), all seven cumulative-probability gaps are bounded by ε = sqrt(log(2/0.05)/(2n)). Its simultaneous coverage of the multinomial law is at least 95% under iid sampling, by the DKW–Massart inequality. The category ordering is fixed before data collection.
- Conditional probability extremes are solved via Charnes–Cooper LP over the DKW polytope, and a monotone outer sensitivity-bound formula is applied at **Gamma=0.25**. If the polytope permits a vanishing denominator, the ratio is conservatively widened to [0,1]; if an observed treatment/stratum arm is empty, the candidate refuses conditional inference. LP implementations need certified numerical-error enclosures before production use; current numerical cross-checks are research validation, not formal machine certification.
- Monte Carlo pointwise test: B=199 null multinomial replicates per dataset, deviance test statistic, p=(1+#replicates with statistic >= observed)/(B+1). At a *fixed true* q the test is superuniform by exchangeability, including ties, and has minimum p=0.005. Simulated q was only used for diagnostic test validity, **never** to calculate DKW operational intervals.
- All datasets and their refusal events count in denominators. Confidence bands for empirical coverage and null-rejection rates use Wilson 95% intervals. No data-driven alpha or Gamma changes.

## Pooled held-out findings

| Family | n | New intervals issued | New width / G25I | Whole-set containment (issued) | True-null MC rejects |
|---|---:|---:|---:|---:|---:|

| exact_kink | 900 | 1,000/1,000 | 1.760× | 100.00% | 56/1,000 |
| exact_kink | 1800 | 1,000/1,000 | 1.690× | 100.00% | 56/1,000 |
| local_kink | 900 | 1,000/1,000 | 1.773× | 100.00% | 40/1,000 |
| local_kink | 1800 | 1,000/1,000 | 1.688× | 100.00% | 53/1,000 |
| rare_binary | 900 | 1,000/1,000 | 2.422× | 100.00% | 50/1,000 |
| rare_binary | 1800 | 1,000/1,000 | 2.176× | 100.00% | 49/1,000 |
| thin_positive | 900 | 1,000/1,000 | 1.299× | 100.00% | 57/1,000 |
| thin_positive | 1800 | 1,000/1,000 | 1.322× | 100.00% | 65/1,000 |
| asymmetric_hidden | 900 | 1,000/1,000 | 1.691× | 100.00% | 52/1,000 |
| asymmetric_hidden | 1800 | 1,000/1,000 | 1.758× | 100.00% | 42/1,000 |
| rare_reversal | 900 | 1,000/1,000 | 2.504× | 100.00% | 59/1,000 |
| rare_reversal | 1800 | 1,000/1,000 | 2.263× | 100.00% | 46/1,000 |


- Positive-support DKW intervals issued: **12,000/12,000**, with 12,000/12,000 simulator-known population-identified-set containments. This 100% conditional result is overly conservative under the empirical nominal-calibration screen; the Wilson interval for 1,000/1,000 excludes 95% in every positive cell.
- Structural-zero controls refused: **2,000/2,000**. No automatic causal-confidence admissions: **0/14,000**.
- The simulator's true multinomial law belonged to the DKW region in **13,778/14,000 (98.41%)** independent draws. The DKW inequality supplies a minimum 95% guarantee; its higher discrete-model empirical inclusion here is not an error.
- The DKW region did not exclude zero conditional mass for every stratum/arm in **4,000 positive cases**. The method recorded conservative [0,1] conditional ratio bounds instead of treating empirical positivity as population support certification.
- The pointwise Monte Carlo true-null rank test rejected **708/14,000 = 5.057%**, with a pooled Wilson 95% interval of approximately **4.706%–5.433%**, compatible with the nominal 5% rate. Two of fourteen individual cells failed the *unadjusted* per-cell Wilson compatibility check: structural_zero n=900 had 36/1,000 rejects (3.6%, Wilson upper about 4.94%); thin_positive n=1,800 had 65/1,000 (6.5%, Wilson lower about 5.13%). These are not multiplicity-adjusted discoveries and do not invalidate the pointwise rank argument.

**G25N DKW screening result: 0/12 positive scientific acceptance cells passed** because every width ratio exceeded 0.95 and every Wilson interval around 100% set containment excluded the nominal 95% target. The pointwise Monte Carlo calibration study does not itself deliver full identified-set intervals, so **global inversion gate remains OPEN**.

## Validation record

- **14,000/14,000 original fixtures structurally regenerated and audited**, including source seeds, count tables, SHA-256 fixture identifiers, population parameter hashes, false-admission tags, exact CP reference values, width accounting, and support/refusal flags.
- **14,000/14,000 independent Monte Carlo test replays**, using SciPy KL divergence and the original deterministic null-replicate streams rather than the runner's deviance implementation.
- **560 exact DKW numerical-method replays** (20 per cohort/family/size cell), with unchanged interval endpoints.
- **24 independent ratio-extremum LP bisection checks** (one per positive cohort/family/size cell). These agree with Charnes–Cooper LP to well below 1e-6 in tested cases.
- **32/32 new G25N implementation and adversarial tests passed** after fixing a test-fixture mistake (the first chosen denominator was strictly positive, so it could not test possible-zero handling); **42/42 unchanged G25L/G25M regression tests passed**.
- 15 forged receipt variations in the adversarial suite were rejected: altered observed counts/seed/fixture/population hash, false causal admission, changed method status, forged MC rank, flipped true-region membership, altered CP reference, changed width and unsupported settings.
- All original frozen source hashes matched during both complete held-out runs; the reporting and auditor scripts were added *after* freezing and do not change the experiment's calculations.

## Acceptance gates

| Gate | Decision | Reason |
|---|---|---|
| Distinct finite-sample confidence-region mathematical argument | **PASS** | Fixed iid multinomial DKW region, theoretical coverage >=95% |
| New DKW computation/refusal at positive and structural-zero cases | **PASS tested cases** | All positive issued; all zero-arm controls refused |
| Full provenance and independent receipt audit | **PASS** | 14,000 structurally reconstructed, 14,000 independent MC rank replays |
| Independent numerical checks of LP extrema | **PASS scoped** | 24 fractional-ratio LP cross-checks; no machine-verified universal optimizer certification |
| Per-cell width <=0.95 G25I reference | **FAIL 12/12** | Ratios 1.299–2.504 |
| Empirical 95% whole-set calibration and Wilson compatibility | **FAIL 12/12** | 100% observed inclusion under a nominal calibration screen; too conservative |
| Exact global MC likelihood-ratio inversion and projection | **OPEN** | Pointwise test alone cannot issue a full identified-set interval |
| General causal identification and justified Gamma from observed data | **NOT ESTABLISHED** | Hidden confounding can pass every observed-data diagnostic |
| Wider causal-model generality, external package equivalence, independent scientific review | **OPEN** | Research-only binary W/T/Y models, no external R Firth equivalence |
| Production algorithm authorization | **NOT GRANTED** | Separate explicit user approval required after scientific gates |

## Scientific implications and next step (proposed G25O)

**Do not spend additional effort merely sharpening the current DKW outer rectangle** unless a globally valid lower-bound proof indicates it could meet the width threshold. G25M already ruled out the old hybrid region; G25N demonstrates that a new distribution-free region can nevertheless be too wide. The more promising unfinished candidate is a *globally invertible*, exactly test-calibrated multinomial likelihood-ratio confidence set, potentially combined with branch-and-bound and explicitly outward numerical certification, or a scientifically distinct endpoint-targeted procedure with its own coverage proof. The Monte Carlo null simulator must never be fed the unknown population table in a deployable inference path. Require independent new seeds and strict optimization/refusal accounting before considering promotion.

The archived programs and receipts are standalone local research artifacts. GitHub is only a repository/documentation record; no production source or Lu code changed.

## References for principles, not implementation validation

- DKW–Massart inequality overview: https://androma.org/theorems/6300
- Exact plus-one Monte Carlo p-value rationale: https://pmc.ncbi.nlm.nih.gov/articles/PMC379178/
- Distinction between inference for a partially identified parameter and for the whole identified set: https://ifs.org.uk/publications/confidence-intervals-partially-identified-parameters