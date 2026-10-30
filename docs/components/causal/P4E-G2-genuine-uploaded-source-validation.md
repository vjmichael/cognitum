# C14 P4E G2 — Genuine Tigramite source-runtime validation (Linux)

**Date:** 2026-10-28. **Status:** Genuine PCMCI and PCMCI+ execution verified on synthetic data with a locally installed source distribution; **NOT Windows / Lu security certified.**

## Origin and integrity

- User-supplied `tigramite-master.zip`: SHA-256 `427e01cc18b75b9bb575537fc3a03ebbd6ee8c8fc973616328725c851e63eff8`.
- The contained `setup.py` declares Tigramite **5.2.10.1**, Python package dependencies `numpy>=1.18`, `scipy>=1.10.0`, `six` and **GPLv3** license. The file name `master.zip` and setup version do **not** cryptographically authenticate an upstream GitHub tag or source commit.
- Original P4E source archive: SHA-256 `151f597cc5667eb9446697785bd563cb08d46840309fb7763ba84b7240068d0a`. It remains unchanged.
- The upload was extracted without modifying it. Source code was installed with `pip --no-index --no-deps --no-build-isolation` into a separate Linux Python virtual environment with preinstalled scientific dependencies; *no network or bundled external source* was required.
- We distribute **no Tigramite source or binary** inside this Cognitum checkpoint; packaging and GPL redistribution obligations require legal review before shipping.

## Findings

1. The installed real Tigramite 5.2.10.1 implementation successfully runs `PCMCI.run_pcmci` and `PCMCI.run_pcmciplus` with `ParCorr` using the P4E v1 Protobuf request, on a seeded 300-row two-variable series. Both produce `TD_CANDIDATE`, recover the known generated lagged X[t-1]→Y[t] relationship and yield request-bound structure receipts. Neither proves real-world causation or validates the causal assumptions.
2. Six independent-variable null-data executions (PCMCI/PCMCI+ × three seeds) produced no reported cross-variable candidate links for these specific fixtures. This small sample is **not** a calibrated false-discovery-rate study.
3. The original subprocess worker launched the resolved path of a virtualenv Python symlink, incorrectly switching to the system interpreter. `causal_tigramite_backend.py` now preserves the absolute configured interpreter path for **launch**, while validating and hashing the executable target. The remaining TOCTOU, trust, package provenance and host OS security requirements are **not** solved by this change.
4. Direct genuine calls and `python -I` subprocess calls passed. Subprocess tests use a **simulated** `host_authorized=True` and `host_isolation_attested=True`; this is a local integration test, **not** genuine Lu host admission or native Windows isolation. Default-denied and no-attestation paths were also tested.
5. P4E focused source-installed runtime: **44 passed, 1 dependency-negative test skipped, 0 failed** (45 tests). Existing C14 runs using default dependency-free interpreter: **343 passed, 15 optional skips, 0 failed** (358 tests). Existing C13: **139 passed, 2 optional skips, 0 failed** (141 tests). Independent compiler verified **41/41** Protobuf schemas; P4E default-disabled six-case smoke passed.
6. A broad C14 run executed *inside the new venv* encountered **three failures in older DoWhy and EconML/causal-learn missing-backend subprocess tests**, because their launchers also resolve venv symlinks to the non-venv interpreter. Those are **not** counted as passing in that environment; they need a distinct adapter fix and must not be used as proof those backends work.

## Reproduction

The source-upload must be installed in a host-controlled Python environment from its exact approved archive, with offline dependencies already present and source/pins separately validated. Run from the checkpoint source root:

`PYTHONPATH=.:tests <tigramite-venv-python> -m unittest tests.test_c14_p4e_tigramite tests.test_c14_p4e_uploaded_tigramite`

`PYTHONPATH=.:tests python -m unittest discover -s tests -p 'test_c14_*.py'`

`PYTHONPATH=.:tests python tools/verify_protobuf_schemas.py --require`

`PYTHONPATH=.:tests python tools/run_c14_p4e_smoke.py`

This source checkpoint **does not bundle an installable runtime**. Reproducibility requires preserving the supplied source archive hash plus the scientific dependency versions, platform and selected test seeds.

## Gates remaining open

- Authenticated Lu host authorization, native Windows Job Object/descendant reaping/revocation/OS confinement.
- Pinned offline wheelhouse and trusted upstream artifact attestations; redistribution/legal review for GPLv3.
- Larger statistically valid synthetic-ground-truth sensitivity/specificity/frequency evaluation with many seeds, different sample sizes, hidden confounding, nonstationary conditions.
- End-to-end Lu+transformer behavior and quantization-controlled augmentation benchmarks.
- Older DoWhy/EconML/causal-learn venv Python launcher path parity should be handled separately.
