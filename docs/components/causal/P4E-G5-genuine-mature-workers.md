# Cognitum C14 P4E G5 — Genuine EconML and causal-learn worker validation

**Date:** 2026-10-28. **Status:** Linux development scientific-runtime checkpoint passed; Windows/Lu admission remains OPEN.

## Scope and provenance

This checkpoint inherits the unmodified G4 Cognitum source snapshot and genuinely executes the existing C14 P3C native-Protobuf, host-gated subprocess workers against the user's supplied Python sources:

- `EconML-main.zip` — source declares EconML **0.17.0** in `econml/_version.py`.
- `causal-learn-main.zip` — source declares **0.1.4.8** in `setup.py`.
- `sparse-main.zip` — source uses *dynamic SCM versioning*, lacks generated `_version.py`; locally registered as **`0+uploaded`**, which is **not** an upstream version certification.
- `momentchi2-0.1.8.tar.gz` — installed locally as **0.1.8**.

SHA-256 identifiers are in the accompanying JSON evidence. All uploaded source archives were left unchanged. Vendor sources, virtual environments and compiled native extensions are **not redistributed** in the Cognitum checkpoint. DoWhy 0.14 remains an outstanding genuine-runtime gate; an uploaded `main` snapshot does not attest to that tag.

For reproducibility in this **Linux Python 3.13.5 development environment**, unpack the source snapshots to a separate scratch folder, use a virtual environment with the existing installed SciPy/NumPy/scikit-learn/statsmodels stack, install momentchi2 and causal-learn offline, and prepare sparse with a local generated `_version.py` and `0+uploaded` metadata. The uploaded EconML source required a **scratch-only** build fix: replace the single wildcard `Extension('*', pyx_files)` with one `Extension` per `.pyx` file, compile the resulting seven Cython extensions, then expose its Python modules from that isolated source tree with its 0.17.0 metadata. Do not treat this as an authenticated release-wheel or Windows build. An environment-specific preparation script is included under `tools/prepare_g5_local_sources.py`; it assumes user packages reside under `/mnt/data`, and uses only a fresh scratch copy.

## Positive, genuine worker evidence

- EconML: a **real `LinearDML` subprocess** through the existing Protobuf request/response boundary accepted 100 expanded binary data observations, returned two conditional-effect estimates (for modifier states 0 and 1: `1` and `0` in this fixture), reported version `0.17.0`, and passed request-bound receipt replay. This is a limited, synthetic fixture, not a general statistical-accuracy certification.
- causal-learn: a **real PC-stable subprocess** through the same native Protobuf contract accepted 250 synthetic observations, returned an undirected candidate skeleton with edges `(0,1)` and `(1,2)`, reported version `0.1.4.8`, and passed request-bound receipt replay. No causal edge direction is asserted.
- G5 additional tests cover repeatability with fixed seed, forged estimate/graph/causal-certification fields, improper authorization, missing host isolation *flag*, worker-source hash mismatch, and library pin mismatch.
- The host-authorization and OS-isolation booleans in the tests are **development fixtures**, not authentic Lu attestations. The worker remains default OFF; the current Python interface must not be exposed directly to LLMs in production.

## Recorded test results

| Check | Outcome |
|---|---|
| Full selected C14 test set with real EconML/causal-learn source runtime | 395 methods run; **380 passed, 15 skipped, 0 failed** |
| Full selected C13 test set | 141 methods run; **139 passed, 2 skipped, 0 failed** |
| G5 dedicated genuine-runtime tests | **7 passed** (included within the C14 total above) |
| Original P3C two pinned-runtime tests | **2 passed** (included within C14 total) |
| Existing P3C boundary tests without installed mature libraries | **14 passed** in the normal environment |
| Native G5 smoke | **2/2 genuine worker calls passed** |
| Original C14, estimation and P4E smoke suites | **6/6 each** in their respective bounded test modes |
| Independent Protobuf descriptor compilation | **41/41** schemas matched compiler-produced bindings |
| Python source compilation | Passed |

All positive mature-library runs are actual source-library executions, not algorithm mocks or emulated results. The C14 source harness was modified so an available real library is not mistakenly treated as an expected missing dependency. Two C13 virtual-environment worker launchers were adjusted to preserve the configured interpreter path while checking its resolved target and digest, fixing a genuine C13 regression inside the G5 environment.

## Open release and assurance gates

1. DoWhy **0.14**, authenticated tag/runtime and full identification/estimation/refutation validation.
2. Exact upstream Git commit and version provenance of dynamic `sparse-main`, plus approved, transitive dependency lock and signed/hashed Windows wheelhouse.
3. Native Windows x86-64 Job Object process tree isolation, hardened filesystem scope, time/memory budgets, cancellation and cleanup.
4. Real Lu host authentication, scoped conversation authority and permission/revocation enforcement.
5. Cross-backend large-seed statistical validation, hidden-confounding and graph-identifiability caveats, robust CPU/RAM benchmarking.
6. The future weight/KV-quantization-controlled paired LLM-with/without-Cognitum experiment; **not run** here.

The mathematical results must be described as *candidate statistical estimates/graphs under assumptions*, never as causal truths. None of these unit tests certifies production security, source authenticity, or broad generalization.
