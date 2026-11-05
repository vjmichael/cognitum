# Cognitum C15 T3 Windows x86-64 — Python prerequisite failure and launcher repair

## Evidence-based finding

Source: user-provided `Cognitum_Windows_x64_Test_Evidence.zip`, `kit-summary.json` from the first Windows execution, completed 2026-10-29T14:52:51Z.

- `gate_status`: `FAILED`
- `failure`: `PYTHON_VENV_CREATION_FAILED`
- Verified original checkpoint digest: `d87cfe953332303333f0d396a7cb201cd7f7cf96717b9f78a7d35bf2470caf7e`
- The screenshot shows the Windows Python Launcher attempting `-m venv` with a missing interpreter path under an LM Studio `node_modules/isolated-vm/Python/pythoncore-3.14.0` tree.
- The native DPAPI, NTFS, ACL, epoch-rotation, and process-restart checks **did not execute**. This is not a product-level security test pass or failure.

## Corrective action

Built a replacement operator kit containing the **exact unchanged** hardened gate candidate. The launcher no longer calls `py.exe -3 -m venv` blindly. It discovers candidate Python executables from an optional explicit path, the Python Launcher registration list, PATH, and per-user/system PythonCore registration keys. Each candidate must exist, be a 64-bit Python >=3.10 with `venv`, `ensurepip`, and `ssl`, and produce a usable venv with `pip`. If a candidate is stale or broken, it is recorded in `python-selection.log` and the next candidate is attempted. A failed prerequisite yields an actionable error and an evidence ZIP without running Cognitum tests. Original evidence whitelisting and isolation remain in place.

The replacement includes the original source archive with **byte-identical SHA-256**. Eight portable package/static checks passed; **Windows execution of the repaired launcher has not yet been verified**.

## How to rerun

1. Download and extract `Cognitum_C15_T3_Windows_x64_Native_Test_Kit_Python_Fix_2026-10-29.zip` in a fresh folder on an NTFS volume.
2. Double-click `Run-Cognitum-Windows-Gate.cmd`.
3. If it reports `NO_WORKING_64BIT_CPYTHON_WITH_VENV_AND_PIP`, install or repair a complete 64-bit CPython 3.10+ distribution from `https://www.python.org/downloads/windows/`, enabling `pip` and `venv`. Do **not** alter LM Studio to solve this prerequisite.
4. If multiple installations are confusing the launcher, use the optional `COGNITUM_PYTHON_EXE` override described in `WINDOWS_TEST_README.md` inside the kit.
5. Upload the resulting **new** `Cognitum_Windows_x64_Test_Evidence.zip`. It should include `python-selection.log`, providing an audit trail of selection and rejection.

Security: evidence may contain local file paths, operating-system details, and account identifiers. Do not share protected journals, DPAPI blobs, HMAC keys, or scratch directories. Actual Windows acceptance remains open pending a successful native run. Lu and GitHub remain unchanged.