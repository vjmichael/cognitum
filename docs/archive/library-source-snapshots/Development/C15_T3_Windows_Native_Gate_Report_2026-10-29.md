# Cognitum C15 T3 — Windows native ACL/evidence gate candidate

**Status:** engineering changes implemented and portable tests passed. **Windows x86-64 native execution NOT performed** in this Linux environment. No Windows process-level acceptance claim is made.

## Changes

The prior standalone Windows host harness was audited and improved in four ways:

1. **Exact ACL installation:** A Win32 API DACL writer replaces an `icacls /grant`-based approach that could retain unwanted explicit ACEs. It sets CurrentUser + LocalSystem with protected inheritance, and a separate API reads every ACE, identity, mask, and inheritance flag and fails if extras remain. This is code reviewed against Windows API documentation but has not been executed on Windows.
2. **Negative ACL test:** Windows-only test temporarily grants BUILTIN\Users read access; the independent auditor must reject that state. The test also covers exact file and directory DACL installation.
3. **Dedicated scratch and evidence:** The Windows runner creates test journals in an explicitly designated scratch folder inside the extracted checkpoint, verifies native Windows/x64/NTFS, and writes operating system metadata, test logs, crash outcomes, gate status even on failures, and evidence hashes. No production Lu files should be selected.
4. **DPAPI corruption behavior:** The test recognizes that DPAPI may sometimes return corrupted bytes rather than always raising a particular Windows error. It will not accept corrupted bytes as the original secret.

## Verification (Linux only)

- 19 targeted tests passed; 4 Windows-only tests skipped.
- 75 independent `.proto` compilation/parity checks passed.
- The three subprocess crash scenarios passed on Linux (recovery states: REJECTED, AUTHENTIC_UNANCHORED_TAIL, CLEAN).
- Portable test-host run used a dedicated scratch folder and reported PORTABLE_TEST_ONLY.
- The wider T3 suite produced partial output but hit its timeout. **Do not count as a pass.**
- Parent harness: 832 files retained byte-for-byte, 3 changed, 5 added, zero removed.

## Run the actual native gate

On a dedicated Windows x86-64 NTFS machine, extract this ZIP into a new folder and run in PowerShell:

```powershell
py -3 -m pip install -r standalone_windows_host/requirements.txt
.\standalone_windows_host\Run-Windows-Host-Gates.ps1 -Python py -EvidenceDirectory .\windows-host-evidence
```

The generated `windows-host-evidence` directory contains the native preflight, ACL and subprocess evidence, tests and SHA-256 summary. Any unexpected native behavior fails the gate. A pass covers Windows **process-level** validation only.

## Still pending

- Actual Win32 API execution (DPAPI, ACL readback, NTFS write-through, fresh Windows process restart)
- Separate Windows user-account access-denial test
- Controlled VM reboot / sudden power loss / storage flush testing
- Genuine independent monotonic antirollback authority, consent, and Lu integration
- Full broader T3 regression sweep

**No Lu, GitHub, original Cognitum dataset, or R1 baseline modifications.**