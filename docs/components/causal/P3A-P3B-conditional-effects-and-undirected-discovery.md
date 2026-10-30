# C14 P3A/P3B — Conditional effect heterogeneity and bounded PC-stable skeleton

**Date:** 2026-10-27. **Scope:** experimental/reference-only checkpoint, **not full C14 P3**, and not Windows Lu production qualified.
**Parent:** C14 P2B G1 offline wheelhouse and footprint checkpoint (immutable).

## Aim and status

Add two independent, Protobuf-native, offline invocations that preserve P1/P2A/P2B unchanged:

1. **P3A conditional empirical treatment-effect reference:** `cognitum/causal_heterogeneity.py`, schema `proto/cognitum/causal/v1/heterogeneity.proto`. For *binary treatment, binary outcome*, uses P2A's assumed DAG and validated backdoor adjustment. Effect modifiers are intentionally restricted to a **subset of the supplied pre-treatment adjustment variables** (max two). Group-level exact empirical risk differences are weighted by each group's observed mix of the remaining adjustment strata, and the weighted combination is cross-checked against P2A's overall empirical adjustment estimate through an alternative arithmetic route.
2. **P3B undirected discovery candidate:** `cognitum/causal_discovery.py`, schema `proto/cognitum/causal/v1/discovery.proto`. Implements a bounded **PC-stable skeleton phase only**, using linear Gaussian Fisher-z approximate conditional independence, stable adjacency snapshots for each depth and deterministic pair/separating-set enumeration. It returns **undirected edges, separating sets and p-values**, not a CPDAG, PAG, oriented graph, causal discovery certificate, neural discovery, or intervention estimator.

Both have typed request-bound digests, metadata-only audit, no implicit persistence of raw samples, strict input and budget bounds, fail-closed explicit unsupported paths, and unauthenticated **development flags** (`host_authorized`, `enabled`) that must not be mistaken for an actual Lu credential or OS security boundary. Both have separate verification receipts: P3A arithmetic cross-checks; P3B deterministic replay **not independent validation of causal structure**. Causal assumptions are always unproven.

## Method restrictions and mathematics

### P3A: exact conditional empirical standardization

Partition adjustment strata `z` by modifier value `m` and compute, within each `m`, the weighted risk difference

`sum_z P_emp(z | m) * [P_emp(Y=1 | X=1,z) - P_emp(Y=1 | X=0,z)]`.

Every `(X,z)` cell must satisfy P2A's original minimum-arm overlap check. All cell masses are exact `Fraction`, and subgroup results must aggregate to P2A's global adjusted estimate. A second arithmetic expression independently re-weights treatment arms. Confidence intervals are **approximate normal plug-in Wald intervals**, not calibrated guarantees. It reports heterogeneity descriptively and makes **no significance or subgroup-selectivity claim**. Conditioned effect interpretation requires correct pre-treatment modifiers, the assumed causal DAG, exchangeability, positivity and outcome/treatment measurement validity; none are proven by observational tables.

Limitations: aggregate fixed binary endpoints only, modifiers must be a subset of adjustment variables, cannot estimate effects for unobserved subgroups, no AIPW/DML/CausalForest methods, and no dynamic or latent-confounder identification.

### P3B: PC-stable undirected Gaussian skeleton

For each undirected candidate pair, test partial correlation with Fisher-z `p = erfc(|atanh(r_partial)| sqrt(N - |S| - 3) / sqrt(2))` across ordered subsets of the frozen adjacency set. An edge is dropped after a conditional independence result `p > alpha`, with the separating set and p-value retained. The result is **undirected** and only a screening hypothesis. It is neither a causal DAG nor a complete implementation of the PC algorithm: collider orientation, Meek rules, background knowledge, and confidence/falsification analysis remain unimplemented.

- 2–8 columns, 60–400 rows, conditioning depth at most 2, max 250 CI tests and 5000 ms, max request 128 KiB. Invalid/degenerated covariance, collinear conditioning sets, exhausted test budgets, runtime errors and unauthorized calls fail closed.
- Assumes linear Gaussian CI testing, independent observations, causal Markov/faithfulness and no unresolved hidden confounding or selection bias. Those conditions are not checked.
- The nominal CI p-value **is not a probability that the edge is causal**, and multiple-testing adjustments and stability-selection are not yet implemented.
- Does not support discrete or mixed variables, time-lagged graph discovery, temporal causality, neural methods, FCI/PAGs or interventions.

## Mature ecosystem and research extensions

- **DoWhy 0.14:** mature estimate/identify/refute APIs; an isolated P2B candidate adapter exists but actual installed execution and Win64 confinement remain **open gates**. Never use unavailable status as success.
- **EconML 0.17.0:** mature candidate for conditional effects and doubly robust learners; published CPython 3.13 Windows x86-64 wheels available as of 2026-07-31, but not downloaded, pinned into a reviewed lock, executed or registered with Lu. `ECONML_CATE_OPTIONAL` explicitly reports backend unavailable.
- **causal-learn:** PC, FCI and related causal-discovery algorithms; optional future host-isolated adapter `CAUSAL_LEARN_PC_OPTIONAL` currently returns backend unavailable. P3B reference is not equivalent to full causal-learn.
- Later optional research: nonlinear/differentiable structure learners, temporal causal discovery, Bayesian SCM/C13 posteriors, uncertainty-aware CPDAG/PAG outputs. Each requires a separate verified adapter and tests.

Public references: https://www.pywhy.org/dowhy/v0.14/dowhy.html ; https://pypi.org/project/econml/ ; https://causal-learn.readthedocs.io/en/latest/search_methods_index/Constraint-based%20causal%20discovery%20methods/PC.html

## Interfaces / security / test instructions

- `HeterogeneityRequest.method` explicitly selects reference or unsupported EconML. The reference's modifier subset and full P2A backdoor result are checked before a successful estimate.
- `DiscoveryRequest.method` explicitly selects reference or unsupported causal-learn. Returned `orientations_inferred` is **always false**.
- Both expose bounded digests, status, reason, backend/version and metadata-only audit. No raw input or output data is included in audit records.
- No worker or tool is registered with Lu. Python boolean flags are development test controls, not authenticated admission or confinement.

Run from repository root:

```
PYTHONPATH=. python -m unittest tests.test_c14_p3_heterogeneity tests.test_c14_p3_discovery -v
PYTHONPATH=. python tools/verify_protobuf_schemas.py --require
```

## Gates that remain unresolved

- Genuine DoWhy 0.14 execution, real offline approved Win64 dependency lock, Windows Job Object containment, Lu authenticated supervision, dependency licensing/ABI review, and end-to-end network/filesystem denial checks.
- Mature EconML CATE and causal-learn PC/FCI backends: workers and positive runtime tests, independent numerical and graph comparisons, ambiguity/provenance checks, host policy and binary pinning.
- Robustness validation: larger synthetic suites, observational bias/missingness/selection stress, many seeds, multiple-testing policy, real datasets reviewed for their causal assumptions, comparable C03 performance/energy measurements, tiny LLM + Lu end-to-end experiments.

This checkpoint claims *synthetic functional coverage only*. P2B Windows and real DoWhy gates have not been passed. A sub-1B LLM is **not** included in this source checkpoint, and no model efficacy claim is made.
