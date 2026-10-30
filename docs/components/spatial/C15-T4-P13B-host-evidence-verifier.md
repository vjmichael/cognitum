# C15 T4 P13B — independent host-side Windows kit evidence consistency check

**Portable test status:** 28 focused verifier tests pass; combined P13/host verifier focused set 32 passes; selected regressions 381 passed / 1 skipped / 17 subtests. **No real Windows gate or physical evidence identity certified.**

## Failure model and implementation

P13 guest runner writes its own `gate-result.json` and suite logs, including purported SHA-256 hashes. An untrusted guest-origin file can be accidentally corrupted after export or can contradict its own flags. P13B refuses untrusted JSON duplicate keys and NaN constants; wrong gate/schema; elevated assurance flags; wrong Windows/platform/Python/OpenSSL/direct package versions; missing, reordered, duplicated suites; nonzero child exit codes; absent positive pytest summaries; symlinks, oversize logs, missing files and SHA-256 mismatches. Windows CRLF is normalized to match Python `subprocess.run(text=True)` and `write_text` handling. No files are executed or changed by `inspect()`.

The resulting `INTERNALLY_CONSISTENT_UNATTESTED` verdict proves only internal evidence self-consistency under the verifier's checks. A forged guest test package can contain fabricated test output with matching hashes. Neither this script nor unsigned guest records can prove the originating VM, trusted host, Windows Job confinement, signed timestamp authority, or genuine calibration. Independent machine attestation is a **separate** future security gate.

## Usage on reviewer machine (not the disposable guest)

```powershell
python tools/verify_c15_t4_p13_windows_evidence.py "C:\Cognitum_T4_P13_Windows_Evidence" --out "C:\CognitumReview\p13b-verification.json"
```

Keep original guest evidence and independent verifier output separately. Reject all nonzero exit codes. A "consistent" result alone is not a P13 native execution pass; examine operator chain-of-custody and the substantive logs, and retain the strict unknown status until independent acceptance.

## External backlogs

- P13: Windows 11 x86-64 actual execution and operating-system level confinement remain open.
- P11/12: Real independent TSA, reviewer identities and calibrated, licensed measurements remain open.
- Lu: read-only reference, not modified or authorized.
