# Cognitum C14 G25M — Certified width obstruction and complete acceptance-gate assessment

**Date:** November 1, 2026 (America/Phoenix)  
**Status:** **G25M research complete; global-width/production scientific acceptance FAILED.**  
**Scope:** Isolated Cognitum C14 statistical research. **No production estimator, Lu, DLC, policy or admission change.** GitHub is used for code provenance and documentation only; development and tests ran locally.

## Executive result

G25L produced mathematically conservative 95%-or-better outer confidence sets, but their width exceeded the G25I exact CP reference. G25M retained the full **joint** observed-law hybrid confidence polytope, reduced exact global endpoint optimization from eight joint-cell probabilities to four treatment-arm masses, and tested whether *any* globally sharp optimization of this region could satisfy the preregistered precision limit. Instead of depending on unverified optimizer convergence, G25M supplied two explicit, independently verified **feasible confidence-region witnesses** per dataset; their identified-set endpoint span is a rigorous lower bound on the sharp interval width.

**Result: every one of the twelve positive-support 1,000-dataset acceptance cells fails the 0.95× G25I reference-width gate, even under ideal global optimization. All 12,000 individual datasets were themselves width no-go certificates.** Cell-mean attainable spans are **100.86% to 102.20%** of reference widths; the maximum admissible ratio is **95.00%**. Pooled attainable lower-bound span / pooled reference width = **101.46%**. Even an exact globally optimal solver cannot close this gate with the frozen hybrid region.

This is **specific to the selected confidence-region construction and width criterion**. It does not preclude a future, differently calibrated confidence region from meeting the gate, and does not prove all causal confidence intervals have to be this wide.

## Mathematical reduction and negative feasibility proof

Observed eight-cell probabilities `q[w,t,y]` lie inside simultaneous eight-cell Clopper–Pearson bounds with a combined α/2 Bonferroni error, seven simultaneous conditional CP restrictions with α/2 error, and the simplex. Every conditional CP restriction is a linear inequality in the eight joint probabilities; the full feasible region is a polytope. For fixed arm masses `a_w=P(W=w,T=0)` and `b_w=P(W=w,T=1)`, success masses have *exact* minimum and maximum consistent with every CP constraint and the joint-cell box. Both endpoints of the risk-difference-Γ identified set are monotone in the success probabilities, so the remaining global problem is a constrained four-mass optimization.

Let the sharp projected interval be `[inf_C L(q,Γ), sup_C U(q,Γ)]`. For any separately validated feasible laws `q_L,q_U` in `C`, its width is at least `U(q_U,Γ)-L(q_L,Γ)`. SLSQP proposes the arm masses only; HiGHS independently repairs them, and the complete eight-cell witnesses are checked against the original joint, conditional and simplex inequalities before their numerical values enter any result. Failures fall back to the empirical observed-law witness. The width proof **does not need SLSQP or branch-and-bound to find a global extremum**. See `docs/G25M_Mathematical_NoGo_and_Gate_Contract.md` and the frozen `tools/g25m_core.py`.

Γ=1 is separately affine and globally solved with an eight-dimensional LP. For other Γ, spatial branch-and-bound supplies valid outward interval enclosures **with explicit nonzero sharpness gaps when budget-limited**. It does not claim a sharp global solution when the gap remains. No unverified optimizer output enters the no-go calculation.

## Frozen cohorts and outcome

- Two disjoint cohorts, A seed start **55,000,001**, B seed start **66,000,001**. Six positive families × n=900/1,800 × 500 seeds/cohort = **12,000 positive datasets**. Structural-zero negative controls = **2,000 datasets**, giving **14,000 distinct dataset receipts**. Primary fixed Γ=.25. No G25I–L evaluation seed reused.
- Frozen protocol SHA-256 A: `c884a4178f3c9b59f98e856de8d5cbeed575560be2c26629860fe5277adb0598`. B: `8958598e5d35f2f4c5f3e86efbf80897fcb26d95824234bdce3e6cc842dbc4b8`. Both lock the same nine scientific source/test/predeclaration hashes; orchestration and audit code cannot alter inference methods.
- The width and completion gate is evaluated across **1,000 independent datasets per positive cell**, comparing mean witness span against the **same accepted-case mean G25I CP width**.

