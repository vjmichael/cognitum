# C06 P7 — Lu-native host fence and typed Protobuf bridge

P7 is a **Library-only source implementation** staged for a pinned Lu Rust checkout, NOT an operational Lu extension. See [overlay installation and security review](../../../integrations/lu/README_C06_P7.md) for full scope, threats and validation.

## Implementation

- P6 native `AnsfMemoryGate` enhanced with `with_source_mutation` (persist-before-write, reauthorization, single SQLite policy lease through source mutation and catalog reconciliation, epoch invalidation, durable fail-closed recovery on failure).
- Host-only `HostMemoryFrameAdapter` accepts canonical bounded `MemoryQuery` / `CitationLookup` frames and emits typed `RetrievalReply` / `CitationResolution` frames. All candidate IDs, epochs, digest and revision/head state are rechecked by the gate; evidence is published only while the gate lease is held.
- The native compiled `.proto` is a byte-for-byte copy of the Cognitum schema. Existing Lu `prost` + `prost-build` and vendored `protoc` are reused; no JSON for Lu ↔ Cognitum internal data.
- Idempotent, safe, explicitly opted-in installer changes five paths in an exact clean Lu checkout; no GitHub changes.

## Evidence

Python unit regression 339/339, synthetic replay 12/12, C03 component smoke 10/10, independent nine-schema `protoc` source-to-checked-in Python binding verification. Rust source includes additional tests but **no native Rust compiler or executable Lu test ran** in this container. Source-level API compatibility was audited against Lu commit `bf2334a7d68f72265c37711de9bb5eda1f611d13` and its Rust `AnsfStore`, `OwnershipStore`, `prost`/`build.rs` interfaces.

## Explicit limitations and next gate

Do not claim P7 delivers production authenticated memory access: the Lu-native host must provide trusted identity, protect files/ACLs, route **every** ANSF mutation/import through the fence, and implement actual deletion/purge semantics. Rust/Windows compilation, effect/security approval gates, and real A/B/C/D model comparisons are pending. Existing Cognitum P5 Python reference remains untouched as an independent conformance baseline.
