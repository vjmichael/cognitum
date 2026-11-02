# Cognitum CH-C14-08 — Rare-event exact outer bounds and design provenance

**2026-11-02 | Engineering PASS; scientific release NO-GO.**

Standalone Linux research work only; no Lu, Windows, G25, or Cognitum production estimator changes. Follow-up to CH-C14-07.

## Frozen study and implementation

- Pre-holdout protocol SHA-256: `3d569dc1c65c8be2ed21ef42cfd7e612026c36ef5d1d6d78857865679ddea2e7`.
- Six new SCM families (three independent randomized; hidden confounding masquerading as RCT; adaptive W-based assignment misclaimed RCT; randomized assignment with selectively missing outcomes), n=240 and 800, 100 independent seeds per family/size: **1,200 datasets**, four methods per dataset, **4,800 method attempts**.
- Four interval methods: Wald, true Newcombe (statsmodels), Agresti–Caffo (statsmodels), and conservative simultaneous Clopper–Pearson risk-difference outer bound. The latter uses alpha=.025 per-arm two-sided CP limits (Bonferroni for two risks), then difference [l1-u0,u1-l0]. Its at-least-95% risk coverage holds *conditional on the arm-binomial assumptions*, not by virtue of attestation.
- Research router binds protocol, enrollment roster, allocation commitment, observed count and aggregate result using hashes and a **hardcoded fixture-only** HMAC. Refuses false/unsupported design labels, selective missing outcomes and malformed/tampered records if the test issuer refuses to sign. **A dishonest or incorrect issuer can still sign a false scientific declaration or fabricated aggregate; explicit unit tests demonstrate this limitation.** Do not treat HMAC as real-world study authentication.

## Holdout results

| Family | n | Wald truth inclusion | Newcombe | Agresti–Caffo | Bonferroni–CP |
|---|---:|---:|---:|---:|---:|
| Rare RCT | 240 | 83/100 | 100/100 | 100/100 | 100/100 |
| Rare RCT | 800 | 97/100 | 100/100 | 100/100 | 100/100 |
| Very rare RCT | 240 | **42/100** | 100/100 | 100/100 | 100/100 |
| Very rare RCT | 800 | **69/100** | 100/100 | 100/100 | 100/100 |
| Heterogeneous RCT | 240 | 95/100 | 95/100 | 95/100 | 100/100 |
| Heterogeneous RCT | 800 | 93/100 | 93/100 | 93/100 | 100/100 |

**2,400 reports issued, 2,400 unsupported/missing/refused**; zero auto causal certifications. The exact CP outer method's observed 100/100 truth inclusion in every eligible cell fails the predeclared nominal 95% Wilson compatibility criterion (Wilson lower ≈96.3%). Its average widths were 1.214–1.646x Newcombe; five of six positive cells also exceeded the 1.25x prespecified width ceiling. Thus **all six eligible cells fail the joint calibration/precision gate**. Do not reframe conservative coverage as nominal calibration.

## Execution and verification

- **15/15 new tests passed** (including two deliberate false-trusted-issuer counterexamples).
- **12/12 unchanged CH07 tests passed**.
- **68/68 unchanged pinned G25 guard/host/supervisor tests passed** in a fresh rerun.
- Independent audit (does not import candidate source): **1,200 dataset groups and 4,800 records**, all **2,400 numerical intervals independently recomputed**, max absolute discrepancy **1.11e-16**.
- Archive: `Cognitum_CH_C14_08_Rare_Event_Exact_Design_Provenance_2026-11-02.zip` SHA-256 `8a42e94e8cdafe53d18d3ceb2eb0a8b2d0476140f8e6b797cd5dd67dd68f2510`; **11/11 payload file checksums verified** after packaging.
- The ZIP includes standalone source, frozen protocol, all case-level results and refusal status, 15 tests, independent audit and detailed engineering report. Original G25 source remains in the CH03 archived checkout, unchanged.

## Scientific release status

**NO-GO retained**: This does not reverse G25N's 12/12 precision/calibration failures. A cryptographic allocation hash cannot certify pre-registration timing, concealed/independent treatment assignment, absence of selective exclusion, or correct scientific measurement. Need independent external study-provenance review, broader genuinely untouched holdouts, identification-aware refusal, rare-event interval calibration without unacceptable width, independent R/Firth validation, certified numerical generalization and external statistical review before any production causal-confidence release. No authorization to change production methods or Lu.

**Next gate:** obtain independent externally auditable trial/experiment design records and a mathematically motivated alternative interval procedure, predeclare fresh evaluation and compare honest non-certification/refusal against sound baselines.
