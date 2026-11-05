# Cognitum C15 T3 P2Z — Trusted-host integration readiness and crash recovery

**Status:** Offline engineering milestone implemented and verified. **Not** production-ready or connected to Lu. Source baseline: P2Y immutable host-anchored journal. R1 tracking baseline and prior T3 milestones preserved.

## Implemented

- New research-only, typed Protobuf `P2ZHostBinding`, `P2ZRecoveryPreview` and `P2ZReconcileIntent`; external host must supply key custody, live epoch/anchor, durable CAS, and one-use reconciliation authorization.
- P2Z host bridge uses P2Y full-replay verification. It refuses changed key identifiers or authority epochs on a live bridge.
- Read-only triage: CLEAN, one cryptographically authentic unanchored tail, or REJECTED. Tail approval is blocked until complete independent full replay against a temporary non-authoritative anchor.
- An exact old anchor, candidate anchor, candidate record SHA-256 and independently verified host proof are required to reconcile a single tail; no automatic deletes or overwrites. A successful host commit is checked by opening the P2Y journal again.
- Epoch-rotation enrollment preflight requires new epoch, distinct key ID, a clean new journal location and fresh genesis. No automatic migration or issuance of authority.
- Linux test-only process-crash matrix: before record link, after record link/before host commit, and after host commit/before worker return.

## Validation

| Gate | Measured result |
|---|---|
| P2S–P2Z focused predecessor and new tests | **143 passed, 1 Windows-only skip** |
| Additional P2Q/P2R/general-volume tests | **47 passed** |
| C07 regression | **218 passed**, 71 subtests passed |
| Independently compiled Protobuf source/bindings | **75/75** |
| Linux process-crash matrix | **3/3 expected transitions** |
| Entire C07/C13/C14/C15 sweep | **Incomplete (timed out); NOT a pass** |
| Windows power-loss / actual host / real sensor | **NOT TESTED** |

The process-crash simulation uses a test-only file-backed host anchor, not protected key custody or a Lu host. The journal contents are HMAC-authenticated **plaintext**. Windows ACL, link/fsync/NTFS and genuine OS-restart/power-loss behavior are unverified. Python process-level key isolation is also not certified.

## Engineering audit

Exactly **7 source/test/documentation files added, 1 existing file modified** (`tools/check_proto_descriptors.py`), and 0 files removed compared with the pinned P2Y checkpoint. No P2Y implementation edits, no Lu or GitHub changes. Earlier benchmark backlogs remain unchanged.

## Deferred acceptance

See the companion backlog JSON and `docs/components/spatial/P2Z-host-epoch-recovery.md`: real host trust store/CAS/approval, Windows x86-64 filesystem semantics, restart/power-loss, rotation, corrupted journal operator handling, resource profiling and real 3D sensor validation. This milestone establishes a testable **contract**, not authority to use a physical-world prediction.