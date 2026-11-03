COGNITUM CH39 WINDOWS OFFLINE EVIDENCE TEST - LAUNCHER FIX V3 (NOVEMBER 3, 2026)

KNOWN WINDOWS RESULT
The ORIGINAL CH39 Windows public verifier passed on the user's Windows 11 PC:
- original ZIP SHA-256 PASS
- all 1,099 archive SHA-256 entries PASS
- 15 original case pins and 30 Ed25519 signatures PASS
- exit code 0

The revised v2 kit FAILED BEFORE VERIFICATION because its launcher preferred
py.exe -3, whose registry pointed to a removed LM Studio Python.  The actual
working Python was C:\Python314\python.exe.  This is a launcher selection bug,
not a failure of the CH39 proof-checking or public signatures.

V3 CHANGE
The launcher prefers a working `python.exe` on PATH and tests it before use.
If missing it tries C:\Python314\python.exe. Only when neither works does it
try the registered `py.exe -3`, and only after validating it can start Python.
The CH39 evidence ZIP and the Python audit code are unchanged from v2.

QUICK START (OPTIONAL; THE ORIGINAL KIT ALREADY PASSED)
1. Extract the entire v3 ZIP to a writable folder.
2. Double-click RUN_CH39_WINDOWS_TEST.cmd.
3. If any step fails, share the CH39_Windows_Results_* JSON/log files.

NO ADMINISTRATION OR REGISTRY FIX NEEDED. Python 3.9+ and `cryptography` required.
To install the latter with your working interpreter, use:
  C:\Python314\python.exe -m pip install --user cryptography

Optional MPFR smoke (only if Windows MPFR/GMP available):
  RUN_CH39_WINDOWS_TEST.cmd -MathProbe

Test scope: frozen archive SHA-256 manifest, case identities, Ed25519 witness
signatures. Does NOT test Linux account isolation, full 127-node MPFR replay,
or establish global mathematical optimality. Scientific state remains NO_GO.
