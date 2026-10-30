# C14 P4B — Exact Time-Indexed Structural Causal Model Reference

**Checkpoint:** 2026-10-28, Linux Python 3.13 source-only functional reference. **No real-world causal identification, Lu host integration, or Windows OS security gate.**

P4B is intentionally separate from P4A. P4A tests whether past variables help *predict* future values in observed time series. P4B instead evaluates observational, interventional and counterfactual queries **under a supplied structural causal model**. Neither output substitutes for the other.

## Typed interface and semantics

- `proto/cognitum/causal/v1/temporal_scm.proto` + compiled descriptor-bound `cognitum/proto/causal_temporal_scm_pb2.py` define time-indexed binary/small finite variables, innovation distributions, ordered lag-0/lag-1 dependencies, flattened structural-function tables, factual observations, a single `do` intervention, and time-indexed target queries.
- `cognitum/causal_temporal_scm.py` translates time slices to the existing **C14 P1 exact finite SCM** and reuses its independently checked output. Slice 0 uses explicit initial distributions. At subsequent slices, independent step-indexed innovation variables drive deterministic transition tables. Shared exogenous noise across time is **not implemented** in P4B.
- Lag 1 parents permit feedback across time (X[t] depends on Y[t−1] and Y[t] depends on X[t−1]) while the unrolled causal graph remains acyclic. Lag 0 parents must be earlier in template order, ruling out contemporaneous cycles. Arbitrarily lagged, continuous-time, dynamic intervention policies and latent state-space estimation are not implemented.
- For a counterfactual, the underlying P1 engine conditions on the factual observations to constrain the joint exogenous world, overrides the chosen node mathematically, and predicts the alternative world with the **same exogenous realization**. A `do` event never authorizes an actual operation on a device.
- Exact posterior cells and factual evidence mass are returned in canonical rational strings, with the full unrolled model digest, request digest, status, and finite-model verification flag. Replay receipts independently re-run the unrolling and exact finite solution; neither receipt nor hash proves the model's causal assumptions.

## Bounds and assurance

Input strictly bounded: 1–3 variables, 2–4 steps, at most 8 total finite exogenous noise variables, 2–4 states per variable/innovation, maximum 4096 exogenous assignments, maximum 4096 entries per structural table, and 5000 ms P1 deadline. The builder rejects malformed states, graph cycles, forward-time references, duplicate evidence, impossible resource requests, out-of-range interventions and unsupported operations. No partial posterior is published after a failed underlying model validation.

The only allowed success state is exact evaluation **within a host-supplied SCM**, with independent P1 checking and hash-bound receipt replay. Models are assumed rather than learned or independently attested. In particular, intervention predictions are not automatically identified from observed data. The Python `host_authorized` parameter is an offline test stub, never a real Lu authentication or Windows isolation mechanism.

## Synthetic verification fixtures

- A binary autoregressive XOR process with independent innovations demonstrates that unconditioned intervention and counterfactual-abduction queries yield different answers. With factual history all zeros, `do(X0=1)` predicts `X2=1` in that same inferred exogenous world; before conditioning, a time-zero intervention leaves the symmetric two-step marginal uniform.
- A two-variable feedback example demonstrates effects through lag-1 edges without a within-slice cycle.
- Non-supporting factual evidence returns `IMPOSSIBLE_EVIDENCE` instead of a made-up counterfactual.
- Host-denial, disabled-by-default, invalid noise normalization, malformed transition tables, invalid lags, impossible input budgets and forged verification claims are rejected.

Refer to `P3E-P3F-P4A-P4B-functional-test-evidence.json` for actual test counts. Run:

```shell
PYTHONPATH=.:tests python -m unittest tests.test_c14_p4b_temporal_scm -q
PYTHONPATH=. python tools/verify_protobuf_schemas.py --require
```

## Remaining gates

No DoWhy, EconML, causal-learn, Tigramite or other external temporal causal runtime was exercised. Windows x86-64 Job Object confinement and authenticated Lu host permissions remain unverified. No 10-arm / quantization-stratified LLM test has run. A later P4C should cover residual/stationarity diagnostics and support for irregular sampling with mature baseline comparison. Continuous/latent time-varying structural mechanisms, Bayesian posterior uncertainty over mechanisms, and credible learned graph structures remain future research adapters rather than claimed P4B features.
