# C13 P1 — Discrete Bayesian graphical models, exact conditioning and sampling

**Development gate:** Functional, bounded offline reference; **not a production Lu capability, not a full probabilistic programming system, not yet a runtime integration with pgmpy/PyMC/NumPyro/Pyro**. No comparative performance benchmark or promotion decision.

## Standards and mature ecosystem assessment (October 27, 2026)

- **pgmpy**: https://pgmpy.org/api/generated/inference/pgmpy.inference.VariableElimination.html — mature discrete Bayesian networks, variable elimination, belief propagation, MAP, causal inference, parameter and structure learning. MIT license: https://pgmpy.org/started/license.html. Preferred **C13 P2** optional discrete network engine. Not installed in this environment; no execution claim.
- **PyMC**: https://www.pymc.io/ — continuous/hierarchical Bayesian probabilistic programming and MCMC. Substantial runtime/packaging requirements; not integrated. Local import raises an error.
- **Pyro**: https://docs.pyro.ai/en/dev/poutine.html — PyTorch-based probabilistic programming, enumerative inference and stochastic variational inference; not installed.
- **NumPyro**: https://num.pyro.ai/en/latest/getting_started.html — JAX-backed HMC/NUTS/SVI and probabilistic programs; not installed. GPU/JAX packaging needs investigation before any Windows release.
- **NumPy/SciPy** present in Linux container, but not used as an external inference solver; Python rational factor arithmetic provides an auditable, deterministic reference and independent oracle. **Do not call this a mature-library replacement.**
- **Research extensions (not implemented):** Fan et al., *Amortized Structural Variational Inference*, AISTATS 2026, https://proceedings.mlr.press/v300/fan26b.html; Bowers et al., *Stochastic Lazy Knowledge Compilation*, PLDI 2025, https://doi.org/10.1145/3729325. Investigate independently, not as guaranteed improvements. Separate host-approved research backend manifests; report dataset, model version, domain, resource costs, and citations when benchmark phase begins.

## Implemented C13 P1

- `proto/cognitum/probability/v1/inference.proto` and compiler-checked `cognitum/proto/probability_pb2.py`: typed BN nodes, parent indexes, enumerated states, row-major integer-ppm CPTs, hard and likelihood (soft) evidence, joint target query, inference mode, audit/receipt.
- `cognitum/probability.py`: exact rational finite factor variable elimination, greedy small-factor elimination ordering, joint posterior distribution, evidence probability, zero-evidence detection, seeded likelihood weighting with effective sample size, independent full-joint enumeration and malicious result checking. Exact output is certified **only** when independent full-joint enumeration fits the verifier cap.
- Acyclic arbitrary-parent-order DAG; normalized nonnegative CPTs and bounded memory. Hard evidence can be on a query target; soft and hard evidence can apply to the same node.
- Strict Protobuf canonical framing, no model-generated Python/SQL, request-framed host gates, hash-linked data-minimized audit record. `host_authorized=True` is a test-only input; NOT a Lu-authenticated credential. Never infer real-world statistical calibration from the synthetic Bayesian network's internal consistency.
- Status distinctions: EXACT_POSTERIOR, APPROXIMATE_POSTERIOR, IMPOSSIBLE_EVIDENCE, UNKNOWN_INFERENCE, REJECTED_INFERENCE. No approximate optimality or proof claim. Zero observed Monte Carlo weight yields UNKNOWN, **not** proof of impossible evidence. Independent verification is a separate call with an intentionally different full-joint algorithm.

## Bounds and assurance

At most 12 variables, each 2–8 states; at most 8192 entries per CPT; at most 32768 potential entries for any constructed factor (host request can lower); at most 512 output joint states; 32768 assignments for independent verification (request can lower); 10,000 sampling draws; 5,000 ms cooperative execution budget; 64 KiB canonical request and response frames. A factor cap returns `UNKNOWN`, never `IMPOSSIBLE_EVIDENCE`. A cooperative time budget is NOT a hard OS kill; external Lu worker containment remains required.

**Exact**: sound for supplied normalized finite DAG CPTs. Returns an exact rational posterior even when the independent verifier budget is exceeded, but `independent_posterior_verified=false` and no certified receipt in that case. **Approximate**: seeded likelihood weighting yields reproducible weighted estimates, not confidence calibration or a mathematical certificate. Warnings for low effective sample size and advanced convergence diagnostics need richer future contracts.

## Tests and future components

- `PYTHONPATH=.:tests python -m unittest tests.test_c13_probability -q`
- `PYTHONPATH=. python tools/run_c13_smoke.py`
- `PYTHONPATH=. python tools/verify_protobuf_schemas.py --require`
- Regressions should set `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1` when running legacy HiGHS-dependent C11 tests in constrained CI.

**C13 P2:** actual pgmpy installed and called in a pinned offline worker, query/MAP/likelihood evidence and approximate sampling parity, independently verify on small cases; add backend manifest and license distribution review. **C13 P3:** continuous/hierarchical models, HMC/NUTS/SVI through mature optional runtime, posterior predictive checking, calibrated diagnostics; don't label MCMC samples mathematically verified. **C13 P4:** optional research algorithms, pinned provenance, reproducibility, benchmark-ready metadata; postpone actual performance comparisons until portfolio complete. **C14 causal inference is separate:** observational posteriors are not interventions or evidence of causal effects.

**Provenance:** C13 P1 extends the immutable C12 P4 Library archive. Lu and GitHub are unchanged. Python code is only a reference; rustc/Windows and production auth gates remain open.
