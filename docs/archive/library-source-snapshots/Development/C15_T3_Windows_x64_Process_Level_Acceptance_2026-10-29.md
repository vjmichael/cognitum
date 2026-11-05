# Cognitum C15 T3 — Windows x86-64 Process-Level Acceptance

**Decision:** PASS — process-level Windows acceptance gate only. NOT production durability or end-to-end certification.

**Evidence reviewed:** User-provided `Cognitum_Windows_x64_Test_Evidence(4).zip` (SHA-256 `6b8d12792f3bf25516400a1303c14b44abe11c146b1e15070cb3ceaf11ab3888`), dated October 29, 2026. The ZIP integrity test passed, and each of its six `evidence-sha256.json` file digests matched its corresponding payload.

## Native environment

- Microsoft Windows 10 Home, version 10.0.19045, AMD64 / 64-bit Python 3.14.6
- C: volume verified as NTFS; dedicated scratch workspace used
- Working Python interpreter selected; broken unrelated interpreter registration skipped

## Results and scope

- `pytest-native.log`: **5 passed, 3 skipped, 0 failed** (2.35s). The three skipped tests are portable non-Windows controls explicitly skipped when `os.name == 'nt'`, not required Windows tests.
- Four native ACL negative/positive tests passed. ACL audit reported a protected DACL with exactly two entries (current user and SYSTEM). Unauthorized ACEs, unexpected masks and incorrectly inherited entries were rejected by tests.
- Native Windows DPAPI user-scoped protect/unprotect round trip and tamper rejection: passed.
- Three real Windows child-process termination and restart cases passed in the standalone harness:
  1. Before journal link: rejected; no automatic repair (exit code 120).
  2. Before host commit: authentic unanchored tail; independent full replay only after explicit approval (exit code 121).
  3. After host commit: clean recovery, independent full replay, isolated authority epoch rotation 9→10, revocation enforcement and stale epoch rejection (exit code 122).
- `kit-summary.json`, `gate-summary.json`, and `windows-process-restart.json` agree on the result: `WINDOWS_PROCESS_LEVEL_GATES_PASSED_NOT_CERTIFIED`.

## Explicitly open acceptance gates

- Windows OS reboot recovery not tested.
- Power-loss and storage-flush durability not tested; NTFS selection alone does not certify power-failure behavior.
- Independent, tamper/rollback-resistant high-water authority not implemented or validated in actual production host; test host is standalone.
- Actual Lu host integration and real sensor/volumetric data validation not tested.
- This is a research engineering acceptance, not a security certification or proof against all local adversaries.

**Project constraints honored:** R1 tracking baseline frozen; no change to Lu or GitHub. Preserve previous negative findings and test evidence.