# Cognitum C14 G25 — Nonproduction guarded sensitivity integration

**Status:** RESEARCH-ONLY INTEGRATION; INDEPENDENT END-TO-END ACCEPTANCE PASSED. **NO PRODUCTION RELEASE.**

This directory is the opt-in C14 G25 research capability. It wraps the **unchanged** G25I conservative binary W/T/Y partial-identification baseline and the **unchanged** G25 release guard. It adds a bounded JSON Lines process interface and an optional native Cognitum research-plugin adapter. **It is not registered by the default Cognitum CLI, is not a Lu tool, and does not confer a causal-identification or production-promotion grant.**

## Local process interface

Python 3.13, NumPy, SciPy, pytest; statsmodels is used by the independent validation, not by the host. Run:

```bash
COGNITUM_G25_RESEARCH_OPT_IN=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  python integration/c14_research_host.py --research-only < requests.jsonl > responses.jsonl
```

Each request is a JSON object on one line:

```json
{"schema_version":1,"request_id":"case-001","action":"c14.g25.sensitivity.report","counts":[[[67,35],[45,31]],[[75,30],[48,39]]],"gamma":0.25,"assumption_evidence":{"sampling_iid_supported":true,"consistency_supported":true,"measurement_validity_supported":true,"gamma_justification":"External analyst-specified bound, not identifiable from the data"}}
```

Alternatively supply **`observations`** as a list of `{ "w": 0|1, "t": 0|1, "y": 0|1 }` records instead of `counts`. Strict binary integers only; no float coercion or boolean-as-counts. A newline-delimited reply contains a numerical conditional report or a typed refusal, a content digest, and explicit `automatic_causal_certification=false` and `production_estimator_promotion=false`. Receipts are deterministic replay checksums, **not cryptographic authentication or authorization tokens**.

The host is **disabled unless both** `--research-only` and `COGNITUM_G25_RESEARCH_OPT_IN=1` are set. It accepts no network connections and writes no state to Cognitum or Lu. Oversized input terminates that stream. OS process termination is available to a supervising host; a separate application-level in-flight soft-cancellation protocol is **not implemented**.

## Optional native Cognitum research track

The `integration/cognitum_research_plugin.py` implements Cognitum's actual `Manifest`/`Operation`/`Shape` plugin protocol, using `track="research"`, `maturity="prototype"`, zero effects and `assurance="unverified"`. It is **not automatically installed**. An authorized trusted host must explicitly install it disabled, nominate its research slot, enable it, provide a matching workspace/subject, and use `HostContext(allow_research=True)`. The runtime's `completed` status means **worker computation completed**, even when the nested research result explicitly **refused** a causal report; callers must inspect that nested status.

To exercise the native plugin against the **six byte-identical pinned source files** for Cognitum's Registry, Runtime, Worker, Contracts, Policy and Trace fetched from repository branch `cognitum/c14-g25-engineering-gate-closure-20261101`:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python tools/native_runtime_acceptance.py
```

Each original module's Git blob SHA-1 matches the source branch. The copies are a **test-only runtime snapshot** and were not modified for the adapter. For an actual native Cognitum checkout, the plugin can be imported as `research.c14_g25_nonprod.integration.cognitum_research_plugin` with the repository root on `PYTHONPATH`. This branch does **not** change the default Cognitum registration path.

## Independent acceptance and regression

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python tools/independent_e2e_acceptance.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python -m pytest -q tests/test_nonprod_host.py tests/test_g25_release_guard.py
```

The independent E2E harness does **not import the candidate guard, integration host or G25I source**. It executes 980 JSONL requests across a separate subprocess: 560 G25N archived cases (20 from each of 28 distinct cohort/family/size cells), 420 new-seed synthetic cases, plus 16 malformed/replay negatives. It independently computes the plug-in identified endpoints using SciPy HiGHS linear programming and the conservative outer endpoints using `statsmodels` exact-beta Clopper–Pearson limits.

- `results/Independent_E2E_Acceptance.json`: exact outcome, refusal, provenance, numerical max delta and gate status.
- `results/Independent_E2E_Requests.jsonl` and `...Responses.jsonl`: original black-box requests and full responses.
- `results/Independent_E2E_Receipt_Audit.jsonl`: per-request independent comparison receipts.
- `results/Native_Runtime_Integration_Acceptance.json`: native research routing/denial, worker timeout and metadata-only trace results.
- `docs/Independent_E2E_Freeze.json`: held-out fixture and acceptance protocol; SHA-256 `8fee77828ee869d2dc20ab88bed8d65b1e3048099902113898707e08b730ad07`.
- `C14_G25_Nonproduction_Integration_Report.md`: gate-by-gate scientific and engineering conclusions.

Archived G25N fixture receipts are needed to rerun the full 980-case black-box acceptance; the complete local experimental corpus is also included in this ZIP. A fresh extraction into `/mnt/data/` with G25N available there reproduces the stated tests.

**Important boundary:** Nothing here proves that Gamma is correct, that hidden confounding is absent, or that causal intervals are calibrated across untested models. The failed G25J–N scientific precision/calibration gates, external Firth comparison, external scientific review, Windows containment, and production promotion remain OPEN or FAIL as appropriate.
