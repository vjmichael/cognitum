# Cognitum C15 T4 P4 — source-byte integrity and split-locked evaluation

**Date:** 2026-10-29. **Status:** portable, offline research-only reference implementation. **No Lu changes or physical action authority.**

## Why this phase exists

P3 evaluated caller-asserted reference hashes, labels and source identities, but its code did not require the actual reference bytes to match those assertions. P4 closes that local evidence-integrity gap without making the invalid leap from a hash match to laboratory authenticity.

## Added components

- `proto/cognitum/spatial/v1/functional_material_p4.proto` and generated `cognitum/proto/spatial_functional_material_p4_pb2.py`: new additive typed Protobuf envelope, bounded untrusted reference-blob receipts and no-authority results. P0/P1/P2/P3 contracts unchanged.
- `cognitum/spatial_functional_material_p4.py`: validates an exact SHA-256 match for *each* reference observation payload; exact JSON field types, immutable declared labels/units/specimen IDs, duplicates, valid numeric observations, source identity, bounded payloads, and strict calibration/holdout assignments against caller-supplied plan bytes. Only then invokes P3, retaining its independent scenario calculations, false-positive/false-negative/abstention/Wilson diagnostics and reference reuse checks.
- `evals/c15_t4_p4_synthetic_evidence_intake.py`: 80 fixed synthetic specimens imported from P3, each assigned a synthetic reference payload, compared with the separately declared P2 conditional inputs, plus tamper/partition-swap negative controls.
- `tests/test_c15_t4_p4_evidence_gate.py`: 31 new tests covering valid and malformed Proto/JSON/plan inputs, exact hash/label/units, group and partition mismatch, unchanged numerical results and authorization denial.

### Trust and measurement boundaries

**Critical:** A locally calculated SHA-256 over caller-supplied bytes proves only that the supplied bytes match the supplied digest. It does NOT prove an original lab instrument produced them, a document license permits use, a sample group is independent, or that the plan was preregistered before observations. Likewise, a `calibration_record_ref` is an assertion, not third-party calibration evidence. P4 accurately returns `source_authenticity_verified=false`, `preregistration_verified=false` and `independent_measurement_verified=false` even for syntactically valid LAB claims. The plan hash binds bytes internally; its creation time is not independently attested. There is no fetching, disk write, untrusted code execution, host service, Lu integration, physical actuation, or certification.

All evidence source IDs are strict short identifiers, **not arbitrary network URLs**; references must be imported by a separate, explicitly authorized provenance system in a later phase. The supplied JSON reference schema is exact: `schema_version`, `case_id`, `specimen_group_id`, `partition`, `observed_class`, `unit`, and optional `observed_clearance_m`; units are `m` for numeric clearance and `not_applicable` otherwise. A frozen plan declares `plan_version=1`, `study_id`, `conversation_id`, `model_id=C15_T4_P2`, `reference_format=C15_T4_P4_OBSERVATION_V1`, and an exhaustive `case_partitions` map.

## Verification

- **31/31 P4 focused tests passed** on Linux research environment.
- **141 selected T4 tests passed**, 7 subtests passed (including P1/P2/P3).
- **262 selected T4/T3/C07/C13/C14 tests passed**, 1 Windows-only skipped and 7 subtests passed. Not a complete repository sweep.
- **79/79** Protobuf source/binding wire-shape comparisons passed using independent protoc 3.13.0.
- **80 fixed synthetic cases** reproduced P3's 5/35 calibration vs 15/35 holdout selective disagreement. Deliberate payload alteration failed with `REFERENCE_CONTENT_HASH_MISMATCH`; deliberate split change failed with `PLAN_PARTITION_MISMATCH`.

## T3 status update from actual Windows 11 VM evidence

After P3 was archived, the user completed real Windows x86-64 VirtualBox experiments. The independent witness detected guest sequence 0 against host sequence 1; on the separate hard-off scenario, the guest replay returned `REBOOT_AND_FULL_REPLAY_PASS`, `CLEAN`, and host `MATCH` at sequence 1. A preceding VirtualBox log independently recorded the operator-requested `POWERING_OFF` → `OFF` state transition. This **closes the experimental VM gates** for that specific environment. It does **not** verify production independent authority, physical disk-controller power removal or native Lu integration. Original P3 checkpoint historical DEFERRED field intentionally remains unchanged; consult the separate final T3 report for provenance.

## Open gates

1. Licensed independently sourced real engineering specimen observations with instrument calibration evidence, reviewer adjudication, source custody and hash-based reproducibility.
2. External preregistration signature/time attestations and authenticated source identities (not present in P4).
3. Nonlinear FEA/material/buckling/thermal/collision model parity with real independent references.
4. Stratified errors and domain-dependent coverage intervals under scientifically justified sampling, not the deliberate fault injection in this synthetic fixture.
5. Matched Cognitum on/off Lu + LLM benchmarking only after an explicitly authorized integration and controlled quantization/resource setup.

**Do not promote P4's local hashes or synthetic test success into physical safety or task authorization.**
