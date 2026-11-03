COGNITUM CH23-CH39 — CONSOLIDATED WINDOWS REGRESSION v1.0
November 3, 2026

Purpose
-------
A single Windows launcher plus ONE consolidated Python test script to examine
original Cognitum C14 CH23 through CH39 archival evidence, without reinstalling
software, modifying production Cognitum or Lu, or using network services.

HOW TO RUN
----------
1. Extract this complete outer ZIP into a new folder.
2. Double-click RUN_ALL_COGNITUM_TESTS.cmd.
3. See status PASS, FAIL, or BLOCKED in the window.
4. If there is a problem, upload the generated
   COGNITUM_Regression_Results_*/COGNITUM_REGRESSION_SUMMARY.json,
   and ERROR.log if present. Do not upload private machine keys.

The CMD launcher verifies python.exe works before using it. It also supports
C:\Python314\python.exe and only invokes py -3 if it actually starts. On the
previous test machine, C:\Python314\python.exe with cryptography 50.0.2 works.

Test scope (17 checks by default)
---------------------------------
* Exact SHA-256 of original frozen CH39 reproduction ZIP against an independently
  hardcoded pin; all 1,099 packaged file hashes; ZIP safety/CRC checks.
* Inventory of archived CH23–CH39 milestone files and 15 original CH25 case
  fixtures/certificates tied to CH32/CH33 frozen case identifiers.
* Independently rehash all archived files referenced by historical cumulative
  manifests from CH32, CH33 and CH35–CH39. This detects changed prior history.
* Verify all 15 linked CH39 witness revisions: 15 Ed25519 attestor signatures,
  15 Ed25519 final signer signatures, source case/policy pins and final trust tip.
* Twelve controlled negative checks that modify ONLY temporary extracted copies
  or a separate disposable ZIP: changed head, rollback, forged public key,
  modified case pin, changed CH33 checkpoint, changed CH32 original head,
  changed revision, missing revision, orphan revision, modified ZIP,
  duplicate JSON keys, and unsafe Windows ZIP paths.

All checks run offline. Python >=3.9 and the 'cryptography' Python package are
required. You have already installed cryptography; no setup should be needed.

OPTIONAL: full history + 7-node MPFR ABI smoke
---------------------------------------------
Open CMD in the extracted kit directory and run:

  RUN_ALL_COGNITUM_TESTS.cmd -MathProbe

Or, with a known compatible DLL and its GMP dependencies:

  RUN_ALL_COGNITUM_TESTS.cmd -MathProbe -MpfrDll "C:\path\to\libmpfr.dll"

This OPTIONAL probe performs a FRESH 224-bit MPFR check of seven nodes from the
original CH29 certificate. It is NOT a 127-node CH39 mathematical replay. The
standard runner does NOT require MPFR. If dependencies are unavailable, the
optional probe reports BLOCKED, without invalidating the completed archive and
signature checks.

OPTIONAL: re-compare the two previous Windows CH39 audits
----------------------------------------------------------
Place copies of CH39_public_audit.json and CH39_public_audit(1).json together in
one folder and run:

  RUN_ALL_COGNITUM_TESTS.cmd --PriorLogsDirectory "C:\path\to\logs"

Their bytes and SHA-256 must match and both must report PASS. This is optional:
the two user runs were already examined and found byte-for-byte identical.

LIMITATIONS
-----------
The script cannot reproduce Linux five-UID containment, actual Linux
ENOSPC/EDQUOT/fault journaling, process interruption, fresh signed witness
issuance, or the full 127-node dual-MPFR verifier/checker cycle. The previous
Linux evidence for those tests is preserved in the ZIP but not re-executed.

This suite does not certify global optimality (0/15 original cases certified)
and makes no production C14/G25 release claim. All deliberate corruption is
performed on temporary copies, which are deleted. No private keys included.

The prior CH39 source and frozen data remain unchanged.
