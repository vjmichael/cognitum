# C06 P4–P5: Durable policy and source-recovery gate (offline reference)

**2026-10-27. Status:** Reference implementation only; native Lu host integration remains blocked.

P4 introduces `cognitum/ansf_host_policy_reference.py`: persistent owner-scoped grants, irreversible revocation, durable logical root tombstones, a policy SQLite write reservation spanning an ANSF source read and synchronous response publication, and failure-closed cancellation. The source is never accessed by an unauthenticated model-facing CE. The host fixture accepts `SyntheticPrincipal` objects only in tests; these are not credentials.

P5 introduces a persist-before-source-write pending flag. A trusted host must call `begin_source_update()` and durably commit the **policy** flag before starting a source mutation. The trusted host commits ANSF changes, reconciles derived indexes, and calls `finish_source_update()` only after recovery/verification is complete. The final operation atomically clears the flag and increments the index epoch, invalidating existing citations. While pending—even after process restart—reads fail closed and publish no evidence. Unauthorized principals cannot set or clear this flag in the fixture.

## Test evidence

- Complete Python unit suite: **321 tests passed**; includes 15 P4 host-policy tests and six new P5 crash/recovery tests.
- C03 synthetic smoke and 12-case replay remain separate non-Lu simulations.
- Scope and limitations: **No Rust host enforcement, authentication, durable cross-DB atomicity, physical erasure, model/CE registration, or live Lu instrumentation.** This gate only works when every source writer is disciplined by a trusted host; direct SQLite modifications bypass it. `finish_source_update` is not itself evidence that the host reconciled the source; a native host must implement and verify that condition before enabling reads. The Python policy code must not be deployed as Lu's authorization service.

## Native Lu integration blockers

1. Implement trusted host principal verification using Lu's `OwnershipStore` / `HostResourceAuthority`, never model-issued IDs.
2. Add a native shared session read/write fence with revocation and tombstone persistence; the policy acknowledgement must serialize with synchronous response delivery.
3. Guard **all** ANSF writers before source mutations and verify pending-change recovery before re-enabling lookup/citation.
4. Define user-visible deletion/retention/physical erasure independently of logical tombstoning; ANSF append-only entries, FTS5, WAL and backups remain present.
5. Run Rust native tests and independent `protoc` checks before any security promotion; record a real Lu+model benchmark instead of extrapolating from fixture tests.
