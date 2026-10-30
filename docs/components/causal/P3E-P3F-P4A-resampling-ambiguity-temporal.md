# Cognitum C14 P3E/P3F/P4A — Bounded Causal Diagnostics, Not Causal Proof

**Date:** 2026-10-28. **Maturity:** synthetic reference / functional tests (Linux Python 3.13). **Parent:** immutable C14 P3D source checkpoint (`d7f1779281f0e0ce0e42ab9c6a1f4639324946eee2a685c2016985eebbe91ff2`).

## Design commitments

- Extend C14 without mutating prior schemas. New typed Protobuf contracts: `stability.proto`, `ambiguity.proto`, `temporal.proto`; their compiler-derived bindings live under `cognitum/proto` and are independently descriptor-checked. No JSON is used as an internal execution contract.
- Preserve host-gated, default-off reference operations; the Python `host_authorized` flag is **not actual Lu authentication** and cannot substitute for Windows Job Object process isolation, trusted host admission, or transitive offline dependency review.
- Preserve proper epistemic labels: candidate edges and observational predictive associations are **not proven causal mechanisms**. Neither statistical significance, stability frequency, Markov-equivalence classification nor calculation replay independently verifies a real-world causal graph.
- Each operation bounds input bytes, sample sizes, variable counts, trials, time, and/or tests, uses request digests, denies on malformed input, and publishes **no partial statistical result** after resource exhaustion. Receipts replay arithmetic and source data *in the same runtime*, not independent external causal proofs.

## P3E — Statistical skeleton stability and permuted negative controls

`cognitum/causal_stability.py` reuses the P3B bounded PC-stable undirected reference on selected rows. Three modes: without-replacement subsamples, bootstrap-with-replacement, and subsamples with one prespecified variable permuted. Uses pinned seeded NumPy PCG64, 2–16 repetitions, 60–400 rows per repetition, 2–8 variables inherited from discovery, and explicit time/test budgets. It reports the frequency of candidate undirected edges over successful repetitions, including edges never selected, plus hash-bound draw-index and canonical reference-result digests. Failed/degenerate/resource-exhausted repetitions produce an inconclusive result with no partial edge counts.

**Statistical interpretation:** An edge selected in 75% of resamples is *not* assigned a 75% probability of being causal. Resampling selection is sensitive to sample dependence, algorithm settings, numerical versions, and data generation; shuffled negatives can show residual false associations due to finite samples. These outputs are descriptive stability diagnostics, not valid posterior or calibrated causal edge probabilities.

## P3F — Exhaustive DAG orientation ambiguity for small skeletons

`cognitum/causal_ambiguity.py` requires a replay-verified P3B skeleton and exhaustively enumerates acyclic edge orientations for at most 6 variables, 9 edges and 512 total orientation assignments. DAGs are partitioned into observational Markov-equivalence classes according to skeleton and unshielded collider signature. It reports class size and arrows shared by *every DAG in an assumed class*, not empirically verified causal directions. A caller may optionally supply the exact unshielded collider signature as an **assumption**; the engine never attests that those colliders were discovered from data.

For X–Y–Z, the noncollider class contains three DAGs and the collider class X→Y←Z contains one. For a 3-clique, all six acyclic orientations lie in one class without compelled arrows. Input/source tampering and fabricated orientation receipts are rejected. **This is not full PC orientation, CPDAG construction, PAG/FCI with latent confounding, or causal identification.** Those remain research/back-end gates.

## P4A — Lagged conditional predictive screening (not temporal causal inference)

`cognitum/causal_temporal.py` estimates nested ordinary least-squares regressions on a full matrix of past lagged variables. For each source→target at lag `k`, remove only that source-lag coefficient and compare restricted/full residual sums of squares with a one-degree-of-freedom F statistic. Uses SciPy survival-function p-values and a Bonferroni familywise adjustment; source/target/lag indexing and printed estimates are deterministic for an unchanged numerical stack. Bounds: 2–4 variables, 100–400 equally spaced ordered samples, lag depth 1–3, explicit interval and execution timeout.

**Statistical interpretation:** These are conditional lagged **predictive** associations (Granger-style) only. The classical F p-value assumes a valid regression noise model and appropriate residual properties, which this slice does not test. Nonstationarity, unobserved common causes, time-varying confounding, measurement timing errors, nonlinear dependence and instantaneous feedback can invalidate a causal reading. A significant lagged predictor must never be phrased as established intervention effect. No temporal SCM, state-space latent noise inference or do-operator is implemented.

## Maturity/gates

| Gate | Result |
|---|---|
| P3E seeded resampling and shuffled negative control | Synthetic reference implemented; verification in evidence JSON |
| P3F small DAG class enumeration | Synthetic reference implemented; verification in evidence JSON |
| P4A conditional lagged predictive screen | Synthetic reference implemented; verification in evidence JSON |
| Independent Protobuf schema compilation | Required in local verification; check evidence JSON |
| Genuine DoWhy 0.14 / EconML 0.17.0 / causal-learn 0.1.4.8 | **Not executed** — dependencies unavailable in this runtime |
| Real temporal discovery tool Tigramite | **Not integrated or tested** |
| Windows x86-64 packaged worker / Job Object isolation | **Not verified** — no Windows target process executed |
| Authenticated Lu admission and model-directed tool use | **Not verified** |
| Real model trials / quantization-stratified paired study | **0 runs; preregistered methodology only** |
| Comprehensive production regression / CI / adversarial dataset study | **Pending** |

### Reproducible local commands

```shell
PYTHONPATH=.:tests python -m unittest tests.test_c14_p3e_stability tests.test_c14_p3f_ambiguity tests.test_c14_p4a_temporal -q
PYTHONPATH=.:tests python -m unittest discover -s tests -p 'test_c14*.py' -q
PYTHONPATH=.:tests python -m unittest discover -s tests -p 'test_c13*.py' -q
PYTHONPATH=.:tests python tools/run_c14_p3ef_p4a_smoke.py
PYTHONPATH=. python tools/verify_protobuf_schemas.py --require
python -m compileall -q cognitum evals tests tools
```

## Next C14 milestones

- Finish the **genuine** external-runtime and native Windows/Lu security gates with separately built/attested environments; no Python flag alone constitutes authenticated authority.
- P4B research/reference: time-indexed SCMs with explicit structural mechanisms, intervention propagation and abduction/action/prediction. Keep fundamentally separate from predictive screens and demonstrate conditional feedback semantics in unrolled time.
- P4C: temporal diagnostics (stationarity, autocorrelation, irregular sampling, time-varying confounding) and appropriate algorithms only after assumptions and baselines are documented.
- Preserve C13 Bayesian integration as a typed future bridge; a statistical posterior must never be quietly treated as verified causal structure.