| Family | n | Attainable-span lower bound | G25I CP mean width | Lower-bound/reference ratio | Individual no-go | True observed law inside hybrid region |
|---|---:|---:|---:|---:|---:|---:|
| `exact_kink` | 900 | 0.8394 | 0.8293 | 101.21% | 1000/1000 | 970/1000 |
| `exact_kink` | 1,800 | 0.7418 | 0.7325 | 101.27% | 1000/1000 | 964/1000 |
| `local_kink` | 900 | 0.8392 | 0.8293 | 101.20% | 1000/1000 | 959/1000 |
| `local_kink` | 1,800 | 0.7416 | 0.7324 | 101.26% | 1000/1000 | 967/1000 |
| `rare_binary` | 900 | 0.4833 | 0.4787 | 100.96% | 1000/1000 | 978/1000 |
| `rare_binary` | 1,800 | 0.4269 | 0.4228 | 100.97% | 1000/1000 | 969/1000 |
| `thin_positive` | 900 | 1.0913 | 1.0744 | 101.57% | 1000/1000 | 975/1000 |
| `thin_positive` | 1,800 | 0.9988 | 0.9773 | 102.20% | 1000/1000 | 976/1000 |
| `asymmetric_hidden` | 900 | 0.8823 | 0.8645 | 102.07% | 1000/1000 | 971/1000 |
| `asymmetric_hidden` | 1,800 | 0.7732 | 0.7583 | 101.96% | 1000/1000 | 971/1000 |
| `rare_reversal` | 900 | 0.4990 | 0.4947 | 100.86% | 1000/1000 | 980/1000 |
| `rare_reversal` | 1,800 | 0.4397 | 0.4359 | 100.87% | 1000/1000 | 960/1000 |

All **12,000/12,000** positive cases completed verified feasible witnesses. The original G25I CP reference band contained both Γ=.25 population identified-set endpoints in **12,000/12,000** evaluated positives. That empirical 100% coverage is conservative, not calibrated nominal 95%; the reference remains a comparator, not an accepted optimized production interval. The hybrid confidence **region itself** contained the simulator-known true observed joint law in between 959/1000 and 980/1000 cases per cell; this is consistent with a conservative ≥95% unconditional confidence-region guarantee. These are distinct coverage outcomes; neither verifies Γ's adequacy or causal exchangeability.

Structural zeros: **2,000/2,000 refused all conditional inference.** They were never entered as positive coverage successes. Numerical interval calculation and structural support are not tests for hidden confounding, and no output automatically granted causal authorization.

## Independent mathematical, regression and integrity verification

- Complete independent receipt audit regenerated **all 14,000 synthetic fixtures** and rechecked 14,000 receipt hashes/seed identities, every accepted eight-cell witness's 8 marginal CP bounds, seven conditional CP restrictions, simplex and signed identified-set endpoint span; recomputed the exact G25I reference and all per-case no-go flags. No duplicate or omitted seeds.
- **12/12 adversarial receipt mutations rejected**, including forged causal authorization, altered fixture/population hash, modified observed counts, modified lower/upper witnesses, status/Γ changes, false width and gate results and altered reference.
- Independent mathematical checks: **96** exact Γ=1 joint-only LP vs *closed-form* diagonal-mass extrema, **96** hybrid Γ=1 full eight-cell LP witnesses, **960** independent identified-set mapping comparisons, and **60** valid branch-and-bound outer checks. Of twelve capped Γ=.25 branch search examples, only **2** reached the selected 0.01 global sharpness-gap tolerance; none of those incomplete searches is called a sharp global optimum.
- Unchanged G25I: **22/22 tests**, G25J: **43/43**, G25K: **23/23**, G25L: **22/22**, new G25M: **20/20** — **130/130 regression and G25M unit tests passed**. They cover separate earlier estimators and do not establish production readiness for G25M.
- No hidden confounding detection, no causal-confidence grant, no production code mutation; external scientific review still pending.

## Gate-by-gate decision

