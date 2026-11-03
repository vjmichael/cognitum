COGNITUM C14 FULL MATHEMATICAL BENCHMARK -- WINDOWS SCRATCH RECOVERY FIX v1.1
November 3, 2026

Windows failure fixed:
 FATAL ValueError Historical working-copy file differs from sealed archive:
 CH_C14_23/audit.json

Cause: original CH23-CH39 mathematical test suites can rewrite archived report
files in the dedicated temporary working copy, while the previous runner
incorrectly treated this disposable working directory as permanently immutable.
The original SHA-256-pinned historical archive was not changed or damaged.

DROP-IN FIX (recommended for an already-extracted kit)
 1. Close any running C14 mathematical benchmark.
 2. Copy the updated C14_MATH_BENCH.py into the folder alongside
    RUN_C14_FULL_MATH_BENCH.cmd, replacing the OLD runner of that name.
    Also copy test_cache_recovery.py if you want the local regression test.
 3. Do NOT delete C14_MATH_RESULTS or MPFR_Runtime.
 4. Double-click RUN_C14_FULL_MATH_BENCH.cmd again.

The updated runner checks every archived file against the independently
SHA-256-pinned ZIP. Modified or missing cached files are restored, one at a
time, using verified data and atomic file replacement. It re-verifies the
scratch source before every actual mathematical test, so one phase's generated
reports cannot silently alter the next phase's frozen inputs. It refuses
unexpected/mismatched provenance markers or symlinked scratch source paths.
The original CH39 evidence ZIP is never edited.

Quick check (optional, PowerShell inside the extracted kit folder):
  python -m unittest test_cache_recovery.py -v
  .\RUN_C14_FULL_MATH_BENCH.cmd --profile quick

Full benchmark:
  .\RUN_C14_FULL_MATH_BENCH.cmd

Benchmark outputs:
  C14_MATH_RESULTS\C14_FULL_MATH_BENCH_SUMMARY.json
  C14_MATH_RESULTS\logs\

Testing performed on development Linux host:
 - Four targeted cached-file recovery tests: PASS
 - 10 CH23 mathematical/gradient tests via pytest: PASS
 - CH25 original one_event_n80_i00 MPFR proof replay: PASS
Native Windows execution of this repaired version is still awaiting the
user test. Global mathematical optimality remains NO_GO.
