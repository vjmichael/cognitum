COGNITUM CH39 WINDOWS OFFLINE EVIDENCE TEST - REVISED V2 (NOVEMBER 3, 2026)

WHY THIS REVISION EXISTS
A Windows test showed PASS for the pinned CH39 archive, immediately followed by
"FAIL: Traceback (most recent call last):" with the useful error suppressed.
The original PowerShell launcher's error-handling was inadequate for failed
Python import/dependency probes. The revised CMD invokes Python directly,
keeps full diagnostic logs, and reports missing/broken cryptography as BLOCKED.
This does NOT assert the earlier failure is solved without a Windows retest.

QUICK START
1. Extract ALL files from this ZIP to a normal writable folder.
2. Double-click RUN_CH39_WINDOWS_TEST.cmd.
3. If it reports BLOCKED or FAIL, find the new CH39_Windows_Results_YYYYMMDD_HHMMSS
   folder beside the CMD file. Upload its .json and .log files in ChatGPT.
4. Do not upload private keys, unrelated folders, or entire machine logs.

PREREQUISITES
Python 3.9+ (x64 recommended) and the cryptography Python package with Ed25519.
The test does NOT install packages, request Administrator, use network access,
write to Lu/Cognitum app directories, or generate or require private signing keys.
If cryptography is missing, the test reports BLOCKED and saves the exact error.
Optional manual installation if needed: py -3 -m pip install --user cryptography

WHAT IT CHECKS
- Externally pinned SHA-256 of exact CH39 original 6.1MB reproduction archive
- Canonical SHA-256 hashes of all 1,099 archived source/evidence files
- All 15 original source/checkpoint pins against CH32/CH33
- 15 attestor and 15 final signer Ed25519 signatures
- 15 linked witness generations and pinned final witness tip

OPTIONAL: seven-node original CH29 proof-prefix MPFR compatibility probe
Open CMD in this extracted folder and run:
  RUN_CH39_WINDOWS_TEST.cmd -MathProbe
If you have a compatible 64-bit Windows MPFR DLL with matching GMP DLL:
  RUN_CH39_WINDOWS_TEST.cmd -MathProbe -MpfrDll "C:\path\libmpfr-6.dll"
A math-probe BLOCKED result does not invalidate a PASS for the cryptographic audit.
The seven-node probe is not a full CH39 mathematical rerun.

NOT TESTED
- Linux UID/AF_UNIX isolation on Windows
- Mathematical independent implementation (CH40)
- Full 127-node mathematical proof in this Windows kit
- Production C14/G25 or Lu modifications
- Any global optimality certificate (the historical science result remains NO_GO)

Original CH39 historical archive SHA-256:
9e713b102982ea09fecbcfbd27bccf55d56808188bfc3e5be1ba76922000ae6b
