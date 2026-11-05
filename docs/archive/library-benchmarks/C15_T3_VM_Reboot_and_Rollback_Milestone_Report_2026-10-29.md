# Cognitum C15 T3 — VM reboot & independent rollback witness

Date: 2026-10-29. Branch/repository: **none altered** (standalone copy of saved Cognitum Windows native gate candidate).

## Implementation

- **New** `standalone_vm_recovery/guest.py`: opt-in Windows x86-64 disposable-VM-only reboot preparation, post-boot P2Z journal replay, and separate snapshot-rollback genesis/advance/check phases. Requires an OS boot change on reboot verification. Does not issue reboot/shutdown or hypervisor power commands.
- **New** `standalone_vm_recovery/witness.py`: host-operator-run SQLite high-water witness with full transaction commit, non-rewinding scope/sequence/digest checks, and explicit rollback, fork, future/unwitnessed, and wrong-epoch verdicts. Witness DB must remain outside the guest VM and all snapshots. No guest-side authority to update DB.
- **New** `VM-Gate-Menu.ps1`, `Run-Cognitum-VM-Recovery.cmd`: explicit operator gating and VM-manufacturer heuristic; isolated guest state, verified 64-bit Python and pinned dependencies. Not a host attestation.
- **New** `Export-VM-Gate-Evidence.ps1`: allowlist-only evidence export; never includes DPAPI state, journal or witness DB.
- **New** `tests/test_c15_t3_vm_reboot_witness.py` plus `VM_GATE_README.md`.

## Offline verification observed

- New **12/12** VM-witness portable tests passed including simulated off-guest snapshot rollback detection.
- Selected legacy P2Y/P2Z/ACL + new regressions: **43 passed, 5 Windows-only skipped**.
- Protobuf independent verification: **75/75** source schemas matched Python binding wire shapes.
- Baseline saved Windows acceptance kit source tree compared file-by-file; predecessors preserved byte-for-byte.
- ZIP integrity/clean-extraction tests: see separate JSON verification evidence.

## Strict acceptance boundaries

| Gate | Current status |
|---|---|
| Previously recorded Windows x86-64 *process-level* acceptance | ACCEPTED (separate existing checkpoint) |
| VM restart with changed Windows boot ID and preserved committed P2Z state | **OPEN: not executed in a real Windows VM** |
| Hypervisor hard-off and independent event provenance | **OPEN** |
| Outside-guest high-water witness detects actual VM snapshot rollback | **OPEN: portable simulated rollback demonstrated only** |
| Production independent antirollback authority/TPM and Lu integration | **OPEN / out of scope** |

## Safety and provenance

The Windows VM must be disposable; this kit never initiates a physical restart or power cut. A local host SQLite database is an independent *test witness* only if actually isolated from the guest storage and snapshots; it is not a production trust service, HSM, TPM, signed remote authority, or tamper-proof audit log. The guest machine ID and hypervisor event log require independent operator review. No changes to Lu, GitHub, R1 or previous Cognitum Library checkpoints.