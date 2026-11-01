# Cognitum C14 G20 — CVXPY 1.9.3 uploaded wheel validation

**Date:** October 31, 2026 (Arizona); test environment UTC November 1.  
**Scope:** Cognitum-only scientific environment; no Lu changes.  
**Result:** Uploaded CVXPY wheel integrity and version verified; DoWhy/C14 scientific regressions remain green. Full CVXPY solver installation **not yet complete**.

## Received artifact
- Wheel: `cvxpy-1.9.3-cp313-cp313-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl`
- SHA-256: `2df107618d847fadaff65c1406d32f1d4c8cb0493cce762f2d977bb47980b02f`
- ZIP integrity passed; installation in isolated Python 3.13 environment succeeded with `--no-index --no-deps`; distribution metadata identifies `cvxpy==1.9.3`.
- **Import fails:** `import cvxpy` raises `ModuleNotFoundError: No module named 'qdldl'`. No optimization solve can yet be certified.

## Unmet runtime requirements
Exact uploaded wheel metadata requires all six packages still absent in the isolated environment:
`clarabel>=0.5.0`; `highspy>=1.14.0`; `osqp>=1.0.0`; `qdldl>=0.1.7.post0`; `scs>=3.2.4.post1`; `sparsediffpy>=0.6.0,<0.7.0`. Existing NumPy/SciPy meet minimums. `pip check` is not clean; an unrelated MoviePy/Pillow mismatch also remains. No fake/stub solver was introduced.

## Completed Cognitum regression
| Suite | Outcome |
|---|---|
| DoWhy 0.14 pinned runtime positives | 3 passed |
| C14 release group A | 464 passed; 1 expected skip |
| C14 release group B (uploaded source path explicit) | 165 passed; 1 expected skip |
| Legacy G7 DoWhy-source tests (separate interpreter) | 24 passed |
| DoWhy-absent and Tigramite-absent controls (clean interpreter) | 2 passed |
| **Distinct C14 full regression subtotal** | **653 passed; 2 expected skips; 0 failures** |

Source-vs-release DoWhy runs were isolated to avoid Python module-cache contamination; the library-absent tests passed separately. Test harness, worker authorization, and isolation were not modified.

## Evidence
- Local engineering report: `C14_G20_Engineering_Report.md` in the uploaded conversation evidence bundle
- Evidence JSON SHA-256: `81722bd77c95203c5b23e810d1037a5cb5c78488291ea7730597ad9c996d769e`
- Test/evidence ZIP SHA-256: `0fcf5fc2ae3ecb55c708d4914308795eb1d679d5525c51ad69b1c3d68b2b7658`
- Bundle name: `Cognitum_C14_G20_CVXPY_Wheel_Validation_2026-10-31.zip`
- Wheel itself and private test environments are not committed to GitHub.

**Gate:** C14 regression pass accepted in the isolated test environment. CVXPY usable-import, solver-runtime and full dependency-lock gates remain **open**. Production OS confinement remains separate.
