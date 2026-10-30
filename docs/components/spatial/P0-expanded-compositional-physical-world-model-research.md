# C15 expanded research program: compositional, volumetric and structural world representations

**Decision:** 2026-10-28. **Scope:** reusable Cognitum AI components and their mathematical/scientific evaluation; **not** a film editor, physics engine, medical device, rescue robot, digital-twin platform, OpenUSD/IFC importer, or any modification to Lu. Zog Zoo / virtual-world native reasoning is a motivating **research use case**, not evidence of attained capability.  The phrase *Compositional Physical World Intelligence (CPWI)* below is a project label, not an established scientific result.

**Current evidence:** C15 P0/P1 implements bounded, in-memory, host-proposed scene IDs, right-handed coordinate-frame geometry, a typed Protobuf scene contract, deterministic updates and limited proximity/world-X relationships. No learned perception, volumetric inference, physical dynamics, capsule system, real observations, or real-model efficacy has been established. The C14 G15 model trial is explicitly DEFERRED / NOT RUN. P2A now adds adversarial **baseline tests** of this existing engine; it is not a complete P2 tracker.

## 1. Research question and precise cognitive objective

Can a compositional reasoning system distinguish **observed surface geometry**, **general class priors** (e.g. structures often have internal parts), **inferred hidden volumes** (e.g. unobserved spaces), **simulated physical outcomes**, and **verified measurements** in a way that enables accurate, inspectable reasoning under ambiguity, occlusion, and domain shift?

A building is neither a uniformly solid box nor an empty shell: occupied structure (walls, beams), cavities (rooms, shafts), material layers, utility systems and unobserved regions coexist. A human is not simply a surface mesh: anatomy has nested structures, but general anatomical facts never prove the specific anatomy of an unobserved individual. An artist may deliberately deform a fictional asset; the underlying spatial and functional consistency constraints still need explicit scope.

The target **research output** is not rendered images. It is a typed, provenance-bearing **world hypothesis** that distinguishes known occupied, known free, unknown and inferred regions, part/whole relations, material and causal assumptions, plus alternative hypotheses and testable predictions.

## 2. Separation of responsibilities

| Area | Cognitum owner | Deliverable; boundary |
|---|---|---|
| Durable scene entities and rigid frames | **C15** | Stable IDs, typed part graph, reference geometry; no authority for real actions |
| Volumes and unobserved interiors | **C15** | Bounded occupancy/SDF/solid/void abstractions with UNKNOWN rather than fabricated interiors |
| Visual object-centric learning / CAPS | **C15 experimental lane** | Learned pose and part/whole hypotheses; optional and judged against competent baselines |
| Uncertain beliefs over internal objects | **C13** | Priors, posteriors, alternatives, calibration, epistemic uncertainty |
| Intervention/counterfactual reasoning | **C14** | Assumption-labelled causal hypotheses; cannot infer causation from a plausible render |
| Dynamical laws / numerical integration | **C16** | Dimensioned physical models, solver diagnostics, model discrepancy, predictive test loop |
| Time-indexed state/dynamics encoding | **C17 / C07** | Temporal representation vs trusted canonical state/revision control |
| Route/constraint planning | **C11/C12** | Search/optimization over a proposed world model; not a physical-control stack |
| Mathematical kernels | **C05** | Rigid transforms, geometry predicates, numerical errors and units |
| Tool safety and externally trusted evidence | **C01/C02/C03/C04** | Typed outcomes, authorization owner separation, benchmarks and collector provenance |

Consumer applications (e.g. NVP, BIM, OpenUSD, clinical, robotics) are **external adapters** or future Lu domain modules. No dependency on those applications enters the C15 computational core. Cognitum Protobuf contracts stay internal; external encodings are boundary-only.

## 3. Formal representation hypotheses

Represent a world snapshot as **W = (V, E, T, G, B, P)**: object/part nodes V; typed relationships E (part-of, contains, connected-to, supports, occludes); time-indexed transforms T in SE(3) with explicit length/time units; geometry/volume G; evidence and beliefs B; provenance and policy scopes P. Each claim binds to a source and epoch, and receives one of **OBSERVED, VERIFIED, INFERRED, SIMULATED, UNKNOWN, CONTRADICTED**; these are provenance/evidence categories, **not** a single scalar truth probability.

