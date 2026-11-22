# Cognitum C15 T2 P2N — Structural ontology consistency checkpoint

**Result:** bounded typed taxonomy/structural relation audit implemented; research-only.

- **New Protobuf:** `ontology_subset.proto` with compiler-derived bindings; 63/63 independent schema comparisons pass.
- **T2 capabilities:** source-linked transitive subclass inference; disjoint type contradictions; explicit part/contains/connection relation signatures; open-world handling; deterministic digests; separation of inferred/observed/hypothetical claims.
- **T1/T2 handoff:** P2M image-space identity proposals revalidated and admitted as hypothetical ontology facts only; no T3 geometry or canonical scene mutation.
- **Selected regression:** 1,156 passed, 39 skipped, 567 additional subtests, 5 warnings. **This is not the full repository suite.**
- **Focused:** 17 tests passed, 5 subtests. Independent NetworkX and RDFLib checks on 168 seeded taxonomy DAGs; 72 additional seeded class-contradiction checks.
- **Legacy protection:** P2M source files unchanged except `tools/check_proto_descriptors.py` and `pyproject.toml`; previous six-item benchmark backlog byte-identical; Lu and GitHub unchanged.
- **Deferred:** OWL 2 RL (owlrl) official external reasoner parity, real structural dataset evaluation, and calibrated T2/T3 geometry. The test environment has RDFLib, NetworkX and Protobuf but no owlrl. No unsupported general semantic reasoning or physical-world benefit is claimed.

Reproduce and inspect using `P2N_START_HERE.md` and `docs/components/spatial/P2N-T2-typed-ontology-structural-consistency.md` in the source archive. The new T2-specific backlog is `docs/components/spatial/C15-T2-external-reasoner-backlog-v1.json`.

Upstream standards: https://www.w3.org/TR/owl2-profiles/ ; optional independent mature OWL RL implementation: https://github.com/RDFLib/OWL-RL .