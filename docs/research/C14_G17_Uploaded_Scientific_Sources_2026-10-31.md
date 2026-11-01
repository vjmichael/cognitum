# Cognitum C14 — Uploaded scientific sources: 37-skip reactivation report

**Date:** October 31, 2026 (Arizona time); tests also ran on November 1 UTC.  
**Scope:** Cognitum only. No changes to Lu or Cognitum source were needed to activate these tests.

## Results

| Verification | Before | After |
|---|---:|---:|
| C14 passed | 618 | 651 |
| C14 skipped | 37 | 4 |
| Previously skipped positive tests newly passing | — | **34 of 37** |
| Tigramite absent negative in separate clean interpreter | 1 passing initially | 1 passing again |

The rerun was performed as **two nonoverlapping file groups**, not a successful single-process full-suite run. Group A was **462 passed, 3 skipped, 31 subtests passed**; group B was **189 passed, 1 skipped, 6 subtests passed**. The combined groups cover the entire 655-case test collection. A monolithic run timed out without a summary; do not count it as a pass.

### Real source execution obtained

- Tigramite **5.2.10.1**, causal-learn **0.1.4.8**, EconML **0.17.0**, and momentchi2 **0.1.8** built from the user's original uploaded archives, using offline pip in an isolated installation prefix. They executed genuine subprocess/worker acceptance tests.
- Uploaded **untagged DoWhy main** source was explicitly supplied to C14 G6/G7 with the environment variable `COGNITUM_DOWHY_SOURCE`; its research-only cross-library suite passed **34/34**. It is **not** DoWhy v0.14 production admission evidence.
- A Tigramite-free interpreter ran its separate **1/1** unavailable-library fail-closed negative test.

### Still open (no false green)

1. The three original DoWhy 0.14 pinned-runtime positive tests remain skipped. The uploaded DoWhy source uses placeholder `__version__ = '0.0.0'` and does not authenticate a 0.14 release. We did not falsify its package version.
2. `sparse-main.zip` has no source-control tag or generated `_version.py`. Offline wheel installation recorded **sparse 0.0.0**, and a local, explicit developer-only `_version.py` compatibility stub was added to the **test environment only**, with that same 0.0.0 version. `pip check` still reports **EconML requires sparse>=0.15.4**. Scientific tests can run; the dependency-version/production lock gate remains **open**.
3. This venv shares the preinstalled scientific stack from `/opt/pyvenv`; it is **not hermetic** and does not attest host or kernel isolation. Tests use development-only host-authorization fixtures.
4. The Tigramite-free negative test is **skipped by design** in the installed-library environment but passed separately in the baseline interpreter.

### Reproduction conditions

Python 3.13.5, NumPy 2.3.5, SciPy 1.17.0, pandas 2.2.3, scikit-learn 1.8.0, statsmodels 0.14.6, and Protobuf 6.33.6 were already available. Build/install commands used `pip install --no-index --no-deps --no-build-isolation` from **local extracted archives**; no downloaded replacements or Lu code changes. For isolated `-I` worker subprocesses, the venv `.pth` file provides the preinstalled scientific module directory. Commands and exact archive SHA-256 hashes are preserved in the evidence bundle.

Run the two groups (exact pytest arguments and environment are in `run_c14_g17_verified_groups.sh`), then the Tigramite-free negative in the base interpreter. Do not present tests passed under a development-only DoWhy snapshot as a pinned production DoWhy 0.14 acceptance.

**Conclusion:** The 37 skipped tests have been reduced to **3 original production-release blockers**; 34 previously skipped tests now pass. One additional environment-dependent negative is covered separately. This does not close the production dependency lock.
