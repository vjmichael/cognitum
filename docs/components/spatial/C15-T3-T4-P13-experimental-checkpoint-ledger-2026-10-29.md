# Cognitum C15 experimental implementation and acceptance ledger — October 29, 2026

**Repository scope:** Cognitum only. This ledger updates the stale Revision 1.5 GitHub status without rewriting the earlier design provenance. **Source in checkpoint ZIPs is not thereby present in Cognitum `main`**. Lu has not been modified. None of these component-level results enables Cognitum capabilities inside Lu.

## T3: Windows recovery and rollback experiments — completed experimental gates

On October 29–30 UTC, a disposable VirtualBox Windows 11 x86-64 guest ran the Run2 writer-fix recovery kit. The operator preserved independent physical-host SQLite witnesses. Distinct experiments recorded:

- Reboot/replay: guest reported `REBOOT_AND_FULL_REPLAY_PASS`, changed boot identity, `p2z_status: CLEAN` and physical-host external witness `MATCH`.
- Snapshot rollback: restored guest sequence 0, independent host high-water sequence 1, host verifier returned `ROLLBACK_DETECTED` and `pass: false`; **this is the desired negative-test pass**, not a failed anti-rollback detector.
- Forced VM power-off: guest after restart reported `REBOOT_AND_FULL_REPLAY_PASS`, sequence 1, changed boot and clean P2Z; separate physical-host database `powercut-highwater.sqlite` reported `MATCH`, 1 vs 1. Host-side VirtualBox session log recorded the GUI power-off request and VM transition to `OFF`; the next log showed subsequent startup.

**Experimental-only:** This establishes the recorded VirtualBox operation and guest recovery consistency for that disposable environment; not hardware power-loss/durable-disk proof, production TPM root custody, or a Lu host/worker isolation certification. Evidence artifacts are archived separately from GitHub source; do not publish protected host witness databases or private keys.

## T4: Engineering constraint and reference-evidence research

| Gate | Checkpoint outcome | Unmet promotion gate |
| --- | --- | --- |
| P0–P2 | Typed structural/material constraints and adversarial tolerance research passed local synthetic suites | Actual physics/material validation |
| P3 | Frozen synthetic falsification ledger and calibration/holdout evaluation | Licensed external reference values |
| P4 | Evidence-byte hashes, study identity, partition isolation and content checks passed portable suite | Authenticated evidence source |
| P5–P7 | Ed25519 signed sources, signed study-plan locking, distinct two-reviewer consistency passed **synthetic** tests | Actual trusted source, timestamp and qualified independent reviewers |
| P8–P10 | Pinned policy generations/revocation, distinct notary role, staged CSV/units/calibration intake passed portable tests | Protected authority roots, independent notary, real allowed dataset |
| P11 | Offline RFC 3161 request/token verification and claimed chronology passed synthetic tests | Real TSA trust chain, revocation/nonce custody, independent preregistration |
| P12 | Exact-Decimal uncertainty bounds and holdout label checks passed synthetic tests | Actual calibrated measurements and authorized safety thresholds |
| P13 | Windows x86-64 non-admin operator test runner and portable runner-contract tests passed | **Actual disposable Windows 11 x86-64 invocation and independent evidence review**; this is not a Job Object/AppContainer test |
| P13B | Independent **offline evidence-consistency** verifier and adversarial unit tests added after P13 | Guest-source authenticity, host-side machine attestation and the actual P13 Windows run still open |

**P13B scope:** `tools/verify_c15_t4_p13_windows_evidence.py` independently reads `gate-result.json`, exactly four expected suite modules and eight captured logs; checks digests, platform/package assertions, nonprivileged flags, report structure and positive pytest summaries; rejects symlinked/missing/oversized/tampered files and contradictions. The result `INTERNALLY_CONSISTENT_UNATTESTED` is **never** a Windows execution certification. A fabricated report with internally matching hashes can pass this consistency check. Do not use it as an authorization source.

**Local test accounting (new P13B checkpoint):** new verifier tests **28 passed**; P13 runner+verifier focused tests **32 passed**; selected T4/T3/C14/C13/C07 regressions **381 passed, 1 skipped, 17 subtests passed**. This is not a comprehensive repository test suite, and the numerical counts are specific to an offline Linux Python environment, not GitHub CI or native Windows. P11–P13 predecessor checkpoint compiler parity was **82/82 Protobuf source/binding schemas**; P13B adds no Protobuf schema.

## Acceptance, current blocker and handoff

1. Run `Run-Cognitum-T4-P13-Windows.cmd` only inside a disposable Windows 11 x86-64 VM, with manually installed pinned dependencies and OpenSSL. Do not use a protected host, reboot VM or amend T3 witness databases for this P13 test.
2. Export `Cognitum_T4_P13_Windows_Evidence/` to an independent review machine. Run `python tools/verify_c15_t4_p13_windows_evidence.py <exported-evidence-dir> --out <new-independent-report.json>`. Inspect report and original logs; do not treat self-reported metadata or self-hashes as proof of physical execution.
3. Separate OS process confinement/denied-privilege probes and real identity/measurement certification are still open. Real matched Lu+model performance comparisons and production release also remain deferred.
4. Published GitHub docs are a status ledger only. Full T3/T4 source checkpoints and private experimental evidence must be reconciled and reviewed before any future code import or merge; no Lu changes are authorized by this ledger.

**Source checkpoint:** `Cognitum_C15_T4_P11_P13_Timestamp_Uncertainty_Windows_Ready_2026-10-29.zip` (SHA-256 `b30d06d70a55e15d6c11f34fee8ae71cc67f12c277f492bbc2961c619ddb326d`), followed by local P13B verifier checkpoint. Historical claims in the Oct 27 R1.5 index remain true for the original GitHub snapshot but are no longer a complete record of off-repository research.
