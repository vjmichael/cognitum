# C15 T3 P2Z — Trusted-host boundary and recovery readiness

## Purpose

P2Z is an **opt-in research component** built on P2Y. It does not implement a Lu trusted host and does not modify Lu. Its job is to make the host/journal boundary precise, supply a read-only recovery diagnosis, enforce explicit *independent host* authorization for one fully verified unanchored record, and prepare epoch-isolated key rotation. No result certifies a physical scene or grants authority.

## Trust architecture

The trusted host, not Cognitum, must supply `P2ZHostBinding`, containing a scoped `P2YHostAnchor`, epoch and key identifier; resolve the epoch-specific secret **outside the journal**; perform atomic durable compare-and-swap of the latest anchor; and independently approve an exact reconciliation (old anchor, candidate anchor, candidate record SHA-256, opaque one-use authorization proof). A local P2Z method cannot issue or validate such a proof. Tests use simulated authorities and a test-only file-backed anchor; neither is production key custody. The simulated on-disk anchor does **not** qualify as a protected host trust store.

`P2ZHostReadiness.open_session` delegates to P2Y; no weakened shortcut. P2Y validates HMAC records, exact Protobuf bytes and full P2W replay parity. The host binding is checked on subsequent operations for changed key ID, epoch, conversation or volume. A rotation in place is rejected.

`inspect()` returns `CLEAN`, `AUTHENTIC_UNANCHORED_TAIL` or `REJECTED` and does not edit journal records. For a single unanchored tail, it validates chain/scope/MAC, exact input/result formats, and **independently replays the entire candidate journal** against a temporary non-authoritative anchor before returning a candidate anchor. Multiple tails, missing records, untrusted state, invalidated host epochs, altered requests and temp files do not get auto-repaired.

`reconcile(intent)` validates an exact fresh preview, then calls `host.approve_reconciliation(...)`; the host must check the opaque proof, enforce scope/revocation/one-time use and atomically persist the new external anchor. The code refuses empty or mismatched proofs and performs full restart replay against the committed host anchor. It never deletes or overwrites an unanchored record. This solves neither an adversarial compromised host nor distributed transaction atomicity.

`validate_epoch_transition` accepts only host-issued, *strictly increasing* epoch, new key identifier, fresh distinct journal directory and a clean genesis anchor. It does not migrate keys, authorize rotation, revoke the old key or move files. Actual host-backed rotation, archival retention, and cross-process isolation remain pending.

## Crash matrix (local Linux subprocesses, not power loss)

- **Before record link**: an incomplete `.tmp-*` file remains; recovery is blocked pending explicit operator action.
- **After durable record write, before host CAS**: an authenticated unanchored tail is reported; a separately approved host action can commit the exact candidate after full replay.
- **After host CAS, before worker return**: a new process recovers normally against the durable external test anchor and independently replays the record.

The harness executes actual `os._exit(...)` subprocess termination. Its file-backed host is a test double. No Windows tests, ACL certification, actual machine restart/power cut, host trust-store security, or real sensors were involved.

## Windows x86-64 validation required before promotion

1. A real Windows runner must execute P2Y/P2Z exact same-scope two-process create/CAS, recovery, live revocation and wrong-key tests in a private NTFS directory.
2. Validate exclusive-record creation, rename/link behavior, file flush and directory durability under Windows (`os.open(directory)`/`os.fsync(directory)` in P2Y may be unsupported); use a Windows-specific durability mechanism if needed **before** claiming installed behavior.
3. Audit ACLs, junctions, reparse points, symlink traversal, user-profile key isolation and quotas; POSIX `0o700` checks are not Windows ACL checks.
4. Run process-kill and actual OS restart tests, then controlled power-loss testing in a disposable VM with retained host high-water marks.
5. Integrate a **real** Lu host authority only after separate user authorization, with durable key custody and epoch-aware revocation. Do not add MCP transport or modify Lu as part of this checkpoint.
6. Measure p50/p95/p99 fsync latency, disk growth, recovery time and full replay parity. Prove privacy/retention and secret-handling controls.

## Limits and non-goals

- HMAC is **integrity**, not data confidentiality; journal payloads are plaintext. P2Z transiently holds host-provided secret bytes in process memory.
- A deterministic record hash and a simulated host proof do not confer production authority.
- Reconciliation is an **operator-approved exceptional action**, not automatic self-healing.
- Clock synchronization, independent sensors, camera truth, T1 tracking accuracy, and T2 physically verified structure remain separate validation problems.
- Real Windows runtime and installed Lu host behavior are **unverified**.

## Reproducible commands

```bash
PYTHONPATH=. python -m pytest -q tests/test_c15_t3_p2z_host_recovery_readiness.py
PYTHONPATH=. python -m pytest -q tests/test_c15_t3_p2s* tests/test_c15_t3_p2t* tests/test_c15_t3_p2u* tests/test_c15_t3_p2v* tests/test_c15_t3_p2w* tests/test_c15_t3_p2x* tests/test_c15_t3_p2y* tests/test_c15_t3_p2z*
PYTHONPATH=. python tools/verify_protobuf_schemas.py --require
PYTHONPATH=. python tools/run_c15_t3_p2z_crash_matrix.py --out /tmp/p2z_crash_matrix.json
```
