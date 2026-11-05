# Cognitum C15 T3 — Standalone Windows x86-64 Host Validation Harness

**Date:** 2026-10-29  
**Scope:** isolated standalone harness extending the saved P2Z checkpoint; **no Lu, GitHub, R1, or original P2Z source edits**.  
**Engineering status:** IMPLEMENTED and portable process/replay tests passed.  
**Windows-native status:** NOT RUN / NOT CERTIFIED in this execution environment (Linux x86-64).

## Implementation

1. **Host key custody:** epoch-specific random 48-byte HMAC secrets held in a DPAPI CurrentUser-protected local state file on Windows, with `icacls` restrictions to the current user and SYSTEM. The state stores the external host anchor separately from P2Y records. On non-Windows, an explicitly requested insecure control-flow backend is used; that backend is not a security test.
2. **Disk persistence:** temporary files are fsynced before publishing. The Windows-only P2Y adapter uses `MoveFileExW` with `MOVEFILE_WRITE_THROUGH` and no overwrite for journal records, while host anchor state replacement uses write-through replace after a cross-process byte-range lock. Only the standalone runner installs this adapter; the predecessor P2Y implementation remains unmodified.
3. **Restart/crash cases:** actual worker subprocesses exit at `(120) before record link`, `(121) after record publication but before host anchor commit`, `(122) after host anchor commit`. Each recovery uses a new process and independent P2Z/P2Y full replay. Case 121 requires a one-use host-issued test approval for exact candidate hashes; 120 stays blocked; 122 recovers normally.
4. **Epoch lifecycle:** clean-state verification before rotation, strictly increasing epoch, fresh secret and key ID, separate journal directory, stale epoch rejection, revocation persisted in the local anchor store. Old journal files are not deleted or rewritten.
5. **Windows gates:** require x86-64 Python, NTFS on the temporary test volume, DPAPI seal/unseal with tamper rejection, restrictive ACL application, reparse/symlink checks, and Windows subprocess recovery. A standalone PowerShell launcher and optional GitHub Actions **template** are included; no workflow has been installed or dispatched.

## Verification evidence

- Combined selected P2S–P2Z and new harness regression: **146 passed, 2 skipped** on Linux (the skips are Windows-specific tests).
- Clean-extracted harness tests: **3 passed, 1 skipped**.
- Clean-extracted existing P2Z tests: **14 passed**, with 2 nonselected cases for the filtered Linux run.
- Independent Protobuf compilation and Python descriptor parity: **75/75 passed**.
- ZIP CRC check passed. **824 original archive files are byte-identical**; **9 new files** and 2 self-describing evidence/inventory files added (**835 members** total).
- Local three-crash process-control study: `REJECTED`, `AUTHENTIC_UNANCHORED_TAIL`, and `CLEAN`; exact recovery and test-only epoch rotation passed. See JSON evidence for details.

## Security boundary and unresolved gates

This is a **local experimental host**, not an independent authority and not the Lu trusted host. Windows DPAPI CurrentUser protects at-rest secret material from other user contexts, but the user or an administrator controlling both local protected state and journal can roll them back together. HMAC does not encrypt camera/voxel journal payloads. The test host can generate its own reconciliation token; production user authorization/consent is not implemented. Secrets temporarily appear as Python bytes in memory; no memory-zeroization claim is made.

**Not tested:** any native Windows API execution in this run; independent ACL inspection and cross-user permission tests; NTFS/storage-controller power-cut guarantees; Windows reboot/OS restart; drive removal and controlled VM power loss; TPM/remote monotonic high-water authority; durable key backup and old-epoch recovery; true Lu integration; full real-sensor benchmarks; p50/p95/p99 I/O latencies. Real Windows process termination requires executing the included harness on Windows; no Windows success should be inferred from the Linux runs.

## Run on Windows x86-64

1. Extract the full ZIP into a fresh workspace (do not use Lu AppData directories).
2. Install x64 Python and the pinned requirements:

```powershell
py -3 -m pip install -r standalone_windows_host/requirements.txt
```

3. Run the Windows acceptance preflight and process-level tests:

```powershell
.\standalone_windows_host\Run-Windows-Host-Gates.ps1 -EvidenceDirectory .\windows-host-evidence
```

4. Retain the generated JSON, test output, OS version, NTFS volume metadata and installer/dependency versions. A passing run means **process-level host harness validation**, not power-loss, antirollback, or production acceptance.

**Recommended next gate:** Run on an actual isolated Windows x86-64 NTFS machine, collect DPAPI/ACL/recovery evidence, then perform VM snapshot/power-cut tests and introduce a genuinely independent high-water authority before attempting host integration. Keep R1 frozen.