# Cognitum C14 G22 — CVXPY offline solver dependency closure

**Research date:** October 31, 2026 (Arizona); test environment UTC November 1.  
**Scope:** Cognitum isolated Linux development test environment; **Lu not modified**.  
**Status:** CVXPY solver dependency closure **PASS**; production OS-isolation acceptance is separate.

## Uploaded wheel validation

- Accepted user-uploaded archive: `Cognitum_C14_CVXPY_Solvers_Linux_py313.zip`; SHA-256 `19e040796bfdb55599162dc3254c613793b55a346554462fb01f286b06b07352`.
- ZIP internal integrity passed. All six wheel sizes and SHA-256 digests match the archive’s bundled manifest. These are self-consistency checks, not independent publisher provenance attestation.
- PEP 384 stable-ABI wheel correction: prior G21 verifier rejected `clarabel-0.11.1-cp39-abi3` despite Python 3.13 compatibility. The revised checker uses `packaging.tags.sys_tags()`. **11/11 offline verifier tests passed**, including stable-ABI positive and incompatible-ABI negative tests.
- Wheel installation: `pip install --no-index --no-deps --only-binary=:all:` into existing Cognitum-scientific venv (no global Python or Windows modification).

| Distribution | Installed version | Hash check |
|---|---:|---|
| clarabel | 0.11.1 | Matches bundle manifest |
| highspy | 1.15.1 | Matches bundle manifest |
| osqp | 1.1.3 | Matches bundle manifest |
| qdldl | 0.1.9.post1 | Matches bundle manifest |
| scs | 3.3.1 | Matches bundle manifest |
| sparsediffpy | 0.6.1 | Matches bundle manifest |

## Actual CVXPY optimization tests

- CVXPY 1.9.3 imports successfully; all six solver dependency modules import.
- `installed_solvers()` reports CLARABEL, SCS, SCIPY, HIGHS, and OSQP.

| Solver | Mathematical smoke test | Solver status | Solution |
|---|---|---|---|
| OSQP | quadratic minimum | optimal | x=3 |
| CLARABEL | linear minimum | optimal | x=1 |
| SCS | linear minimum | optimal | x=0.999999995 |
| HIGHS | linear minimum | optimal | x=1 |

**All four** real solver tests passed. This is a representative runtime gate, not a production mathematical accuracy benchmark.

## Cognitum C14 scientific regression

- **653 passed, 2 expected skips, 0 failures**, obtained in nine isolated pytest batches after an earlier monolithic run stalled after test progress hit 100%. Each successful batch exited with status 0 and printed its own summary.
- Source-snapshot DoWhy G7 tests were isolated from the official DoWhy 0.14 interpreter context to avoid Python module-cache contamination.
- The **3 official release-pinned DoWhy runtime tests** passed in a focused rerun (they are already represented in the 653 test count).
- The **2 library-absence negative controls** passed separately in a clean interpreter. The two expected skips within the 653-test aggregate are these intentionally incompatible-with-installed-library controls.

| Batch | Passed | Skipped | Exit code |
|---|---:|---:|---:|
| A1 | 88 | 1 | 0 |
| A2 | 71 | 0 | 0 |
| A3 | 113 | 0 | 0 |
| A4 | 110 | 0 | 0 |
| A5 | 82 | 0 | 0 |
| B1 | 34 | 0 | 0 |
| B2 | 62 | 0 | 0 |
| B3 | 69 | 1 | 0 |
| G71 | 24 | 0 | 0 |

## Remaining qualifications

- `pip check` is clean for CVXPY and its solver dependencies, but reports an **unrelated** MoviePy 2.2.1 / Pillow 12.3.0 conflict (MoviePy requires Pillow <12).
- Wheel hashes were verified against the uploaded PyPI-generated manifest; they were **not independently compared to live PyPI hashes** in this offline checkpoint.
- No Linux cgroup/worker containment claim is made by these results. The stronger OS isolation acceptance gate remains open.
- No Lu repository, Lu source, Windows build, or convergence branch was changed.

## Reproduce offline

```bash
/mnt/data/c14_release_gate/venv/bin/python /mnt/data/c14_g22_wheel_acceptance/validate_wheels_g22.py /mnt/data/c14_g22_wheel_acceptance/wheels
/mnt/data/c14_release_gate/venv/bin/python -m pip install --no-index --no-deps --find-links /mnt/data/c14_g22_wheel_acceptance/wheels clarabel==0.11.1 highspy==1.15.1 osqp==1.1.3 qdldl==0.1.9.post1 scs==3.3.1 sparsediffpy==0.6.1
/mnt/data/c14_release_gate/venv/bin/python /mnt/data/c14_g21_offline_closure/run_real_cvxpy_gate.py
/mnt/data/c14_release_gate/venv/bin/python /mnt/data/c14_g22_wheel_acceptance/run_c14_segmented.py
```

All paths refer to the saved local test environment; the accompanying ZIP includes the source scripts, summary and logs, **not the original wheels**.
