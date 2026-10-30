# C15 T3 — Standalone Windows x86-64 Host Validation Harness

This is an **isolated laboratory harness** for Cognitum P2Y/P2Z. It does **not** modify Lu, implement real Lu authorization, certify sensor-derived 3D results, or protect against rollback by an adversary that controls both the local journal and local state. The original P2Z checkpoint is frozen.

## Test matrix

| Gate | What is tested | Limit |
|---|---|---|
| Key custody | Windows DPAPI **CurrentUser** encrypted host state, random epoch-separated journal secrets, restricted ACLs | Same-user rollback and privileged compromises remain possible; not TPM or DPAPI-NG |
| Durable write | fsync/FlushFileBuffers on temp data + `MoveFileExW` with `MOVEFILE_WRITE_THROUGH`, `CREATE_NEW` temp files | No claimed power-loss guarantees; must validate on NTFS and VM fault injection |
| Host anchor CAS | Cross-process byte-range lock; exact expected anchor; durable write-through replacement | A local test host, **not** a remote independent authority or monotonic hardware counter |
| Restart | Real worker subprocess exits at three write/commit boundaries, new Python interpreter recovers | Does not reboot Windows or simulate power removal |
| Recovery | Uncommitted tail demands exact host-token approval; tampering fails closed; full P2W replay parity | The test host can issue its own approval token, so this is **not** real user authorization |
| Rotation | Epoch-specific random secret + different key ID/journal, old epoch rejected, revocation persisted | Retired-key archival / recovery strategy deferred |
| Privacy | Secrets sealed in DPAPI encrypted state, journal records authenticated | **Journal payloads remain plaintext**; no memory-zeroization guarantee |

## Run on an actual Windows x86-64 machine

Install 64-bit Python 3.12 or later, then from the extracted checkpoint root in a PowerShell terminal:

```powershell
py -3 -m pip install -r standalone_windows_host/requirements.txt
py -3 -m pytest -q tests/test_c15_t3_windows_host_harness.py
py -3 -m standalone_windows_host.runner --suite --out windows-host-evidence.json
```

Alternatively use `standalone_windows_host/Run-Windows-Host-Gates.ps1`, which checks Windows, 64-bit Python, NTFS, and runs both test and subprocess suites. The suite creates and removes fresh temporary host/journal directories. **Do not point it at Lu AppData or production journals.**

Linux control-flow smoke run is explicitly labelled insecure and cannot satisfy Windows acceptance:

```bash
python -m pytest -q tests/test_c15_t3_windows_host_harness.py
python -m standalone_windows_host.runner --insecure-test-only --suite --out portable-smoke.json
```

## Windows acceptance still outstanding

- Independent clean Windows x86-64 run and exact output log, including DPAPI/tamper checks, ACL audit, Windows record and anchor writes, and all crash points.
- Controlled reboot and VM power-interruption testing; NTFS/virtualization/storage-controller sync behavior and p50/p95/p99 write latencies.
- A **separately trusted** antirollback high-water record (secure service/TPM/remote authority), user authorization and consent, key backup/rotation/revocation policy, and threat model.
- Windows file-system reparse-point/TOCTOU hardening, file access auditing, Windows service account key scope, signing/distribution, journal encryption, and host integration only after separate authorization.

## Evidence standards

Portable results are valid only for process logic. A successful Windows run proves **process-level controls**, not hardware durability, independent host trust, key zeroization, or installed Lu behavior. The P2Y Windows writer adapter is installed only within this standalone process, preserving original P2Y source bytes.
