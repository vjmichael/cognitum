# C14 P4E G6 — Genuine uploaded DoWhy source execution and cross-library numerical validation

**Date:** 2026-10-28. **Status:** genuine uploaded-source scientific computation **VERIFIED** on Linux, official DoWhy v0.14 release/runtime **UNVERIFIED**, production Lu/Windows security gate **OPEN**.

## Scope

This checkpoint starts from the immutable G5 ZIP and introduces a **development-only**, explicit-command validation harness (`tools/run_c14_p4e_g6_crosslibrary.py`) and focused tests (`tests/test_c14_p4e_g6_source_comparison.py`). It does **not** modify Cognitum's production/default-OFF DoWhy worker, widen its version selection, or grant model access. G6 uses real `dowhy.CausalModel`, `identify_effect`, `backdoor.linear_regression`, and `placebo_treatment_refuter` against the user's uploaded `dowhy-main (1).zip` source; and `econml.dml.LinearDML` from the previously validated EconML 0.17.0 source runtime. No library API is mocked.

The uploaded DoWhy main snapshot declares `__version__ = "0.0.0"` because its packaging derives the version dynamically from Git metadata that the ZIP does not contain. Its source can be tested, but the archive alone cannot prove that it is the official **v0.14 release**. The source archive contains a documentation symlink, excluded from the scratch extraction. The ZIP's SHA-256 is preserved in the evidence record. DoWhy source and scientific dependencies, compiled wheels, and environment-specific virtual environments are **not bundled** in the Cognitum checkpoint. A source archive from a public repository is not an independently authenticated software supply chain.

## Empirical fixture (same observations, different estimators)

G6 uses the existing C14 P2B fixture of **80 explicitly counted binary observations**, an assumed causal graph with treatment `v1`, outcome `v2`, and adjustment covariate `v0`. The graph and complete backdoor adjustment are *supplied assumptions*, not derived empirical facts. It rechecks the adjustment with two independent graph checks and validates minimum arm overlap.

| Computation | Result | Interpretation |
|---|---:|---|
| Cognitum P2A exact empirical standardization | 0.500000 | Exact average contrast in the supplied fixture |
| DoWhy actual backdoor linear regression | 0.500000 | Source API computes an equal point estimate on this fixture |
| DoWhy placebo permutation refutation (10 simulations, seed 42) | approximately -0.014870 | Diagnostic only; not a certificate of no hidden confounding |
| EconML actual LinearDML, 3-fold, seed 42 | 0.513306 | Mean of model-based predicted effects over same observations |
| EconML conditional effect at `v0=0`, `v0=1` | 0.515585, 0.511028 | Estimates on the same two adjustment strata |

The DoWhy–EconML absolute difference is **0.013306**, not proof the estimators are interchangeable. DoWhy's ordinary regression and EconML's orthogonalized cross-fitted model can estimate different finite-sample quantities when model conditions, sample sizes, nuisance models, positivity, and effect heterogeneity differ. Agreement is a limited numerical smoke test, not a statistical-power study, real-world causal proof, or universal method equivalence.

The developer-only DoWhy worker runs as a subprocess with `-I` and consumes/emits typed **Protobuf**. Its resulting development receipt is bound to the request digest, includes the exact standardized reference and numerical difference, and explicitly identifies the unauthenticated source. **The unmodified production v0.14 receipt verifier rejects the development receipt.** Python `-I` is not OS isolation, and the development harness must never be exposed to LLM-supplied file paths or promoted as a Lu-certified worker.

## Verification results

- **10/10 new G6 genuine-source tests passed**, including real subprocess estimation, placebo, cross-library estimate comparison, request replay, tampered estimates, forged causation statements, and rejected use of a development receipt as a production receipt.
- Selected C14 discovery: **405 methods, 381 pass, 24 optional-runtime skips, 0 failures**. This is without the explicit uploaded-source environment variables, so 9 of the 10 new G6 cases deliberately skip (they must not accidentally run user-provided source).
- Selected C13 discovery: **141 methods, 139 pass, 2 optional-runtime skips, 0 failures**.
- **41/41 Protobuf definitions** matched independent compiler-generated bindings.
- G5 archive passed integrity verification before G6 changes. Original G5 zip and uploaded third-party ZIPs are unchanged.
- Full historical regression and Windows-native checks not run.

## How to reproduce

From the extracted G6 source directory, using a separate, pre-provisioned scientific environment that can import EconML 0.17.0:

```sh
PYTHONPATH=.:tests python tools/run_c14_p4e_g6_crosslibrary.py \
  --python /absolute/path/to/scientific/env/bin/python \
  --source-root /absolute/path/to/checked/dowhy-main \
  --report docs/components/causal/P4E-G6-crosslibrary-evidence.json

COGNITUM_DOWHY_SOURCE=/absolute/path/to/checked/dowhy-main \
COGNITUM_DOWHY_PYTHON=/absolute/path/to/scientific/env/bin/python \
PYTHONPATH=.:tests python -m unittest tests.test_c14_p4e_g6_source_comparison -v

PYTHONPATH=.:tests python -m unittest discover -s tests -p 'test_c14*.py'
PYTHONPATH=.:tests python -m unittest discover -s tests -p 'test_c13*.py'
PYTHONPATH=. python tools/verify_protobuf_schemas.py
```

The DoWhy source path in the child is supplied by the **developer-run harness**, not by the model, and it must be reviewed before executing third-party code. Offline extraction should reject unsafe ZIP members, including symlinks. G6 does not generate trusted provenance from source hashes alone.

## Remaining gates / next work

1. Obtain and independently verify the **DoWhy v0.14 tagged** source or a pinned, reproducible wheelhouse, then run the **existing production** `causal_dowhy_backend` end-to-end worker tests and actual DoWhy placebo with that release. Do not fake `importlib.metadata.version` to close this gate.
2. Broaden cross-library validation to many independent synthetic seeds, heterogeneous effects and identification failures with method-specific baselines and interval coverage. Do not assume CATE, ATE, graph discovery and temporal-screening methods share an estimand.
3. Review source/dependency licenses, hash-locked Windows x86-64 dependency builds, and genuine Windows Job Object/host-supervisor confinement.
4. Authenticated Lu scope and revocation integration, cancellation/resource exhaustion tests, and permission UI remain open.
5. Full quantization-controlled five-tier ON/OFF Lu+Cognitum model benchmarks are deferred and unexecuted.
