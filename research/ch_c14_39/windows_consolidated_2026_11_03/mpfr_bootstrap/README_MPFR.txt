COGNITUM CH39 — OPTIONAL NATIVE MPFR/GMP WINDOWS RUNTIME
3 November 2026 — Python 3.14 / MSYS2 UCRT64, 64-bit

WHY
The 17 original CH23–CH39 historical Windows checks PASS.
The optional seven-node 224-bit MPFR smoke reports BLOCKED because
no native MPFR DLL was present. No core Cognitum test failed.

INSTALL NOTHING; DO NOT CHANGE PATH
1) Extract these two helper files into your EXISTING
   Cognitum_CH23_CH39_All_History_Windows_Regression_2026-11-03 folder,
   alongside RUN_ALL_COGNITUM_TESTS.cmd and COGNITUM_HISTORY_REGRESSION.py.
2) Double-click GET_MPFR_AND_RUN_TEST.cmd.
3) It uses your working Python 3.14, downloads two small upstream .pkg.tar.zst
   files from official MSYS2 mirrors over HTTPS, verifies the exact published
   SHA-256 of EACH package, and extracts only the two 64-bit DLLs to:
     MPFR_Runtime\libmpfr-6.dll
     MPFR_Runtime\libgmp-10.dll
4) It runs the existing kit using:
     RUN_ALL_COGNITUM_TESTS.cmd -MathProbe -MpfrDll "<folder>\MPFR_Runtime\libmpfr-6.dll"
5) Send only the resulting COGNITUM_REGRESSION_SUMMARY.json if BLOCKED/FAIL.

OFFLINE OPTION
Use these official package-page URLs to download both exact versions
and save both .pkg.tar.zst files beside SETUP_MPFR_RUNTIME.py.
The script will verify the pinned SHA-256 and use them without internet:
https://packages.msys2.org/packages/mingw-w64-ucrt-x86_64-mpfr
https://packages.msys2.org/packages/mingw-w64-ucrt-x86_64-gmp

SOURCE HASHES (exact official package versions)
MPFR 4.2.2-3: 6b70a275d2ec75c70aa50a236c218e6b7ee9a5ab4c6d52cb0b580267b7d200fe
GMP  6.3.0-2: e82a75968a556484a50084578238a84eb60fb93e34986fd6695c537975bd39ea

PROVENANCE / PRIVACY
Only official MSYS2 source package bytes are downloaded; no arbitrary code
is executed from those archives, and only specifically named DLLs are extracted.
No MSYS2 installation, global DLL install, Python package install, PATH change,
registry edit, administrator rights, or alteration to Cognitum/Lu is needed.
Source DLLs are external runtime code, not included in this tiny helper ZIP.

LIMITS
- Test MAY remain blocked for missing transitive native dependencies.
- Windows execution of this setup has NOT been independently verified here.
- This is a 7-node original CH31 prefix mathematical smoke, NOT the full
  dual 127-node CH39 check and NOT a global-optimality certificate.
- The earlier 17 public-evidence checks remain valid regardless.
