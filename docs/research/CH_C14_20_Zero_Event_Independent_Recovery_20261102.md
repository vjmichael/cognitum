# CH-C14-20 — Independent recovery of genuine zero-event brglm2 nonconvergence

**2026-11-02 · Research-only engineering diagnostic PASS · scientific production NO-GO.** No Lu, Windows, pinned G25, or production C14 modifications.

## Protocol and original cases

The CH19 benchmark found **10 original nonconvergent R fits across 5 different datasets**, using both ordinary and zero-offset actual `brglm2` 0.9.2. CH20 is a **targeted reanalysis of known failures**, not a fresh, blinded holdout. Frozen-before-run recovery protocol SHA256 `418a6e71fedc8cde2b8dee744f7b673c9154e9d6be8a98c26aa526e89c21ccb3` specified 4 independent initializations, 3 SciPy numerical solvers, 3 actual R retries per dataset and score / coefficient / information checks. All original fixture hashes checked.

## Initial recovery experiments

For each dataset, several independent numerical starts yielded Jeffreys adjusted-score roots. Actual `R 4.5.0 / brglm2 0.9.2` explicit-start and optimization-setting retries produced **15 fit attempts**: 14 reported convergence; 13 passed the initial numerical reference and adjusted-score checks; **2 refused** even though one of those two reported `converged=TRUE`.

Crucial new issue: a **separately labeled post-hoc** penalized-likelihood and finite-difference audit found **three distinct stationary solutions** to the Jeffreys adjusted score for `all_zero_n160_s06.csv`, with coefficients substantially separated and penalized objective approximately `-0.987351`, `-0.986566`, and `-0.981487`. Each had a small score residual. This demonstrates that score near zero plus positive-definite information **does not establish uniqueness, or a global optimum**, and one reported-converged R attempt also disagreed with the original root by about **0.297** in a coefficient.

**Final strict, research-only disposition: 4/5 datasets have coherent and repeatable numerical recovery across tested starts; 1/5 is wholly REFUSED because of competing stationary roots.** Do not present the 13/15 initial retry count as blanket scientifically validated success. The multi-root refusal gate is a post-hoc safety tightening, not a prespecified performance achievement. Original CH19 failed records remain unchanged.

## Tests and evidence

**10/10** new tests pass; **10/10** again after extracted ZIP replay. Tests cover original failures, fixture SHA256 identity, protocol digest, 15 unique R retry IDs, independent starting values and solvers, finite-difference gradient, detected multi-root ambiguity, conservative refusal, and no production promotions.

Reproducibility ZIP: `Cognitum_CH_C14_20_Zero_Event_Independent_Recovery_2026-11-02.zip`, SHA256 `807ee5fbf614dff6bfacfb8f35ebde1b1a48ed94b8b5136724be343e7d116278`; **21/21 internal SHA256 payload checks verified**. Contains frozen protocol, source scripts, targeted 5 original CSV datasets + CH19 original receipts, all 60 SciPy candidate solves, 15 actual R retry outcomes, separate initial and post-hoc audits, ten tests, README and detailed engineering report. R executables and third-party Debian packages not redistributed; the isolated local R runtime used for execution.

## Gate state

Scoped numerical recovery investigation **PASS, one mandatory refusal**. No causal-effect interval coverage, independent global optimum proof, external `logistf` package equivalence, study-design provenance, or independent statistical review established. C14 scientific release **NO-GO**. Further work should investigate why Jeffreys penalized likelihood has competing stationary solutions in this edge case and use genuinely independent implementations/multi-start optimization before changing any estimator.