| Gate | Result | Evidence / remaining issue |
|---|---|---|
| M1 — Mathematical exact reduction and feasibility | **PASS** | Four-mass reduction; every returned witness satisfies original eight-cell joint+conditional constraints; Γ=1 exact LP and closed-form cross-check. |
| M2 — Reproducibility, preregistration and complete provenance | **PASS** | 14,000 disjoint seeded receipts, frozen science/source hashes, regeneration of every observed dataset, auditor/12 tamper tests. |
| M3 — Observed-support safety / no automatic causal authority | **PASS under tested conditions** | 2,000 structural-zero refusals; zero automated causal authorizations. Hidden confounding cannot be certified absent. |
| M4 — Completion ≥99% for positive supported cases | **PASS for primary Γ=.25 pilot** | All 12,000 positive width witnesses completed; these are width certificates, **not candidate confidence intervals**. |
| M5 — Sharp global numerical optimizer | **INCOMPLETE** | Verified outward branch enclosures, but ten of twelve capped Γ=.25 searches retain global gaps >0.01. No finite-gap solver success is claimed. |
| M6 — Required mean width ≤0.95× G25I reference | **FAIL: mathematically impossible for this frozen hybrid region** | All 12 positive cells, and all 12,000 datasets, have certified attainable spans exceeding the threshold. No sharper numerical optimizer can fix this region. |
| M7 — Nominal 95% full-set coverage and cellwise calibration | **NOT PROMOTION-ELIGIBLE** | The frozen G25M primary screen is a *width lower-bound test*, not a new globally sharp CI. G25I CP comparator achieved 100% set inclusion, too conservative for the research calibration screen; no claims for uncomputed sharp G25M intervals. |
| M8 — Broader G25 science (continuous covariates, rare outcomes, HTE, confounding, measurement) | **PARTIAL / OPEN** | G25M's binary observed W/T/Y study includes rare outcomes and hidden-U simulations, but does not validate general continuous-covariate AIPW inference, correct nuisance uncertainty, or unmeasured causal assumptions. |
| M9 — Independent external implementation/statistical review | **OPEN** | SciPy LP, a separate closed-form result and formula comparisons are local independent routes; external R sparse-logistic equivalence and a separate independent review remain outstanding. |
| M10 — Production authorization and rollback | **NOT AUTHORIZED** | No production algorithm change. A mathematical/scientific gate failed; a new preregistered method and external review would be required before requesting production approval. |

## Engineering outcome and next task

**Do not promote G25M.** Its numerical implementation helps prove the root cause of G25L's precision problem: the inherited conservative confidence region, not merely the rectangular outer projection. Investing further in sharper global optimization of that same region cannot pass the preregistered width gate. Stop this research branch at a reproducible negative milestone.

A proposed **G25N**, if pursued, must build a *new finite-sample confidence region* using a genuinely different joint multinomial construction or coverage argument (not post-hoc α retuning), preregister new synthetic models/seeds and its own width and coverage acceptance gates, and demonstrate performance at smooth, kink, rare-outcome and thin-overlap settings. The longstanding Firth `logistf`/`brglm2` external validation, independent statistical review, nonbinary-covariate generalization and G25 production acceptance are still open. A one-click Lu installer or Cognitum addition to Lu is unrelated to this scientific gate and was not attempted.

## Operational record

An attempted interactive local cohort launcher was unsupported by the container execution interface, and the first noninteractive wrapper launch referenced a script that had not yet been written; neither produced evaluation data. After the wrapper was created, the entire frozen cohort executed once across local bounded workers and completed. No method, source hash, seed selection, threshold, or α allocation was altered after freezing. A post-freeze structural audit and the independently derived Γ=1 LP were separate verification procedures and did not change inference receipts.

**Replication:** Unpack the companion `Cognitum_C14_G25M_Certified_NoGo_2026-11-01.zip`, preserve the original research receipts, run `python -m pytest -q tests/test_g25m.py` with BLAS=1, then `python tools/audit_g25m.py`, `python tools/g25m_independent_numerical.py`, and `python tools/run_regression_gates.py`. The frozen source requires Python 3.13, NumPy 2.3.5, SciPy 1.17.0, pytest 9.0.2. Long-running held-out regeneration uses `tools/run_g25m_witness.py A|B family n start stop`; the `execute_g25m_cohorts.py` dispatcher is execution-only and uses no scientific settings. Original results are retained separately so a rerun cannot erase the evidence.