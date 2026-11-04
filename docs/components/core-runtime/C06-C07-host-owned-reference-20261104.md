# C06/C07 host-owned reference — initial implementation (2026-11-04)

## Ownership and scope

Lu remains the **only** canonical ANSF/SQLite memory and permission authority.
Cognitum does not open a canonical database, mint scope or user identities,
apply mutations, schedule workers, or persist alternate memory.

- `cognitum.memory_retrieval` accepts host-supplied canonical record snapshots,
  provides explicit exact-scope and validity filtering, bounded literal-token
  matching, latest-revision suppression and tombstone handling.
- `cognitum.state_revision` replays host-supplied ordered claim events and rejects
  stale expected revisions, conflicting event IDs and invalid transitions. The
  result is a *derived* state view, never a durable authoritative event writer.
- Provenance includes source IDs, citation handles, claim origins and conflict
  source references. USER_DECISION, IMPORTED_CLAIM and MODEL_HYPOTHESIS stay distinct.

## Security boundary

`actor_authority` is an opaque host attestation field, **not** a permission
that Cognitum may validate or mint. Host validation must happen before dispatch.
The pure Python reducer does not provide cross-process exactly-once semantics:
Lu's atomic effect journal/ANSF transaction must enforce it.

## Gates remaining

1. Pass the new `tests/test_c06_c07_reference.py` and the full portable
   Python regression across Windows/Linux 3.11 and 3.13.
2. Replace reference token matching with a host-owned SQLite FTS5/BM25
   index contract, including index invalidation, canonical revision and
   tombstone synchronization. Benchmark retrieval vs exact lookup.
3. Define and compile strict native Protobuf C06/C07 wire schemas. Test
   malicious, malformed, oversized and cross-scope input.
4. Integrate against Lu's current ANSF snapshot/read and atomic
   append/journal APIs, using actual host grants and durable replay.
5. Validate authorization, revision conflicts and crash/restart recovery
   across process boundary before any model tool registration.
6. Evaluate retrieval accuracy and task impact with fixed model and
   measured resource budgets, not just deterministic unit tests.

No C06/C07 production gate is asserted by this checkpoint.
