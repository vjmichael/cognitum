COGNITUM CH39 WINDOWS TEST KIT (read-only) - November 2, 2026

HOW TO RUN
  1. Extract the ENTIRE Cognitum_CH39_Windows_TestKit.zip to a normal folder
     such as Downloads\Cognitum_CH39_Windows_TestKit.
  2. Double-click RUN_CH39_WINDOWS_TEST.cmd.
  3. A CH39_Windows_Results_YYYYMMDD_HHMMSS folder appears beside the launcher.
  4. Share CH39_windows_summary.json and CH39_public_audit.json (and *.log if needed).

NO ADMIN, NO INSTALLER, NO CHANGES TO LU OR COGNITUM
The launcher temporarily bypasses PowerShell's execution policy ONLY for its
own process. It does not modify system policy. The test needs Python 3.9+
with the Python 'cryptography' module already available; it never installs
anything, reads or modifies existing Lu or Cognitum directories, or uses the
network. No private signing keys are included. Extracted test data is removed.

If you get a 'cryptography missing' message, you can install it yourself with:
    py -3 -m pip install --user cryptography
Then double-click the test launcher again.

WHAT PASSES
  - One exact, externally pinned CH39 reproduction ZIP SHA-256
  - All 1,099 original package members against the canonical SHA-256 manifest
  - All 15 original CH32/CH33 source/checkpoint pins
  - All 15 signed witness generations and 30 real Ed25519 signatures
  - Final recorded externally pinned witness tip

OPTIONAL: WINDOWS MPFR/GMP TEST
Run from cmd.exe in the extracted folder:
    RUN_CH39_WINDOWS_TEST.cmd -MathProbe
For an explicit x64 Windows MPFR DLL (with its matching GMP DLL available):
    RUN_CH39_WINDOWS_TEST.cmd -MathProbe -MpfrDll "C:\path\to\libmpfr-6.dll"
This runs a 7-node projected prefix from the original CH29 proof, with 224-bit
MPFR and direct outward rounding. It is *not* the full 127-node CH39 replay.
It is possible to pass signed evidence verification while the mathematical
probe is BLOCKED because your Windows MPFR/GMP DLLs are unavailable.

WHAT THIS DOES NOT TEST
  - The Linux UID 1000/1002/1003/1004/65534 isolation and SO_PEERCRED
  - Signed-witness issuance or authority write durability on Windows
  - Independent (distinct-code) mathematical verification (planned CH40)
  - A full CH39 archived 127-node MPFR replay on Windows
  - A scientific claim of global optimality; historical result remains NO_GO
  - Production C14/G25 or Lu integration

PACKAGE PIN (use to confirm the correct ZIP)
  SHA256: 9e713b102982ea09fecbcfbd27bccf55d56808188bfc3e5be1ba76922000ae6b
  Original archive: Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip

Offline testing only. Results are diagnostic; do not run as Administrator.
