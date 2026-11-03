COGNITUM CH39 MPFR RUNTIME CLOSURE FIX v2 - 2026-11-03

The former helper extracted MPFR and GMP only. Your Windows screenshot shows that the
libmpfr-6.dll file is present but Windows cannot load it or a dependency.
MSYS2 UCRT64 MPFR also depends on cc-libs; libgcc and libwinpthread are important
transitive runtime DLLs. This patch adds SHA256-verified official libgcc,
libwinpthread and libstdc++ UCRT64 binaries without installing MSYS2.

STEPS
1. Open the EXTRACTED Cognitum_CH23_CH39_All_History_Windows_Regression_2026-11-03 folder.
2. Extract both files in this ZIP directly beside RUN_ALL_COGNITUM_TESTS.cmd.
3. Double-click REPAIR_MPFR_AND_RUN.cmd.
4. It will verify official MPFR 4.2.2, GMP 6.3.0, libgcc 16.2.0,
   libwinpthread 14.0.0 and libstdc++ 16.2.0 runtime archives.
5. It extracts five runtime DLLs to MPFR_Runtime, attempts to actually load
   MPFR via Windows, then runs the usual 17 regressions plus the 7-node MPFR smoke.

NO ADMIN, NO GLOBAL INSTALL, NO PATH/REGISTRY/PYTHON CHANGES.
The script downloads upstream packages via HTTPS from the official MSYS2
mirrors, verifies exact SHA256 values published on packages.msys2.org before
extracting the specified DLL files, and never executes the package installer.
A Windows DLL load succeeds only with compatible native dependencies.

If Windows still reports BLOCKED, share ONLY:
  MPFR_Runtime\MPFR_RUNTIME_DIAGNOSTICS_V2.json
  newest COGNITUM_REGRESSION_SUMMARY.json
The diagnostic report contains imported DLL names but no private keys.

OFFLINE: Place these verified UCRT64 .pkg.tar.zst packages beside this script
and run again; they must match the hardcoded official hashes.

SECURITY LIMIT: This is a runtime load test plus 7-node 224-bit mathematical
smoke, not a 127-node dual-verifier run or global optimality certificate.
Original 17 historical Windows checks passed and remain unchanged.

SOURCE REFERENCES
https://packages.msys2.org/packages/mingw-w64-ucrt-x86_64-mpfr
https://packages.msys2.org/packages/mingw-w64-ucrt-x86_64-gmp
https://packages.msys2.org/packages/mingw-w64-ucrt-x86_64-libgcc
https://packages.msys2.org/packages/mingw-w64-ucrt-x86_64-libwinpthread
https://packages.msys2.org/packages/mingw-w64-ucrt-x86_64-libstdc%2B%2B
