# Cognitum C15 T3 — Windows ACL audit diagnostic-order correction

## Verified Windows evidence (user's second native retest)
- Windows AMD64, NTFS, Python 3.14.6. Python discovery and dependency installation succeeded.
- Native pytest: **3 passed, 1 failed, 3 skipped**. The harness stopped before process-recovery tests.
- Failure: `test_extra_inheritable_ace_rejected_by_sid_policy` required `UNAUTHORIZED_OR_DUPLICATE_ACE`, but audit produced `UNEXPECTED_ACE_ACCESS_MASK`.
- The auditor **did reject** the unauthorized BUILTIN\Users ACE, and the test failed only because it expected a specific rejection reason.
- This evidence is **not** a complete Windows gate pass.

## Engineering correction
- Validate SID authorization and uniqueness before exact access-mask equality. Both validations remain mandatory; unknown SIDs, inherited/unexpected flags, wrong masks, NULL DACLs and extra ACEs are still rejected.
- Add a negative test: authorized current-user SID with its access reduced to RX must fail the exact-mask check.
- Retain both existing unauthorized-ACE tests unchanged. Add a portable test guarding diagnostic-check ordering.
- Changes are confined to the Windows ACL auditor, its tests, and the source integrity manifest; Lu and the original Cognitum checkpoints are unchanged.

## Reproducibility and limitations
- Focused Linux run: **19 passed, 6 Windows-only skipped**.
- Wider T3 sweep exceeded its time budget at ~58% and is **not** counted as a pass.
- All tracked source file hashes and both ZIP CRCs verified at packaging; the launcher pins the embedded SHA-256 hash.
- Windows ACL correction and new negative test are **awaiting native execution**.
- Windows process restart/DPAPI/epoch rotation are still **not accepted**; power loss and independent rollback protection are separate gates.

## Windows retest
Extract the new ZIP into a fresh local NTFS folder; double-click `Run-Cognitum-Windows-Gate.cmd`. Upload `Cognitum_Windows_x64_Test_Evidence.zip` from the new `Windows-Native-Run-*` directory. The Python-selection fix for the stale LM Studio Python registration is preserved.

## Final package verification

- 75 of 75 Protobuf schemas compiled successfully with `protoc` 3.13.0 from clean extraction.
- 842 tracked source hashes matched; the outer and inner ZIPs passed CRC verification.
- The Windows launcher SHA-256 pin matches the embedded candidate.
- Verified download package SHA-256: `b499e5aa24cc7aff26392c9489ec0e05f10ed0abd1632fbf6db35270e3cbc5c9`.
- Windows-native acceptance remains open until the revised kit is run on Windows.