COGNITUM C14 WINDOWS FULL MATHEMATICAL BENCH - MPFR DISCOVERY FIX v1.2
2026-11-03

WHAT WAS WRONG
Your first completed full-bench attempt ran CH23 and passed its 10 tests, but
CH24 and the 105 original-case mathematical replay tasks could not start:
the MPFR search returned None. 112 tasks were marked BLOCKED, none FAILED.
Eight CH32-39 Linux-only OS integrations remain UNSUPPORTED_PLATFORM by design.
The previously successful Windows MPFR Runtime exists in the *other* CH39 kit.

WHAT CHANGED
* Searches kit-local MPFR_Runtime first, then sibling CH39 consolidated
  test-kit folders (including '(1)' duplicate suffix and one extra ZIP wrapper).
* Searches USERPROFILE\Downloads if the benchmark was moved elsewhere.
* Accepts explicit --mpfr-dll path to the DLL OR its containing directory.
* Accepts environment variable C14_BENCH_MPFR_DLL (path to the DLL).
* Prints the resolved DLL path before starting actual mathematical tasks.
* Keeps the v1.1 sealed-source scratch-cache recovery fix.
* Keeps the pinned original CH39 source archive unchanged.
* Existing PASS statuses remain in results. BLOCKED entries are retried.

RECOMMENDED QUICK FIX WITHOUT ANY PATCH
Copy the entire MPFR_Runtime folder (all five DLLs) from the successful
CH39 Windows consolidated regression kit into the same folder as
RUN_C14_FULL_MATH_BENCH.cmd, then rerun that CMD. The v1.1 runner already
supports this fallback. Do NOT copy a single DLL alone.

IF USING THIS PATCH
Extract the patch ZIP directly beside RUN_C14_FULL_MATH_BENCH.cmd,
replacing C14_MATH_BENCH.py. Then double-click the same CMD.
The new launch should say: 'MPFR: discovered local runtime DLL: ...'

EXPLICIT PATH OVERRIDE IF NEEDED
In PowerShell, from the benchmark folder:
  .\RUN_C14_FULL_MATH_BENCH.cmd --mpfr-dll "C:\path\to\MPFR_Runtime\libmpfr-6.dll"
Or point at the MPFR_Runtime DIRECTORY itself (v1.2).

TEST A SHORT PHASE FIRST
  .\RUN_C14_FULL_MATH_BENCH.cmd --phase 25 --case one_event_n80_i00
Then launch .\RUN_C14_FULL_MATH_BENCH.cmd (default full matrix).

REPORTS
  C14_MATH_RESULTS\C14_FULL_MATH_BENCH_SUMMARY.json
  C14_MATH_RESULTS\logs\<task>.log
No production C14, Lu, PATH, registry, private keys, or original CH39 evidence
are modified. Validation was done on Linux and in synthetic path tests, NOT
native Windows; the next Windows run is the acceptance check.
