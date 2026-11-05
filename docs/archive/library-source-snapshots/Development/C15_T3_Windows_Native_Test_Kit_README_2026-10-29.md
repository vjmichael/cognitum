# Cognitum C15 T3 Windows x86-64 native test kit

This is the operator-run native acceptance package. **Windows tests have NOT run in ChatGPT's Linux environment.** The kit embeds the exact existing hardened gate candidate unchanged.

## On a Windows x86-64 computer

1. Install **64-bit Python 3.10+** (Python Launcher `py` is preferred), with networking to install the pinned `protobuf==6.33.6` and `pytest==9.0.2` packages. You do not need Administrator privilege if your Python and folder are accessible. The test harness itself verifies x64 and NTFS.
2. Extract this entire ZIP onto an **NTFS drive** into a new folder. Do not run it inside another ZIP, a Windows junction, or a cloud-synced reparse folder. Do not use Lu's install directory or AppData.
3. Double-click **Run-Cognitum-Windows-Gate.cmd** and review what it will execute. The launcher invokes a PowerShell script, creates a uniquely named Windows-Native-Run directory, creates an isolated Python venv, installs the pinned dependencies into that venv, unpacks the original checkpoint and runs its native suite.
4. Find **Cognitum_Windows_x64_Test_Evidence.zip** inside the newly generated `Windows-Native-Run-*` folder. Upload **only that evidence ZIP** to this chat for acceptance analysis (you can inspect it first). It contains diagnostics and may include OS details and your Windows account SID. Do not upload the complete scratch or protected-state directories.

A failure is a valuable test result, not a reason to relax a security check. Preserve the evidence ZIP and any error message. Never disable ACL or DPAPI gates merely to produce a pass.

## What the gate checks

- Native Windows x64 and 64-bit Python on NTFS.
- DPAPI round trip and tamper behavior, exact ACLs and unwanted-ACE rejection.
- Journaling and write-through publication, subprocess interruption at 3 crash points, explicit host reconciliation, independent replay parity, authority epoch rotation and revocation.

## What it does NOT certify

Actual power-loss survivability, malicious same-user rollback, a separate trusted authority, real Lu integration, real-sensor measurements or production key custody. The test authority uses user-scoped DPAPI; it is not independent or TPM-backed.

## Integrity

Embedded checkpoint SHA-256: `d87cfe953332303333f0d396a7cb201cd7f7cf96717b9f78a7d35bf2470caf7e`. The launcher verifies it before extracting or running.

No original source file or GitHub repository is modified by this kit. All generated files are confined to the new Windows-Native-Run folder.