# Cognitum C14 G19 — Release wheels received and three pinned tests activated

**Date:** October 31, 2026 (Arizona); container clock November 1 UTC.  
**Scope:** Cognitum only; no Lu source, platform or build changes.  
**Disposition:** **release-pinned DoWhy C14 tests passed**. Full dependency closure and OS isolation **remain unaccepted**.

## Uploaded release wheels

| Distribution | Metadata version | Bytes | SHA-256 |
|---|---:|---:|---|
| `sparse-0.15.4-py2.py3-none-any.whl` | `0.15.4` | 237,311 | `76ec76fee2aee82a84eb97155dd530a9644e3b1fdea2406bc4b454698b36d938` |
| `dowhy-0.14-py3-none-any.whl` | `0.14` | 403,110 | `9c5855d80601e0feb2d0d232c19e7b660db4cd0ea04ace2ebaefcdb3599ab9db` |

The uploaded ZIP wheels passed integrity checks and were installed **offline**, with `--no-deps`, into a copy of the existing Cognitum scientific virtual environment. The previous source-snapshot environment was preserved. Local SHA-256 receipts are supplied, but a comparison to published PyPI artifact digests was **not performed**.

## Exact original version-pinned tests

`test_c14_dowhy_adapter.py::C14P2BTests::test_actual_dowhy_runtime_when_installed` plus both tests in `test_c14_dowhy_runtime_gate.py`:

**3 passed**. The tests executed the real installed DoWhy 0.14 backend for effect estimation and placebo refutation, including independent receipt checks. The tests supply a developer assertion `host_isolation_attested=True` and therefore **do not certify operating-system sandboxing**.

## Full C14 local regression replay

| Segmented suite | Passed | Skipped | Notes |
|---|---:|---:|---|
| First 25 test modules (official release env) | 464 | 1 | Version-pinned DoWhy positive tests passed; the no-DoWhy negative control now skips intentionally |
| Remaining modules excluding legacy G7 (official release env) | 165 | 1 | Tigramite-absent negative control skips intentionally |
| Legacy G7 untagged DoWhy source tests (separate interpreter) | 24 | 0 | Keeps source `0.0.0` research import independent of installed release `0.14` |
| **Total (unique test cases)** | **653** | **2** | **0 failures in completed segmented runs** |

Both absence-dependent negative tests were rerun in a clean interpreter without DoWhy or Tigramite: **2/2 passed**. The large first group also produced a duplicate completed pytest summary of `464 passed, 1 skipped`; the wrapper had timed out after the test summary, so this report does not count that duplicate as an additional successful group.

**Harness detail:** Combining G7's explicitly untagged source (`0.0.0`) with the official installed DoWhy (`0.14`) in one pytest process caused 7 fixture errors from Python's `sys.modules` cache. The exact same source G7 tests passed 24/24 when launched in their own Python interpreter. Neither scientific library nor Cognitum's underlying causal algorithm was patched to hide this distinction.

## Remaining issues

1. **CVXPY missing:** DoWhy 0.14 declares `cvxpy>=1.7.1,<2.0.0`. `pip check` reports it unavailable. The tested estimation functions work, but the full dependency lock is not closed. Install CVXPY in an appropriately compatible scientific test environment before claiming all DoWhy dependency requirements are satisfied.
2. **Unrelated global conflict:** system `moviepy==2.2.1` requires Pillow below 12; host Pillow is 12.3.0. This is not a C14 test failure.
3. **Host isolation:** Test policy flags are not independent OS confinement evidence. Windows Job Objects and Linux kernel-required containment need their own separate acceptance.
4. **Release provenance:** Supplied wheels have correct internal versions and reproducible hashes; matching these to the published distribution metadata has not been externally verified in this offline checkpoint.

## Reproduction outline

```bash
# Run in Cognitum developer environment; both wheels are local uploads.
python -m venv --system-site-packages venv
venv/bin/python -m pip install --no-index --no-deps sparse-0.15.4-py2.py3-none-any.whl dowhy-0.14-py3-none-any.whl
# PYTHONPATH points at the Cognitum checkout and existing base scientific packages.
venv/bin/python -m pytest -q -rs tests/test_c14_dowhy_adapter.py::C14P2BTests::test_actual_dowhy_runtime_when_installed tests/test_c14_dowhy_runtime_gate.py
# Run source-only G7 separately from other C14 tests to avoid DoWhy 0.0.0/0.14 import cache conflict.
```

The original user-uploaded wheels were **not modified**, nor were Lu files, branches, or runtime registrations changed.
