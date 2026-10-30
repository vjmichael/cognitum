# C15 experimental checkpoint ledger — 2026-10-29

> **Status accounting only.** The historical GitHub `main` snapshot contains Revision 1.5/C01–C19 designs, not the full later C15 implementation described here. Source checkpoints are local ZIP artifacts pending independent repository reconciliation. **No Lu modifications or enabled Lu capabilities.**

## C15 T3 — Experimental Windows VM recovery (passed)

On a disposable Windows 11 x86-64 VirtualBox guest, the Run2 writer-fix recovery kit reported clean journal replay with a changed boot identity. Independent physical-host witness comparisons reported `MATCH` for reboot and hypervisor-power-off recovery (guest sequence 1, host high-water sequence 1). The snapshot rollback experiment restored guest sequence 0 against host high-water 1; independent verifier returned `ROLLBACK_DETECTED`, the expected negative-test success. A physical-host VirtualBox log also recorded a GUI power-off request, transition to `OFF`, and subsequent VM startup.

**Not certified:** production physical power-loss durability, hardware rollback resistance, TPM-backed host authority, real Lu supervisor, or OS isolation. Preserve original experimental evidence and SQLite witnesses privately.

## C15 T4 — Portable synthetic research status

| Gate | Local checkpoint finding | Still open |
|---|---|---|
| P0–P3 | Typed functional/material constraints, adversarial tests, frozen synthetic falsification ledger | Real engineering validation |
| P4 | Reference-byte integrity and calibration/holdout partition checks | Authenticated real sources |
| P5–P7 | Signed evidence, study-plan lock and two-reviewer consistency, synthetic | Qualified external publishers/reviewers |
| P8–P10 | Role-separated trust-policy revocation, notary signature and staged calibrated CSV intake, synthetic | Protected trust roots, real calibration |
| P11 | Offline RFC 3161 request/response verification and signed-token chronology, synthetic | Trusted TSA issuer, actual preregistration and revocation proof |
| P12 | Uncertainty-aware threshold and holdout checks, synthetic | Licensed real measurements and instrument certification |
| P13 | Windows x86-64 runner implemented and contract-tested on Linux | **Real Windows execution and host review** |
| P13B | Offline evidence-consistency verifier implemented; 28 focused tests passed | Machine-origin attestation, actual P13 Windows run and OS sandboxing |

P13B checks four expected test suites and eight captured log files against `gate-result.json`, recomputes SHA-256 over normalized log contents, checks declared platform/version/assurance flags and positive pytest summaries, and refuses missing, symlinked, oversized or contradictory evidence. **A matching hash is not authentication.** It returns `INTERNALLY_CONSISTENT_UNATTESTED`; never treat this as native Windows certification or authority.

**P13B portable verification:** 28 dedicated tests passed; 32 tests passed in the combined runner/verifier group; selected C15/T3/C14/C13/C07 regressions **381 passed, 1 skipped and 17 subtests passed**, all on the available Linux runtime. The predecessor checkpoint reported **82/82 independently compiled Protobuf descriptors**; P13B adds no Protobuf schemas. These are test-run-specific counts, not full CI or end-to-end Lu/model benchmarks.

## Next acceptance work

1. In a disposable Windows 11 x86-64 VM run `Run-Cognitum-T4-P13-Windows.cmd` from the complete extracted P13B checkpoint, with manually installed pinned dependencies and OpenSSL. Do not alter T3 witnesses.
2. Export the resulting `Cognitum_T4_P13_Windows_Evidence` directory and independently execute `python tools/verify_c15_t4_p13_windows_evidence.py <exported-evidence-dir> --out <new-report.json>`. Preserve raw logs and manually corroborate machine provenance.
3. Real TSA/nonce custody, signed time authority, source licensing, calibrated observations, qualified blind review and Windows OS confinement remain separate open gates.
4. Matched Cognitum-on/off Lu-model efficacy benchmarks remain deferred. Lu remains read-only; this documentation does not authorize integration.

**Source checkpoint:** `Cognitum_C15_T4_P11_P13_Timestamp_Uncertainty_Windows_Ready_2026-10-29.zip` (SHA-256: `b30d06d70a55e15d6c11f34fee8ae71cc67f12c277f492bbc2961c619ddb326d`), followed by the P13B local addendum. The full C15 T4 code is **not yet committed to GitHub**.