Candidate volume states are **OCCUPIED**, **FREE**, **UNKNOWN**, plus optionally a separate **INFERRED_OCCUPIED/INFERRED_FREE** field. Avoid collapsing unknown to empty. A signed distance or occupancy grid encodes geometry; a scene graph encodes semantics; neither alone knows whether a beam is load bearing or where an organ lies. Uniform voxels require O(NxNyNz) memory; sparse grids/octrees and continuous neural fields trade compute, fidelity and interpretability. Store uncertainty and resolution/bounds alongside representations.

Part graph constraints: strict containment is acyclic; relationships such as connected-to or adjacent-to need not be acyclic. Multiple possible decompositions may coexist as hypotheses. Geometry validation: finite metric coordinates, normalized quaternions, coordinate-frame consistency, overlapping-solid rules conditional on material/intent, nonnegative physical quantities, explicit unknowns. A type label such as 'human' can cue an **anatomical prior**, not asserted individual organ locations.

Physical-model loop (research only): initial belief W_t and parameter posterior q(theta) → predict state under hypothetical action a with C16 solver → measure prediction residual and uncertainty → incorporate *authorized, provenance-linked* new observation → revise W_(t+1). A bad simulation, mismatched unit or out-of-distribution observation must reduce assurance rather than manufacture a confident policy. Simulation planning is not permission to enact a real-world action.

## 4. C15 research tracks (not a renaming of P0/P1/P2/P3)

The standard Cognitum lifecycle is preserved **for each track**: P0 survey + baseline specification; P1 reference implementation; P2 adversarial stress; P3 held-out benchmark and falsification. Individual track status is separate from the overall C15 P0–P3 label.

| Track | Scope | First competent baseline | Hard negative test | Current status |
|---|---|---|---|---|
| **T1 Identity and evidence continuity** | Occlusion, stale/cross-sensor claims, swap ambiguity, deletion, revision | Current P1 scene graph + conventional multi-object tracking (later, with data) | Two same-category objects cross; labels and nearest poses alone are insufficient | P1 built; P2A baseline tests begun |
| **T2 Hierarchical composition / mereology** | Nested parts, assemblies, contains/part-of, expected vs verified structure | Typed property graph with hand-authored, constrained relations | Wall/room/beam and human/tissue/organ: generic part prior mistaken for individual fact | P0 design |
| **T3 Volumetric epistemics** | solid/free/unknown, cavities, surface thickness, sampled occupancy, SDF | Dense/sparse occupancy, octrees, SDF and mesh predicates | Exterior-only object confidently declared hollow/solid | P0 design |
| **T4 Functional/material constraints** | connection, affordance, joint, stiffness and dimensional validity | Explicit constraint solving + unit-aware numerical kernels | False physical-validity claim based on attractive geometry | P0 design |
| **T5 Structural consistency metrics** | Part connectivity, navigable void topology, relative scale and deliberate fictional constraints | Invariant checkers / graph algorithms / geometry libraries | Inaccessible cavity, colliding components, impossible connection under declared rules | P0 design |
| **T6 Prediction and revision** | Quantified model discrepancy, multiple physical hypotheses, prediction error | C16 conventional ODE/rigid-body/invariant solvers + C13 uncertainty | Agreement with a simulator treated as empirical verification | P0 design; C16 dependency |
| **T7 CAPS and other learned object-centric models** | Learned pose, part–whole assignments, occlusion recovery | Conventional trackers and object-centric neural baselines (e.g. slot/object models) | Equal metrics but vastly higher memory and runtime; unstable routing | P0 research; models not run |
| **T8 Generalization and explanation** | Held-out compositions, domain shifts, human-inspectable structural reasons | Hand-specified graph/invariants, non-caps object-centric model | Ground-truth leakage, overconfident unseen interiors, evidence replay | P0 design |

