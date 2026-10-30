# C15 T3 Windows x86-64 native acceptance gate — ACL audit revision

This is a **candidate Windows-native gate**, not a Windows pass. It adds a Win32
DACL writer/auditor and durable acceptance evidence to the previous standalone
harness. The original P2Z checkpoint and Lu are unchanged.

## Run on Windows (PowerShell, not WSL)

Extract the checkpoint ZIP into a NEW dedicated folder on an NTFS drive outside
Lu, Cognitum production journals, and protected profile directories. Install
x64 Python 3.12+ and the pinned dependencies:

```powershell
py -3 -m pip install -r standalone_windows_host/requirements.txt
.\standalone_windows_host\Run-Windows-Host-Gates.ps1 -Python py -EvidenceDirectory .\windows-host-evidence
```

The script selects a dedicated scratch area **under the extracted checkpoint**;
no test journals should be directed to any existing application workspace.
The harness writes `gate-summary.json`, Python/OS/NTFS preflight evidence,
`pytest-native.log`, subprocess test results, and evidence checksums. If any
native gate fails, its summary is FAILED. A PASS remains limited to **Windows
process-level validation**.

The Win32 DACL gate now sets a protected DACL consisting solely of explicit
full-control ACEs for the current Windows account and LocalSystem. It then
**re-reads the security descriptor and every ACE** without relying on localized
`icacls` text. A negative test adds a BUILTIN\\Users read permission and checks
that the independent auditor rejects it. The DACL is restored afterward.

## Still not certified by these tests

- Windows 10/11 OS reboot and hypervisor power-cut durability
- Controller write-cache, disk flush, and file-system ordering during sudden loss
- TPM/remote independent antirollback authority or protection against same-user rollback
- Separate-user and elevated-admin read-denial validation
- Lu trusted-host integration, user consent, protected service account, real sensors

Windows-specific API behavior cannot be certified by running the portable tests
on Linux. The Linux control-flow tests are informational only.

## Regression evidence in this package

The new ACL/API code is not executed on Linux. The portable new/native-adjacent
suite, previous P2Z recovery tests, compileall and 75 independent Protobuf
schema checks are logged separately. The comprehensive T3 sweep exceeded the
available test timeout and must not be reported as passed.
