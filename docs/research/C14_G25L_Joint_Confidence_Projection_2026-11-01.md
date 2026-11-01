# Cognitum C14 G25L — Finite-sample joint confidence-region projection

**Date:** 2026-11-01 (America/Phoenix)  
**Status:** G25L isolated research complete. **G25 scientific acceptance NOT MET; NO production promotion.**  
**Scope:** Cognitum C14 only. No Lu changes, no Cognitum production estimator changes, no causal-confidence admission. GitHub is the repository/documentation archive; development and tests ran locally.

## Decision

G25J's smooth simultaneous delta interval refused many kink-boundary cases. G25K's derivative-free subsampling avoided many refusals but undercovered the *whole* Gamma sensitivity-identified set in several positive-support cells. G25L preregistered and evaluated:

1. **joint8:** eight marginal two-sided Clopper–Pearson confidence intervals on joint observed P(W,T,Y), each with error alpha/8, intersected with the multinomial simplex; exact marginal linear-fractional ratio bounds followed by a conservative outer projection of the kinked sensitivity bounds.
2. **hybrid:** joint8 at error alpha/2 intersected with seven conditional CP confidence intervals at combined error alpha/2, then conservative outer projection.
3. **G25I CP reference:** original seven-conditional Bonferroni reference.
4. **G25K m-out-of-n comparator:** frozen 199-draw method with n^0.8 and minimum 190 valid draws, which is research-only and not uniformly calibrated.

For joint8, the Bonferroni event of all eight binomial CP intervals covering the corresponding true probabilities has probability >=95% under iid multinomial sampling. Projecting an **outer enclosure** of that region through the nonsmooth identified-set map preserves whole-set containment whenever the true observed law lies in the region and the requisite observed arms are supported. The hybrid's two separately controlled alpha/2 regions have joint coverage >=95% by union bound. Both are outer approximations, **not globally tight optimizations**. A data-dependent refusal does not imply 95% conditional-on-admission coverage; the relevant unconditional safety statement is P(issued AND population set excluded) <= alpha. Crucially, neither method verifies that a user-specified Gamma is scientifically justified or that latent confounding is absent.

## Frozen experiment

- Two disjoint cohorts, A from seed 33,000,001 and B from 44,000,001; 500 independent datasets per family/size/cohort.
- Seven families: exact_kink, local_kink, rare_binary, thin_positive, asymmetric_hidden, rare_reversal, structural_zero; the latter is the negative control and the two preceding it are newly specified W/U synthetic mechanisms. Sample sizes 900 and 1,800.
- **14,000 distinct dataset receipts**, including 12,000 positive-support and 2,000 structural-non-overlap cases. Gamma risk-difference sensitivity assumptions {0,.10,.25,.50,1}. Four interval methods: **280,000 recorded method/Γ attempts**, including refusals.
- Frozen protocol SHA-256 cohort A: `a4bdd8809e07972d909b029022af1a48160222cce955e342642f00973e9fba46`; B: `a96e5924f7db83d996fb3190f170fcf2eb0998a01d0b3e0a430f7734a2abe468`.
- Original receipt hashes: A `225f4f3a623e21c5dbdf2458312c2f4ef32e139bcbcaec26ac58b3f3cfc09115`; B `6d276665e61bff54257281ae900f9a932bb0cf099bf716386e4a6da49fc29112`.

## Scientific results

**Every positive-support cell was accepted by both G25L candidates.** Each method issued 60,000/60,000 Gamma-specific positive intervals; each showed 60,000/60,000 empirical simultaneous population identified-set containments. Both refused 10,000/10,000 structural-zero Gamma attempts. This is evidence of overconservatism rather than precise 95% calibration.

