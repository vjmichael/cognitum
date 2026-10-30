# Cognitum C15 — T2 P2B / T3 P2B Research References

**Date:** 2026-10-28. Separate working copy of sealed T2/T3 P2A checkpoint. No changes to Lu, GitHub, or original archives. Research-only; no action authority.

## Objective and scope

Build **reusable mathematical AI components**, not a digital-asset tool, sensor system, robotics stack, medical advisor, structural engineer, digital twin, or navigation planner. Maintain the boundary between *caller assertions* (including claims marked observed) and independently authenticated measurements. There are no camera, LiDAR, OpenUSD, simulator, or Lu invocations here.

## T2 P2B — Assembly/mereology and functional requirements

New files: `proto/cognitum/spatial/v1/assembly.proto`, checked-in compiler-derived `cognitum/proto/assembly_pb2.py`, `cognitum/spatial_assembly.py`, and `tests/test_c15_t2_p2b_assembly.py`.

- **Multi-parent membership:** `part_id -> assembly_id` relations form a directed acyclic graph; a beam or shared utility may be a component of multiple assemblies. This is a separate model, not a mutation of P1's intentionally single-parent scene ontology.
- **Qualified evidence:** observed, inferred, and hypothetical claims each carry source references. Hypothetical membership is never promoted to admitted observed membership.
- **Open-world missing parts:** a required role with no reported parts produces `NOT_ESTABLISHED`, **not** `ABSENT`. Explicit reported absence has a distinct type and remains only a caller assertion; contradictory presence/absence yields `CONTRADICTION`.
- **Functional dependencies:** records sets of required roles and whether they are *claimed* to be present. It never attests load-bearing strength, performance, safety, biological function, or physical operability from mere presence.
- **Validation:** bounded nodes/edges, required source/scope fields, duplicate prevention, cycles, an observed relationship connected to a hypothetical object, unknown fields, and attempted authority promotion fail closed. Inputs remain immutable; results have `research_only=true` and `grants_authority=false`.

This is a bounded structural-claim reasoner and not a general OWL reasoner, quantitative structural engineering model, shared-ownership ontology, or machine-learned CAPS implementation.

## T3 P2B — Sparse inverse-sensor reference

New files: `proto/cognitum/spatial/v1/ray_occupancy.proto`, checked-in compiler-derived `cognitum/proto/ray_occupancy_pb2.py`, `cognitum/spatial_ray_occupancy.py`, and `tests/test_c15_t3_p2b_ray_occupancy.py`.

- Bounded voxel grid (index 0..127, metric resolution) with 3D DDA ray traversal. Interior cells crossed by a ray receive a free-space update. A ray returning a hit assigns the endpoint voxel an occupancy update; a no-hit ray treats the endpoint as free. Exact simultaneous grid-boundary crossings advance all axes, avoiding spurious cells touched only at an edge/corner.
- **Sparse:** only reported traversed/endpoint cells are retained. Unobserved space is absent from storage and remains epistemically **unknown**.
- Inverse sensor assumptions: one independent hit update contributes `log(p_hit/(1-p_hit))`; a free update contributes `log(p_free/(1-p_free))`. Summed log odds are clamped to `[-8,8]`; the parameters are **not estimated or calibrated** in this research prototype. Correlated evidence can overstate confidence.
- Identical `(source,tick,voxel)` evidence is deduplicated; incompatible same-source/same-tick updates are rejected. Conflicting readings from different sources are explicitly marked as conflicted even if the numeric log odds favor one state. Unknown Protobuf fields, zero-length rays, invalid probabilities, unbounded rays, invalid metadata, and authority claims are rejected.
- Sparse 2× and 4× **coarse summary blocks**, not an octree or OpenVDB implementation: a block is complete only when all its fine cells have been observed. Incomplete coarse blocks have no reported average occupancy probability. A complete block with mixed observed states is marked mixed. No hierarchical interpolation fabricates interior observations.
- Input and output contracts are versioned, research-only, conversation-scoped *claims*. A source label is not an authenticated sensor signature. No real sensor pose/frame registration, occlusion/visibility model, dynamic-world decay, ray measurement independence, or real-data accuracy is established.

## Existing technology / nonreinvention

- **OctoMap** offers mature probabilistic octree occupancy mapping, including occupied/free/unknown, free-ray traversal and log-odds; this work implements a small independent mathematical reference, not a replacement or performance comparison. https://octomap.github.io/ and https://github.com/OctoMap/octomap
- **OpenVDB** offers a mature sparse hierarchical volume and transforms; this prototype produces sparse cells and conservative summaries, without implementing VDB or its scale-dependent indexing. https://www.openvdb.org/documentation/doxygen/overview.html
- Conventional graph/ontology reasoners provide baselines for richer part–whole and functional knowledge; P2B is a purposefully bounded structure-audit reference, not a new general ontology standard.

## Deterministic experiments and scope of results

Run `PYTHONPATH=. python tools/run_c15_t2_t3_p2b_study.py` to regenerate `P2B-reproducible-study.json`.

- 240 assembly trials with an independent role-count oracle, including claimed presence, missing evidence, claimed absence and contradictions: **240/240 agreed**.
- 240 3D ray trials independently sampled at 7,001 points along each segment: **240/240 ray cell paths agreed**. Log-odds checks for the 2,086 affected cells also agreed with the independent mathematical formula.
- These are **synthetic, bounded arithmetic tests**, not statistically meaningful estimates of real-world accuracy. Numerical sampling is not a formal proof of ray traversal for all floating-point boundary cases.
- T2 P2B/T3 P2B unit tests cover cross-assembly parts, cycle rejection, functional claim nonpromotion, absence vs unknown, duplicate evidence, sparse completeness, invalid rays, conflict, provenance, unknown fields, and denial of action authority.

## Production and next-stage gates left open

1. **T2 P2C:** Ontology reasoner parity; uncertainty across competing assembly explanations; provenance and role schema validation; geometric registration of part claims.
2. **T3 P2C:** Actual calibrated sensor model, trustable acquisition path, time-aware correlated update model, dynamic-world decay, accurate frame registration, original OctoMap/OpenVDB parity and memory/latency comparisons.
3. Original **T1 DeepSORT/ByteTrack** on real annotated frames and genuine learned appearance features remains **unrun**; annotated metadata alone is not benchmark evidence.
4. Learned CAPS, physical simulation/real-world execution, native Windows containment, authenticated Lu integration, and deferred real LLM evaluations remain outside this milestone.

No output in this research package authorizes a physical intervention, a medical or structural claim, or an action in Lu.
