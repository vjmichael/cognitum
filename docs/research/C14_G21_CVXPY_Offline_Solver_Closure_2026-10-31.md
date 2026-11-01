# Cognitum C14 G21 — CVXPY Solver Dependency Closure: Offline-Ready, Execution Blocked

**Research date:** October 31, 2026 Arizona time; test container date November 1, 2026 UTC.

**Scope:** Cognitum scientific dependency validation only. No Lu code, Linux/Windows convergence code, or C14 scientific algorithms modified.

## Goal

Complete the solver dependency closure for official CVXPY 1.9.3 in the isolated CPython 3.13 Linux x86-64 C14 test environment and run real OSQP, Clarabel, SCS, and HiGHS optimization examples.

## Verified current state

- Existing official versions in `/mnt/data/c14_release_gate/venv`: DoWhy 0.14, EconML 0.17.0, sparse 0.15.4, and CVXPY 1.9.3.
- The installed CVXPY wheel metadata directly requires: `clarabel>=0.5.0`, `highspy>=1.14.0`, `osqp>=1.0.0`, `qdldl>=0.1.7.post0`, `scs>=3.2.4.post1`, `sparsediffpy>=0.6.0,<0.7.0`.
- All six are absent in that venv. **Real CVXPY import/optimization remains BLOCKED**. No performance, correctness, or precision claim for CVXPY optimizations was made.
- Container `curl` to official PyPI fails DNS resolution, `pip download` cannot resolve packages, and the alternate binary download path also failed. No third-party mirrors, fake solver modules, or bypass of package guards were used.
- C14/DoWhy smoke replay (with the correct pinned environment) completed: **22 passed, 1 expected skip**; the skipped test is an environment-dependent negative assertion rather than a solver correctness failure.

## New offline-ready test and acquisition kit

- `cvxpy_solver_requirements.txt`: requirements from installed wheel metadata (not guessed from latest website state).
- `validate_wheels.py`: verifies exactly six distribution names, version bounds, proper CPython 3.13 Linux x86-64 wheel tags, internal wheel ZIP integrity, METADATA/filename agreement, and locally recorded SHA-256. Exits nonzero if any are missing or malformed. **Wheel metadata checks do not prove publisher identity**, so official PyPI source must be used.
- `test_offline_gate.py`: nine synthetic validator contract tests; all **9 passed**. Synthetic fixtures are explicitly not executable wheels or a substitute for solver validation.
- `run_real_cvxpy_gate.py`: fails closed until all six distributions exist and the actual CVXPY solver registry advertises OSQP, Clarabel, SCS, and HiGHS; then solves four real QP/LP examples and checks optimal values numerically. Current result: **BLOCKED**, listing all six missing distributions.
- `Acquire-CVXPY-Linux-Wheels.ps1` / `Download-Wheels.cmd`: optional one-click acquisition helper intended for a Windows computer with Python and pip already present. Downloads **Linux CPython 3.13 x86-64 wheels**, not Windows wheels, from the official PyPI index; doesn't install anything on that machine. Packs them as a single ZIP. **The PowerShell launcher was not executed in this Linux environment**, so it is an unverified convenience helper, not an accepted test gate.

## Accepted vs open gates

| Gate | Result |
|---|---|
| Installed version and requirement inspection | Passed |
| Local ZIP/ABI/version validator test suite | 9/9 passed |
| Real DoWhy C14 smoke replay | 22 passed, 1 expected skip |
| Six binary wheels acquired | Blocked — no network access |
| CVXPY import and solver registration | Blocked — six missing runtime requirements |
| Actual OSQP/Clarabel/SCS/HiGHS solve examples | Not executed (fail-closed) |
| Full CVXPY dependency closure | Open |
| Lu changes | None |

**Next actual action:** supply a single ZIP of the six official PyPI Linux wheels (or an environment where they can be retrieved), run `validate_wheels.py`, install offline into the isolated C14 venv, run `run_real_cvxpy_gate.py`, and repeat the pinned C14 science gates. Do not represent planned solves as completed.