| Model at Γ=0.25 | n | G25I CP width | joint8 width | hybrid width | G25K set coverage (completed) |
|---|---:|---:|---:|---:|---:|
| exact_kink | 900 | .8299 | 1.0117 | .8559 | 92.6% (1000/1000) |
| local_kink | 1800 | .7326 | .8685 | .7514 | 93.9% (1000/1000) |
| rare_binary | 900 | .4790 | .5373 | .4942 | 93.4% (1000/1000) |
| thin_positive | 900 | 1.0742 | 1.1468 | 1.0962 | 95.99% (548/1000) |
| asymmetric_hidden | 1800 | .7583 | .8516 | .7795 | 95.0% (1000/1000) |
| rare_reversal | 900 | .4949 | .5579 | .5110 | 93.3% (1000/1000) |

Across all 60 positive model/size/Gamma acceptance cells, joint8 mean width ratios relative to G25I reference range from **1.028 to 1.540**, hybrid from **1.008 to 1.082**. The preregistered screen requires >=99% completion, >=93% set coverage, nominal .95 inside the Wilson 95% Monte Carlo CI and mean width <=.95 x matched G25I. The screens passed: **joint8 0/60; hybrid 0/60; G25I baseline 0/60 (a self-reference necessarily fails the .95 width rule); G25K subsampling 46/60**. G25K completed 57,735/60,000 positive attempts, with 54,831 full-set containments; it also retains weak-overlap refusals and undercoverage.

**Decision: NO PRODUCTION PROMOTION.** The joint/hybrid procedures have defensible finite-sample *outer* coverage, but are wider and less useful than G25I CP. Empirical 100% coverage does not establish well-calibrated 95% inference. The mathematical coverage result does not justify causal certification when Gamma or identification assumptions are unverified.

## Independent verification

- 14,000/14,000 complete exact same-code receipt replays, in fourteen nonoverlapping, bounded 1,000-case chunks. Every chunk pinned the original cohort receipt hash.
- Full structural/provenance audit of 14,000 fixtures and 280,000 interval attempts; no lost refusals and no causal admissions.
- Independent SciPy HiGHS/Charnes–Cooper calculations agree with 5,760 marginal ratio extremum values, maximum absolute difference **3.33e-16**; 2,400 independent empirical-set containment checks pass.
- **22/22 G25L tests** and **23/23 unchanged G25K regression tests** pass. **12/12 adversarial receipt mutations** detected.
- The concurrent and monolithic exhaustive audit commands exceeded local execution limits; source/receipts unchanged, subsequent bounded full replay succeeded. This operational deviation is recorded in the local research package.
- Local research ZIP `Cognitum_C14_G25L_Confidence_Projection_2026-11-01.zip`: 48 files plus SHA-256 manifest, 7,501,958 bytes, SHA-256 `b74cca10b5f3584902af1312b701405e48989fba522f6eb03c5dd3673a231349`. ZIP CRC and all 48 member file hashes passed. The complete archive was supplied in the ChatGPT conversation; GitHub stores this milestone ledger and the predeclaration, not the 54 MB uncompressed receipts.

## Reproduction and follow-up

The complete companion archive contains `tools/g25l_core.py`, `tools/g25l_models.py`, `tools/run_g25l.py`, frozen G25I/J/K baselines, frozen configs and tests, full receipts, independent numerical checks, postholdout auditors, exact replay chunk certificates and engineering report. Execute with Python 3.13, NumPy 2.3.5, SciPy 1.17.0, pytest 9.0.2 and single-threaded BLAS. Preserve the original archive before rerunning seed cohorts, because the local runner overwrites receipt files.

**Next proposed research G25M:** globally optimize both kinked identified-set endpoints over the *joint* confidence region while rigorously bounding numerical optimization error. G25L discarded dependence among nuisance probabilities when replacing the joint region by an outer rectangle. Reducing that relaxation, not changing alpha based on observed failures, is the principled next question. Use new seeds, preregistration, independent optimization checking and explicit approval before any production algorithm changes.

Conceptual references: Chernozhukov–Hong–Tamer (2007), Econometrica, DOI 10.1111/j.1468-0262.2007.00794.x; Imbens–Manski (2004), Econometrica, DOI 10.1111/j.1468-0262.2004.00555.x. These publications do not independently validate this implementation.
