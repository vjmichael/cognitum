# C14 P3C — EconML and causal-learn optional worker integration candidate

Date: 2026-10-27. Status: **implemented, subprocess contract tested; mature runtime unverified**.

## Verified references / versions

- EconML **0.17.0** (PyPI release 2026-07-31): https://pypi.org/project/econml/ ; `LinearDML`, treatment nuisance classifier and outcome regressor. Python 3.13 Win64 wheel exists. MIT license; dependency graph/license audit pending.
- causal-learn **0.1.4.8** (PyPI release 2026-07-11): https://pypi.org/project/causal-learn/ ; `causallearn.search.ConstraintBased.PC.pc(..., indep_test='fisherz', stable=True)`. Package metadata lists MIT license. Wheelhouse and Windows ABI test pending. PC docs: https://causal-learn.readthedocs.io/en/latest/search_methods_index/Constraint-based%20causal%20discovery%20methods/PC.html
- The current executor cannot install either distribution: configured package source DNS resolution failed. Neither mature runtime is locally present. **No successful real-library execution is claimed.**

## Native contract

`proto/cognitum/causal/v1/mature_worker.proto` / `cognitum/proto/causal_mature_pb2.py`:
- Explicit backend enum, separate `oneof` task shapes (P3A conditional effect or P3B graph discovery), seed and execution budgets.
- Candidate-only outputs, request SHA-256, trace ID, exact backend/version, subgroups or *unoriented* skeleton edges, independent structural receipt and metadata-only audit.
- Input/output frames are binary Protobuf only. None of these outputs can assert proof of causal assumptions, CI calibration or identified graph structure.

## Backend semantics

**EconML candidate:** bounded aggregate binary observations expanded to rows, with pre-treatment modifier indices as `X`, other supplied backdoor adjustment variables as `W`, treatment `T`, outcome `Y`. `LinearDML` uses fixed-seed bounded random-forest nuisance models and two-fold cross-fitting. Output is the *model-estimated* conditional effect per observed modifier state. P3A exact standardized subgroup risk difference appears as a reference comparator, **not** an expected equality. Differing estimands, specification errors and finite-sample bias remain possible. No statistical confidence claims from this adapter.

**causal-learn candidate:** bounded, complete Gaussian numeric dataset; PC with `fisherz`, `stable=True`, output only an undirected adjacency skeleton. A directed/oriented PC result is deliberately reduced to presence/absence edges because graph orientation from observational data is not verified causation. Limits: 2–4 variables, 60–400 rows, fixed maximum 2 conditioning variables, `max_tests=250`, and outer 30-second deadline; PC internal conditional-independence call counts are **not** individually instrumented. No claims for hidden confounders, selection bias, time series or interventions. Specific orientation, FCI, LiNGAM, nonparametric KCI and structural identifiability are separate future interfaces.

## Safety and provenance

- Disabled unless a trusted host supplies authorization, a backend-specific exact pinned version and source/executable SHA-256, enabled flag, and external OS-isolation attestation.
- Python `-I`, isolated subprocess, narrow environment, bounded output, deadline and process-group kill in Linux tests. **These are not an OS sandbox or Windows Job Object validation.** Any boolean host flag here is development harness state, not cryptographically verified Lu admission.
- Results are rejected if request SHA, task, trace ID, backend ID, pinned version, claimed assurance, group sizes/reference values, numeric distances or skeleton bounds fail request-bound verification. This *does not independently validate EconML estimation or causal-learn's inferred graph*.
- No Lu code, Windows profile, GitHub repository or persistent memory was modified. Worker remains disabled in Lu.

## Remaining gates

1. Approved, hash-locked, license-reviewed *full transitive* offline Win64 CPython 3.13 dependency wheelhouse for both libraries.
2. Run `tests.test_c14_p3c_runtime_gate` in a clean pinned worker environment with both libraries genuinely installed. Positive gates must not be marked passed on skip.
3. Windows Job Object containment, deny network and unapproved filesystem access, enforce process-tree kill and resource budgets, authenticated Lu host admission.
4. More independent real-library statistical baselines, numerical tolerance/coverage, PC graph stability and ambiguity tests with carefully designed synthetic data and multiple seeds.
5. Hardware benchmarking and the paired 10-arm LLM with/without Cognitum experiment **later**, not inferred from these tests.

## Focused verification

```shell
PYTHONPATH=. python -m unittest tests.test_c14_p3c_mature_adapter tests.test_c14_p3c_runtime_gate -v
PYTHONPATH=. python tools/verify_protobuf_schemas.py --require
```
