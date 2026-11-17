# P20 — Cognitum grounded world model and believable acting objectives

Date: 2026-11-01 (America/Phoenix). Research-only, Linux-only. No Lu edits, Windows/P15 remain deferred.

## Owner-approved long-range objectives

1. **Physical-world understanding:** durable object identity, part-whole composition behind surfaces, space, motion, materials, causality, uncertainty, consequences, and grounded predictions. A visible surface does not prove an object's interior. Hollow or unknown internals are legitimate.
2. **Believable character performance:** use screenplay as narrative blueprint; retain characters' objectives, subtext and continuity; recommend editable alternate takes in a persistent physically consistent NVP 3D scene, with separate voice and facial/body animation engines. Never apply automatic emotional stereotypes such as smiling by default. The human director approves the performance.

NVP is an initial demanding use case, **not a permanent Cognitum restriction**. HDC/KAN/SSM remain separately trainable or replaceable for other applications. Retain Cognitum/Lu separation and authorization boundaries.

## P20 local research outcome

The local P20 package adds research-only **world_grounding_p20.py** (synthetic authoritative entity vs limited observation, unknown interiors, coarse AABB path collision, idealized response+braking distance, explicit-director constraints and human-review-only acting checks), **grounded_curriculum_p20.py** (deterministic family-disjoint data generator with input/oracle separation), plus tests and 70 synthetic train/validation/test cases.

Focused validation: **19 passed, 1 deliberate ZIP duplicate-entry warning** in P19's bad-checkpoint test. This is NOT model training, physical-safety validation, professional acting evaluation, full regression, or live cgroup certification.

P19's unordered token-bundle HDC produces identical vectors for identical unordered role words; P20 adds an explicit role-swap failure test and a role-qualified token roundtrip. No valid claim of general relational reasoning or open-domain world perception follows.

## Planned learning gates

- **P21 HDC:** role-sensitive object/part and evidence/provenance relations, benchmark on unseen scene families and role-swapped facts, no confident fabrication of hidden parts or authority escalation.
- **P22 KAN:** numerical dynamics approximation benchmarked against exact physics and conventional baselines, out-of-domain refusal and worst-case error; no learned safety controller.
- **P23 SSM:** temporal object state, occlusion and movement prediction with chunk/reset/continuation equivalence and holdout lengths; authoritative state remains outside the model.
- **P24 Acting Coach/Voice Director:** script intent, subtext and continuity; licensed/consented acting data, explicit physical blocking, alternative takes and human director reviews. Vocal generation and animation are separate execution components.
- **P25 NVP integration:** persistent editable scene, script traceability, virtual camera and reproducible film/take assembly.

Predeclare scene/character split, withheld ground truth, baselines, abstention, human quality review and versioned model/data receipts. Do not promote on synthetic accuracy alone.

## Archive

Local tested overlay is **Cognitum_P20_Grounded_World_Acting_Curriculum_2026-11-01.zip**, SHA256 **4d6e63f0a80280ae037c51df2556d905b1b88febb3f41581d687005b2294a130**. Source and tests remain in the local overlay archive, not yet applied or merged to the GitHub branch.

Previous outstanding requirements (read-only cgroup mount, independent OS-supervised recovery, combined-suite lifecycle hang and C14 causal uncertainty) remain open.
