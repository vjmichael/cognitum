# Cognitum C15 — T2/T3 P2A: structural/volumetric adversarial consistency

**Date:** 2026-10-28. Research-only, offline Python + native Protobuf specification, no change to Lu or GitHub.

## Objective

Compare *explicitly proposed* finite-index regions of parts or voids (T2's
part/whole graph) with T3's finite sparse occupancy-evidence grid, without
conflating a named part with a measured volume or treating empty/unobserved
space as an observed cavity. This is a sanity checker, not a digital twin,
sensor authenticator, medical model, building-code checker, physics simulator,
robotic navigation planner, or intervention controller.

## New module and contract

- `proto/cognitum/spatial/v1/structural_audit.proto` / generated binding
  `cognitum/proto/spatial_structural_audit_pb2.py`.
- `cognitum/spatial_structural_audit.py`: `audit(graph, volume_grid, request)`.
- Typed `StructuralSpatialClaim` gives a known graph `node_id`, explicit
  `SPATIAL_EXPECT_OCCUPIED` or `SPATIAL_EXPECT_FREE`, and **voxel-index box**.
  No assumption of continuous-world geometry, correct frame, or geometry
  derived from the node's label. Its source reference is caller supplied.
- Source validators for both original graphs and grids are executed before
  comparison; schema/scope matches, limited claims, area caps, bounds,
  duplicates, and typed expectations fail closed.
- For every region, the result counts reported supporting, contradicting,
  unresolved and internally conflicting cells. **Prediction-only data remains
  unresolved.** A partially observed region never passes as fully supported.
- Outcome is `CONSISTENT_WITH_CLAIMED_EVIDENCE`,
  `CONTRADICTED_BY_CLAIMED_EVIDENCE`, `MIXED`, or `INDETERMINATE`. Even
  `CONSISTENT` is **not** `VERIFIED_IN_REALITY`.
- Typed result is always `research_only=true`, `grants_authority=false`.
  It does not modify either input, and provides no bridge into an operating
  system, sensor, planning agent, or Lu permissions.

## Evidence-quality boundaries

The T3 `VOLUME_MEASURED_*` types are **caller-asserted measurements, not
independently authenticated sensor measurements**. T2's `EVIDENCE_OBSERVED`
label has the same limitation. Reported source identifiers/hashes cannot
certify actual collection or calibrate a sensor. This module does not estimate
P(occupied), perform ray tracing, check measurement independence, register
coordinate frames, detect spoofed sensor identities, or infer anatomical/
mechanical structures from visual appearances.

This deliberately follows the established modeling separation seen in
OctoMap (occupied/free/unknown) and part-whole ontologies, without porting
OctoMap's probability fusion or declaring the proposed structure grounded.
Research references:
- https://octomap.github.io/
- https://www.w3.org/wiki/PartWhole
- https://www.openvdb.org/documentation/doxygen/overview.html

## Verification

- `PYTHONPATH=. pytest -q tests/test_c15_*` — 154 passed and eight subtests.
- 600 deterministic seeded trials with an **independent per-cell oracle**:
  all classifications and counts agreed. This tests software arithmetic,
  not real-world accuracy or independence of generators.
- Selected `tests/test_c13* tests/test_c14*`: 754 passed, 39 optional skips.
- 56/56 independent `protoc --descriptor_set_out` source definitions matched
  checked-in Python descriptors (including proto3-optional compiler support).
- Focused negative testing: contradictory sensors, partial observations,
  unknown and predicted-only regions, arbitrary source claims, two mutually
  exclusive claims, duplicate IDs, oversized regions, absent box, tampered
  underlying graphs, missing node and cross-conversation scoping.
- An earlier per-file Protobuf sweep exceeded the execution limit. It was
  **not** counted as a pass. The successful check used a single compile batch
  and one in-memory independent comparison of every descriptor.

## Current limitations / next research milestones

1. **T2 P2B:** Validate richer mereology (shared parts, functional assemblies,
   incomplete topologies) without imposing erroneous single-parent ontology
   restrictions universally; benchmark reasoning against OWL/graph approaches.
2. **T3 P2B:** Validate source calibration, ray-based inverse sensor models,
   free/unknown handling, time-consistency and sparse/multiresolution storage
   against established octree/voxel baselines. Retain epistemic uncertainty.
3. **T2/T3 P2C:** Registered coordinate frames, aligned region geometry,
   evidence signatures, and independently evaluated sensor provenance. No
   absolute physical safety claim without domain certification.
4. **T1 P2D:** Original DeepSORT/ByteTrack with real annotated frames and
   trustworthy appearance features **not executed**, official scores OPEN.
5. CAPS experiments, real perception, sim-to-real trials and real LLM
   augmentation benchmarking remain deferred/unperformed.

Do not promote a consistency finding into a structural safety assessment,
clinical conclusion, pathfinding clearance, or authority to act.
