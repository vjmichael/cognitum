COGNITUM C14 -- REAL MATHEMATICAL REGRESSION (CH23 through CH39)
Windows 10/11, 64-bit Python 3.14, frozen original CH23 inputs.
Version 1.2 -- scratch-cache restoration and MPFR sibling DLL discovery; research-only, no production or Lu changes.

PURPOSE
The earlier 17/18 Windows checks primarily verified ARCHIVED EVIDENCE.
THIS kit executes ACTUAL C14 MATHEMATICAL FUNCTIONS and MPFR proof verifiers.
It uses the unchanged, SHA-256-pinned original CH39 archive and never edits it.

WHAT IT RUNS (FULL, DEFAULT)
* CH23: original numerical optimizer objective/gradient/finite-difference,
  independent data generation, ordinary interval upper-bound regression.
* CH24: 11 original MPFR directed-rounding, gradient/Hessian, solver, proof tests.
* CH25: fresh 224-bit MPFR bound and partition replay of all 15 original
  31-node certificates (NOT another optimization run).
* CH26: fresh original 127-node determinant/analytic-Hessian certificate replays.
* CH27: original 15-node coupled Fisher-likelihood / interval-Newton replays.
* CH28: original 127-node selective/cached-bound independent MPFR replays.
* CH29: original 127-node parent-cap proof inheritance replays.
* CH30: original 127-node COLD MPFR verification for 15 frozen datasets.
* CH31: original five-stage 7/15/31/63/127 incremental verification chains
  for the 15 original datasets.
* Available historic CH26/27/28/29/30/31 test suites are run in addition
  to the original-data proof replays. Tests include deliberately forged data.
* CH32/33 filesystem tests and CH34-39 Linux-only security/UID tests are
  explicitly listed UNSUPPORTED_PLATFORM on native Windows. Their underlying
  mathematical proof core is exercised through CH25-31 replays.

WHAT THIS KIT DOES NOT CLAIM
It does NOT guarantee every single declared function is executed. A separate
MATH_FUNCTION_INVENTORY.json inventories 152 Python modules and 741 declared
functions from the source archive. Not every function has a direct test.
Full pre-CH23 C14 sources and fixtures (including CH21/CH22 except the pinned
CH22 source) are NOT in the CH39 reproduction ZIP. They cannot be tested by
this kit without those separate historical archives.
Windows AF_UNIX, five-UID signer, kernel ENOSPC, physical power-loss, and
Linux-only storage guarantees are NOT represented as passing Windows tests.
No test asserts unrestricted global optimality or calibrated causal inference;
the frozen original 15-case scientific acceptance remains NO-GO.

RUNNING
1. Extract THIS ZIP into its own folder, not on top of the old regression kit.
2. Your previously working Python was C:\Python314\python.exe.
3. Native MPFR dependencies are already installed LOCALLY in your old
   Cognitum_CH23_CH39_All_History_Windows_Regression_2026-11-03\MPFR_Runtime
   folder. The new script searches this sibling, duplicate-suffix folders, nested ZIP wrappers, and USERPROFILE\Downloads. It prints the selected DLL path.
   If it cannot find it, copy MPFR_Runtime (all five DLLs) into this new
   kit's folder. Nothing needs to be installed system-wide.
4. For Python-only modules run SETUP_DEPENDENCIES.cmd once, if needed.
   It installs --user numpy scipy mpmath pytest cryptography if they are absent.
5. Double-click RUN_C14_FULL_MATH_BENCH.cmd.
6. This version repairs modified or missing files in its dedicated TEMP scratch cache from the original sealed ZIP before mathematical tests. It does not modify the sealed ZIP or the C14_MATH_RESULTS folder.
7. This is a deliberately heavy benchmark. It runs each case sequentially,
   saves the report after EACH check and RESUMES prior validated passes on
   restart. You can close and rerun the CMD window without losing completed
   results. Each timed-out test is BLOCKED, never silently counted PASS.

COMMANDS (PowerShell, in the extracted folder)
.\RUN_C14_FULL_MATH_BENCH.cmd
.\RUN_C14_FULL_MATH_BENCH.cmd --profile quick
.\RUN_C14_FULL_MATH_BENCH.cmd --phase 29
.\RUN_C14_FULL_MATH_BENCH.cmd --case one_event_n80_i00
.\RUN_C14_FULL_MATH_BENCH.cmd --timeout 3600
.\RUN_C14_FULL_MATH_BENCH.cmd --fresh
.\RUN_C14_FULL_MATH_BENCH.cmd --inventory-only

To specify an MPFR DLL without moving files:
.\RUN_C14_FULL_MATH_BENCH.cmd --mpfr-dll "C:\path\to\MPFR_Runtime\libmpfr-6.dll"

RESULTS
C14_MATH_RESULTS\C14_FULL_MATH_BENCH_SUMMARY.json
C14_MATH_RESULTS\MATH_FUNCTION_INVENTORY.json
C14_MATH_RESULTS\logs\suite_CH24.log and CH29__<case>.log, etc.

Share the summary JSON and any FAIL/BLOCKED logs, not machine secrets.
The original sealed ZIP remains unchanged. On Windows, the historical source
working copy is extracted under %%TEMP%%\C14M_9e713b102982 to avoid Windows
MAX_PATH errors; JSON and logs stay under C14_MATH_RESULTS. No private keys are created.

RECOVERY REGRESSION
If an earlier attempt stopped with "Historical working-copy file differs from sealed archive: CH_C14_23/audit.json", replace the old C14_MATH_BENCH.py with this version. Do NOT delete C14_MATH_RESULTS; the repaired runner restores only modified archived scratch files. A wrong source archive SHA-256 or an untrusted scratch provenance marker still fails closed. To self-test cache repair: python -m unittest test_cache_recovery.py -v

VALIDATION STATUS
Tested locally in the development host with actual original CH23, CH24,
CH25 mathematical checks; larger CH26-31 regressions are explicitly reported
separately. The complete new kit has NOT yet passed Windows execution.
Please report actual Windows problems rather than assuming a Linux pass
means a native Windows pass.
