# Cognitum CH-C14-06 — Design-aware research routing and rare-outcome inference

**2026-11-02 | Linux local research | Engineering PASS, Scientific NO-GO.** No Lu, Windows, or Cognitum production-estimator modifications.

## Frozen study

Pre-run frozen protocol SHA-256: `4b94a683c475d083209f7263842e3275ed2b624e817d1b162038ef24b9b6e122`. Seven fresh SCM families, n=450 and 1200, 100 independent simulated datasets per family/size: **1,400 datasets**. Four method attempts per dataset: **5,600 attempts**. All have known simulator truth; no oracle truth is used by the router or estimator.

**Research-only router**, separate from G25 and production runtime: it requires a user/external design declaration, routes declared randomized designs to eligible experimental interval methods; observed-W adjusted designs remain `conditional_adjustment_only`; honest declarations of hidden confounding, coarsened continuous confounding, or unidentified design cause refusal. It routes sensitivity-only requests to the original pinned G25 guard. Every result has `automatic_causal_certification=False`; a text declaration is **not independent design authentication**.

Compared candidate interval methods: unadjusted Neyman/Wald variance, poststratified sandwich/delta variance, 299-replicate full-row multinomial-equivalent bootstrap, and a conservative Bonferroni–Wilson per-arm difference bound. **Naming correction:** code's frozen method identifier `newcombe_wilson_rct` is not the canonical Newcombe hybrid-score interval. Report only as **Bonferroni–Wilson bound**.

## Principal results

| Family / n | Neyman truth inclusion | Poststratified sandwich | Full-pairs bootstrap | Bonferroni–Wilson |
|---|---:|---:|---:|---:|
| RCT heterogeneous, 450 | 95/100 | 93/100 | 93/100 | 100/100 |
| RCT heterogeneous, 1200 | 94/100 | 93/100 | 93/100 | 100/100 |
| Stratified RCT heterogeneous, 450 | not routed | 95/100 | 95/100 | not routed |
| Stratified RCT heterogeneous, 1200 | not routed | 92/100 | 92/100 | not routed |
| **Rare randomized heterogeneous, 450** | **86/100** | **86/100** | **85/100** | **100/100** |
| Rare randomized heterogeneous, 1200 | 95/100 | 95/100 | 94/100 | 100/100 |
| Adjusted observational heterogeneous, 450 (conditional only) | not routed | 92/100 | 92/100 | not routed |
| Adjusted observational heterogeneous, 1200 (conditional only) | not routed | 95/100 | 94/100 | not routed |

For rare randomized n=450, mean widths were Neyman 0.03401, sandwich 0.03407, full-pairs bootstrap 0.03334, and Bonferroni–Wilson 0.06911. The first three undercover in this holdout; the fourth is much too wide to pass a 95%-nominal Wilson-compatibility screen (100/100 containments). **No candidate passed the small-sample rare-outcome primary screen.** Only 100 trials/cell; these are descriptive research results and not tight proof of coverage calibration.

Totals: **2,400 issued intervals**, **3,200 refusals** (2,400 unsupported designs, 800 incompatible method/design combinations), **0 causal certifications**, **0 promotions**. The adjusted observational case is never represented as verified causal identification.

## Verification

- Exact original G25I and guard pins preserved and checked: `f881ae12bdae90fa4acec0bae9046e5580f5ddad80a1794006c3da5a3f6621e4` and `3480952a031d17061615eaa92597e7b2f0df22495954d5656aeeb6b51322f64c`.
- New router/component regression **10/10 pass**.
- Independent post-holdout auditor rechecked **1,400 dataset groups and 5,600 method records**, 40 numerical-method examples, and 2,500 per-method bootstrap distribution equivalence draws.
- All **10 archive payload SHA-256 hashes** checked.
- Reproduction archive: `Cognitum_CH_C14_06_Design_Aware_Router_Heterogeneous_Rare_2026-11-02.zip`; archive SHA-256 `54041666096eb176b409085a605127ed7e09575b0290a7fdc26c25ad32bfd4c8`. Contains sources, original frozen protocol, case results, audit, test suite and report. The exact G25 files are an external pinned dependency restored in CH-C14-03; they were **not** rewritten or copied into this archive.

## Unresolved issues and CH-C14-07

- Study-design self-declaration is **not** an authenticated clinical or causal design; false attestation remains a serious hazard. Router is a research demonstration, not a safe production causal admission policy.
- Bonferroni–Wilson is overly conservative; ordinary Wald, stratified, and pairs-bootstrap intervals undercover for the small rare scenario. Candidate mathematical improvement and new frozen holdout needed.
- Real HC3/cluster robust, cross-fitted AIPW, continuous heterogeneous effects, rare-event separation, multi-source observational validity and independent external statistical code review **not tested** here. Do not advertise them.
- CH-C14-07: preregister true Newcombe-style score/hybrid and alternative rare-event inference, finite-sample variance and propensity-aware diagnostics, and adversarial false-design attestations; compare against independent implementations. Keep G25N scientific NO-GO (12/12 width failures), incomplete LR inversion and analyst Gamma validity gates untouched.

**No C14 scientific promotion**: engineering research selector works under the supplied oracle design labels; it does not prove identification in unknown-world data. GitHub remains a repository and milestones record, not a development hub.