### T1 P2: immediate next tests

- Probe source swaps, object-ID reuse/tombstones, late measurements, frame errors and cross-conversation replay against existing P1.
- **Known unsolved:** legitimate object re-identification across sensors, same-category identity swaps with valid IDs, confidence decay over long unobserved gaps, per-observation covariance, and restart/durable deletion. Do not score a guard on the first group as proof of solving the latter.
- Next T1 algorithm candidates: gated assignment with explicit measurement covariance (Mahalanobis distance), linear/Hungarian baseline, multi-hypothesis tracking, independent appearance cues where consented. Use time **seconds**, not arbitrary P1 ticks, for velocity constraints. No automatic identity admission, especially when hypotheses are ambiguous.

### T2 / T3 initial fixtures

Fixtures shall include **layered wall with enclosed room**, **pipe running inside wall**, **articulated mechanical assembly**, **generic body with anatomical parts but no specific patient observations**, **hollow fictional prop**, **solid fictional prop**, and **hidden compartment with no interior evidence**. Every fixture has ground truth for synthetic domains; the model sees only selected observations. Human inspection of generated assets remains a distinct downstream acceptance test, not proof of physical/clinical correctness.

## 5. Methods and literature to compare, not reinvent

**Mature/incumbent mathematical methods:** NetworkX graph algorithms / constrained DAG validation; NumPy/SciPy SE(3) transforms, optimization and numerical kernels; sparse voxel/octree data, finite geometric predicates, SDF/occupancy, and standard data-association algorithms. Build pure, minimal references only where they support audit and independent parity checks; do not build new physics, imaging, CAD or rendering engines.

**Research challengers:** CAPS dynamic routing (Sabour et al. 2017) and matrix EM routing (Hinton et al. 2018), learned object slots, object-centric dynamics (Dyn-O NeurIPS 2025), and probabilistic graphical 3D world models (3WM ICLR 2026). Capsules are a **required experiment in the Zog Zoo research hypothesis**, but **not** a proven necessary condition for 3D reasoning or a default dependency for all Cognitum installations. Routing overhead, limited pretrained assets, robustness and reproducible training cost must be measured. Surface/image reconstruction literature (2025 NIR survey) describes SDF/UDF/occupancy/NeRF as distinct geometry representations. Do not treat appearance-only neural rendering as structural ground truth.

**Bibliographic links, checked 2026-10-28:**

1. Sabour, Frosst & Hinton (2017), *Dynamic Routing Between Capsules*: https://arxiv.org/abs/1710.09829
2. Hinton, Sabour & Frosst (2018), *Matrix Capsules with EM Routing*: https://research.google/pubs/matrix-capsules-with-em-routing/
3. Haq et al. (2023), capsule-network limitations survey: https://doi.org/10.3390/make5030047
4. *A 3D Scene Graphs Survey* (forthcoming ARCRAS 2027, survey status as of review): https://research.google/pubs/a-3d-scene-graphs-survey-open-challenges-and-future-directions/
5. Zhang, Yu & Ren (2025), *Neural Implicit Representations for Multi-View Surface Reconstruction*: https://pubmed.ncbi.nlm.nih.gov/40560706/
6. Wang et al. (NeurIPS 2025), *Dyn-O*: https://papers.neurips.cc/paper_files/paper/2025/hash/b03b9ec80fc599bb5161746edff0f322-Abstract-Conference.html
7. Lee et al. (ICLR 2026), *Unified 3D Scene Understanding Through Physical World Modeling*: https://proceedings.iclr.cc/paper_files/paper/2026/hash/3e6c9a8f3863f0343bf5cbabf1f85ca6-Abstract-Conference.html
8. Venkatesh et al. (CVPR 2026), *Physical Object Understanding with a Physically Controllable World Model*: https://openaccess.thecvf.com/content/CVPR2026/html/Venkatesh_Physical_Object_Understanding_with_a_Physically_Controllable_World_Model_CVPR_2026_paper.html
9. Chen et al. (2025), *Compositional Physical Reasoning of Objects and Events From Videos*: https://pubmed.ncbi.nlm.nih.gov/40424100/
10. Annual Reviews (2025), *Scene Representations for Robotic Spatial Perception*: https://www.annualreviews.org/content/journals/10.1146/annurev-control-040423-030709

