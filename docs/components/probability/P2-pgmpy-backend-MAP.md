# C13 P2 — pgmpy backend contracts, worker isolation and exact MAP

**Status (2026-10-27): functional reference MAP and worker/adapter integration code; actual installed pgmpy execution NOT verified.** No full benchmark campaign. Source developed and tested on Python 3.13 Linux. No Lu/Windows native integration or production host authentication.

## Established ecosystem selection

- **pgmpy 1.1.2**, released April 30, 2026, MIT licensed. Release: https://pypi.org/project/pgmpy/1.1.2/ ; license: https://pgmpy.org/started/license.html . Optional `probability-pgmpy` packaging extra; do not copy a third-party binary into the checkpoint. No installed pgmpy package in test runtime and package index inaccessible; one real-runtime conditional test is correctly skipped.
- `pgmpy.models.DiscreteBayesianNetwork`, `pgmpy.factors.discrete.TabularCPD`, `pgmpy.inference.VariableElimination` and `BeliefPropagation` (junction-tree exact inference). Documentation: https://pgmpy.org/api/generated/inference/pgmpy.inference.VariableElimination.html ; https://pgmpy.org/api/generated/inference/pgmpy.inference.BeliefPropagation.html . The adapter maps P1 PPM CPTs into pgmpy child-major probability matrices in parent-index order, preserving arbitrary parent orders and factor axes. The matrix translation has a stub-class regression test; NOT a live library parity test.
- PyMC/Pyro/NumPyro remain C13 P3 continuous/hierarchical inference candidates; no invented integration or runtime claims.
- Research extension candidates remain the independently documented 2025 lazy knowledge compilation and 2026 amortized structural inference. No learned inference model has executed, and neither is a certified improvement.

## Actual C13 P2 implementation

- `proto/cognitum/probability/v1/backend.proto` + `cognitum/proto/probability_backend_pb2.py`: backend/query enums, typed nested P1 network query, numerical error tolerance, posterior or MAP result, independent verification receipt, and metadata-only audit. **24 schemas compiled and checked against their bindings.** No user/model-supplied executable path or arbitrary code.
- `cognitum/probability_backend.py`: `REFERENCE_EXACT` offers exact rational joint posterior and MAP assignment for bounded supplied Bayesian networks, with lexicographic MAP tie resolution and independent full-joint oracle. The established backend adapter translates to pgmpy VE/junction-tree BP, mapping CPDs and evidence; its numerical results cannot receive an exact-rational proof label.
- `cognitum/probability_pgmpy_worker.py`: subprocess entrypoint with bounded Protobuf frames; host-owned `WorkerPolicy` pins Python executable SHA-256, worker source SHA-256, backend adapter source SHA-256, and an expected pgmpy version; process deadline enforced via kill. Backend must be explicitly enabled by host in Python reference. Child can be in a different Python environment from Cognitum host. Host controls arguments, working directory and environment; stderr suppressed and stdout bounded in a temporary file. This is NOT OS containment on Windows (Job Objects/AppContainer not integrated) or independent authenticated Lu authorization.
- `verify_graph_receipt()`: independently enumerate bounded joint assignments, check selected MAP assignment against the maximum joint posterior and compare probabilities to exact expected values. No positive receipt when the oracle budget is exceeded, when output was forged, on impossible evidence without an independent proof, or for unsupported/UNKNOWN results. pgmpy numerical tolerance is capped at 100 ppm and defaults to 1 ppm. **Numerical cross-check is not a symbolic proof.** `make_graph_audit()` binds source and result SHA-256, backend identity/version and assurance flags without recording sensitive evidence values.
- An independently checked impossible-evidence result is distinct from an unverified backend failure. If the backend or proof machinery fails, Cognitum returns an explicit UNKNOWN/REJECTED status rather than asserting a posterior.

## Functional gates and evidence

The focused tests include exact posterior and MAP queries, evidence and factor ordering, tying and disambiguation, invalid inputs, host gates, exhausted budgets, tampered model probabilities, forged receipts, worker SHA-256 checks, worker missing-dependency handling, and stand-in library API mapping. The integration-test stand-ins do **not** count as actual pgmpy runtime validation.

```bash
PYTHONPATH=.:tests OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python -m unittest tests.test_c13_p2_backend -q
PYTHONPATH=.:tests python tools/run_c13_p2_smoke.py
PYTHONPATH=. python tools/verify_protobuf_schemas.py --require
```

Actual P2 test count, grouped regressions, and skipped runtime test appear in `P2-functional-test-evidence.json`. The optional runtime check is `test_real_pgmpy_worker_when_installed`: enable it only with the genuine dependency present and host-pinned policy. On a Windows x86-64 Lu build, test expected wheel integrity, runtime dependencies, child/descendant process confinement, host-held permissions and cancellation before distribution.

## Limitations / next work

- pgmpy, Pyro, NumPyro and PyMC were **not installed or executed** in this test environment. `pip install --target` attempted but no package source was available. Accordingly **this is an adapter-ready P2 milestone, not completed third-party runtime integration**. Validate VE and BP against a real pgmpy 1.1.2 worker on Windows before production promotion.
- Host/worker version equality is checked for successful results; Python/adapter source hashes are host-pinned, but the installed pgmpy package's full file manifest and transitive wheel hashes are not yet enforced. This is NOT a fully secure third-party sandbox. Production memory/CPU quotas, Windows descendant termination and authenticated Lu CE permissions still open.
- The exact interpreter and cross-check have intentionally finite resource limits. The bound is a correctness/security feature, not evidence that the prototype matches pgmpy's large-network performance.
- This supports **discrete finite Bayesian networks only**. No causal interventions, Markov networks, continuous random variables, HMC/NUTS/SVI, Bayesian structure/parameter learning, dynamic models, or held-out calibration guarantees in this phase. Distinguish these omissions from standard library coverage.
- Do not run major benchmarks before the full portfolio is built, per owner decision. Benchmark-ready traces are present, but no Lu end-to-end collector contract has been certified.