These references are technology comparators and hypotheses, not evidence Cognitum has reproduced their results.

## 6. Evaluation protocol and falsifiable gates

- **Data splits:** independent generated mechanisms and seeds; hidden interiors unknown at inference; held-out object combinations, altered camera frames, appearance perturbations and occlusion length; real-world images only with lawful permission and appropriate handling.
- **Metrics:** identity swaps (IDSW), association accuracy, false merger/split rates, missed unknown-state rate, geometry IoU/Chamfer/occupancy calibration where ground truth exists, part-graph precision/recall, structural-invariant violation rates, prediction error vs observation, interval coverage/calibration, explainability trace, throughput/latency, peak RAM/VRAM and measured energy only if instrumented.
- **Core comparators:** (A) explicit graph/geometry; (B) competent conventional tracking and occupancy methods; (C) CAPS; (D) non-CAPS object-centric model; and (E) mixed architectures only after isolated ablations. Equal supervision/data/hardware and training budgets; report failures and missing runtimes, not phantom gains.
- **Adversarial requirements:** no categorical individual-anatomy claim from species prior; no UNKNOWN→FREE inference without evidence; no action grants via geometry/simulation/identity metadata; no unreviewed cross-source identity reassignment; adversarial content in labels is inert; no cross-conversation evidence leakage.
- **No preset superiority:** improvement is a preregistered effect-size and uncertainty target for a defined task, not presumed. If CAPS does not beat strong non-CAPS baselines on held-out composition/occlusion per memory and energy budget, retain it as an optional research challenger rather than making it a required runtime component.
- **Independent checks:** exact analytic geometry; SciPy/NumPy comparison; independent topology/graph validator; fixture-reconstruction from hashes; blind human assessment of functional structure where appropriate; release provenance and versioned evidence.

## 7. Contracts planned, not yet shipped

No new runtime schema is claimed in this P0 expansion. Future Protobuf-native, source-specific types (proposal, subject to independent compiler checks): `SpatialPartGraph`, `PartRelation(kind, source, target, temporal_validity, evidence)`, `VolumeEvidence(cell_frame, resolution, state, provenance)`, `StructureHypothesis(assumptions, confidence, unresolved_parts)`, `PhysicalModelReference` (links to C16 without embedding its solver), `SpatialVerificationReport`, `IdentityHypothesisSet`, `GeometryConstraint`. Names are intentionally provisional. Source-scoped permissions, resource caps, privacy, deletion and user consent remain host-owned.

## 8. Dependencies, hardware and deliberate non-goals

- CPU-first: graph and geometry references, synthetic bounded volumes; NumPy/SciPy optional numerical parity. Compare sparse vs dense memory/time before adding GPU path. Learned CAPS/object-centric inference needs separately pinned weights/training data and may need GPU; measure transport/VRAM overhead.
- No direct camera, microphone, sensor, medical data, remote feed or robot controls; those belong to other authorized domains. No OpenUSD or asset exporter required in the Cognitum base. No guaranteed real-world physically accurate digital twin, clinical advice or rescue automation.
- Research code must not modify Lu. Existing C15 P1 scene invariants must remain backward-compatible. Native Protobuf remains the internal contract, and real Windows confinement, Lu authentication and C14 model comparisons stay open.

## 9. Go/no-go milestones

**Near-term:** finish T1 P2 identity/source ambiguity stress; write T2 part-graph schema proposal and exact-graph reference; T3 simple occupied/free/unknown volume fixtures and independent geometry parity. **Medium-term:** compare sparse representations, add explicit epistemic provenance, connect C13/C14/C16 only through bounded contracts. **Later:** CAPS vs competent tracker/object-centric challengers; held-out sim–observation revision loops; externally chosen asset or navigation tasks. No model or real-world efficacy claim until actual datasets and reproducible benchmarks exist.
