# Cognitum C15 — P0 Standards, Prior-Art and Research Gap Re-audit

**Date:** 2026-10-28  
**Type:** research-only amendment to the existing C15 P0; not an implementation or runtime milestone.  
**Code baseline inspected:** `/mnt/data/Cognitum_C15_T1_P2E_Real_Annotation_Pilot_work/docs/components/spatial/P0-expanded-compositional-physical-world-model-research.md` (existing T1–T8 roadmap).  
**Scope:** mathematical and algorithmic AI components, Protobuf-native internal contracts, independent scientific validation. No changes to Lu, NVP, GitHub or an application-specific simulator.  
**Standard terminology:** 'standard' below is explicitly either a formal published standard, a de-facto research baseline, or experimental prior art. These are not interchangeable. Sources were checked on 2026-10-28; this is a selective technical survey rather than a systematic literature review.

## Executive finding

C15's general direction—separating identity, part–whole semantics, spatial volumes, physical constraints and causal assumptions—is well motivated. Its original P0 was **not a complete survey of incumbent technology**. The principal omissions were: (1) probabilistic multi-target tracking and end-to-end / segmentation trackers; (2) data/evaluation standards and protocol pitfalls; (3) formal ontology and provenance semantics; (4) dynamic semantic scene graphs and factor-graph estimation; (5) different volumetric representations and their epistemic meaning; (6) large part/assembly datasets and physically articulated objects; and (7) strong contemporary learned object-centric challengers, including SAM 3/3D and modern slot-based approaches.

**Architectural decision:** retain T1–T8 and the P0/P1/P2/P3 lifecycle. Add comparison families and requirements *within* those tracks. Adopt mature external methods as independently verified comparators or optional adapters, not as mandatory proprietary core dependencies; do not reimplement large systems for the sake of owning them. Continue treating CAPS as a research requirement to evaluate for Zog Zoo, not as a prerequisite theorem for 3D intelligence.

## 1. Taxonomy of what exists

### T1 — Object identity, association and re-identification

**Classical multi-target state-estimation (foundational):** motion models and Kalman/extended/unscented filters, Hungarian or min-cost assignment, gated Mahalanobis matching, JPDA, MHT, and random-finite-set trackers such as PHD, LMB/GLMB, PMBM. These are *model families* rather than mutually interchangeable implementations; complexity, data association uncertainty, false detections, birth/death, and sensor assumptions differ. T1 P2B/P2C should be compared with at least one covariance-aware tracker and one multiple-hypothesis method before claims of improved uncertainty tracking.

**Tracking-by-detection baselines (widely adopted):** SORT (simple geometry), DeepSORT (appearance plus motion), ByteTrack (low-confidence detections), OC-SORT (observation-centric correction), BoT-SORT (camera motion and optionally ReID), StrongSORT, Deep OC-SORT, Hybrid-SORT. Use code pinned by commit and published detector inputs. It is misleading to rank methods across different detector confidences, frame preprocessing, model weights, or train/test conditions.

**Learned/end-to-end alternatives:** TrackFormer, MOTR/MOTRv2, MeMOTR and more recent track-query approaches. **Pixel-mask tracking** is a distinct task from box MOT: SAM 2, SAM 3/3.1, XMem and related video object segmentation methods should compete on mask-specific tests, not be forced into a box-only score. SAM 3.1 was announced March 2026. Open-vocabulary tracking is relevant if C15 is to handle novel object types. Multi-camera/3D tracking, persistent identities across sensors and global track reconciliation are additional challenge axes.

**Benchmarks:** MOTChallenge MOT16/17/20 (pedestrians), DanceTrack (similar appearance and changing motions), SportsMOT (fast-moving players), BDD100K (moving camera), TAO (long-tailed classes), and 3D benchmarks such as nuScenes/KITTI where relevant. TUD-Campus is only a small annotation-format smoke fixture, not a representative tracker ranking. Fair runs require genuine image frames, fixed detections, confidence scores, real extracted descriptors, identical sequences, and original baseline implementations.

**Evaluation:** TrackEval reference implementation: HOTA and its DetA/AssA/LocA decomposition, IDF1, MOTA and IDSW; identity recovery after varying occlusion lengths, fragmentation, false merges, and track births/deaths. Separate detection-quality errors from association errors and score calibration of declared identity confidence. Do not score a tracker on perfect ground-truth detection boxes as if it were an end-to-end real-video tracker. Mark public/private detections explicitly.

### T2 — Hierarchical composition, structured hypotheses and ontologies

**Formal standards:** W3C OWL 2 supports open-world ontological inference: absence of a fact does not imply falsity. W3C SHACL validates RDF against explicit shapes/constraints; it is not equivalent to OWL entailment. PROV-O expresses provenance claims, not evidence authenticity. Consider OWL 2 profiles (EL/QL/RL) for tractability. 'Part of', 'contained in', 'adjacent to', 'assembled from', 'functionally depends on' and 'shared by' are *different relations*, and ownership is not the same as a physical relation.

**Reference engines:** established reasoners e.g. HermiT, Pellet, ELK or a capable OWL library, and an independent SHACL validator. A typed property graph / NetworkX is adequate for deterministic graph tests but does not prove OWL semantics or open-world inference parity. The P2C probability model's priors/likelihoods must be evaluated against a C13 probabilistic baseline rather than labeled objectively calibrated.

**Dataset and evaluation baselines:** PartNet (hierarchical 3D parts), PartNet-Mobility (articulations, joints and object functions, access controlled), newer PartNeXt (2025; textures and fine-grained hierarchies), 3DSSG/3RScan (semantic 3D scene relations). Part segmentation IoU, relation precision/recall, assembly-completion correctness, shared-part consistency, open-world unknown-vs-absent error, cost and latency. Preserve multiple mutually incompatible structural hypotheses with evidence and revision lineage.

**Crucial semantic hazard:** asserting that a *class* of objects typically has a component (e.g. a building has walls) does **not** establish that an observed individual contains a particular hidden component at a known location. Class defaults, existential ontology assertions, learned priors and sensor-confirmed facts must remain separate.

### T3 — Volumetric occupancy and geometry

**Distinct representations to compare, not conflate:** occupancy log-odds (occupied/free/unknown), dense/sparse octrees, TSDF (surface distance near measured observations), ESDF (distance for spatial queries), SDF/UDF, polygon meshes, point clouds, CAD/CSG, voxel hashing, neural implicit fields (NeRF/SDF), and Gaussian splats. A photorealistic reconstructed view is not reliable evidence of watertight geometry or hidden anatomy; a TSDF zero crossing is not a full semantic interior model.

**Established engines:** OctoMap (probabilistic octree, explicit unknown state), UFOMap (explicit unknown space), Open3D (voxel block grid and TSDF integration), Voxblox (CPU TSDF/ESDF), nvblox (CUDA/GPU TSDF/ESDF), OpenVDB (sparse volumetric storage and operations). The current sparse ray update is a useful reference test, not an implementation of all these systems. Compare memory, discretization/resolution, update latency, ray traversal, correct unknown-state behavior, and temporal change handling.

**Data and scoring:** SemanticKITTI, Occ3D, OpenOccupancy for voxel occupancy/semantic occupancy; RGB-D/scene-reconstruction datasets for metric depth and surface quality when licenses permit; IoU/mIoU and per-class performance, Brier/log-score and reliability diagrams, surface Chamfer/F-score, free-space false positives, conservative unknown rates, collision-query validity. Report calibration separately for occupied and free hypotheses. Do not claim real-sensor calibration based on synthetic holdout labels.

**Key fusion issue:** repeated observations from one camera, derived pixels from the same image, or correlated sensor readings are not independent Bernoulli trials. A naive log-odds sum can become overconfident. Pose/registration uncertainty may be larger than occupancy uncertainty. Store frame/time/transform covariance, source lineage and correlation groups; test unmodeled pose drift and moving objects.

### T4/T5 — Material, physical, and structural plausibility

**Standard mathematical methods:** unit-aware geometric predicates, graph connectivity and topological constraints; collision/penetration checks; joint limits, kinematic chains, rigid bodies and articulated assemblies; finite-element/constitutive modeling and numerical solvers as external validators where justified. A constraint solver can certify **the declared model**, not certify the physical truth of its constitutive assumptions.

**Research and datasets:** PartNet-Mobility / SAPIEN for articulated objects, BEHAVIOR-1K / OmniGibson for object states, affordances and relations, HSSD/HM3D for coherent indoor scene layouts. Evaluate functional relation prediction, part accessibility, traversable cavity topology, collisions, impossible joint constraints and consistency of representations under deliberate stylization. These environments are test fixtures / optional research dependencies, not Cognitum features.

**Opportunity:** build a typed predicate taxonomy distinguishing geometric-valid, topological-valid, model-simulated, human-plausible, and physically-verified. Do not merge them into one 'makes sense' score.

### T6/T8 — World model, estimation, generalization and explanation

**Spatial state-estimation reference:** factor graphs and smoothing (GTSAM, Ceres-family optimizers), relative-pose/SLAM systems, and Hydra/Spark-DSG for *dynamic semantic scene graphs*. These couple observations, poses, map components, places, and objects. A hand-authored scene graph is not equivalent to a calibrated perception or SLAM stack.

**Data:** 3DSSG/3RScan, HM3DSem, HSSD, Habitat, and held-out compositional scenes. Evaluation should include pose ATE/RPE, topology/map correctness, unseen part combinations, novel viewpoints, simulated-to-observed residuals, uncertainty reliability, false structural certainties, provenance integrity, compute cost and failure rate. World-model improvements require held-out **prediction** quality, not only visual reconstructions.

### T7 — Capsules versus other learned object-centric representations

**Required challengers:** CAPS dynamic routing and matrix EM routing; Slot Attention and successor object-slot models; query-based segmentation, SAM 2 and 3/3.1; single-image 3D methods including SAM 3D; learned object-centric world models including Dyn-O (NeurIPS 2025). A fair benchmark must use comparable supervision, datasets, resolution, preprocessing, resources, real model outputs and held-out compositions. Slot methods can over-fragment objects; capsules can have routing cost and training stability problems. Do not infer from a rendered full-object reconstruction that hidden interior organs or support beams have been *observed*.

**CAPS specific hypotheses to preregister:** pose extrapolation, part–whole hierarchy recovery, long-occlusion identity recovery, open-world novelty detection, robustness to viewpoint change, and more efficient structured physical predictions at a fixed compute budget. Keep null-result and failure criteria explicit.

## 2. Normative vs de-facto comparison requirements

| Category | Source / method | Status | Applies to |
|---|---|---|---|
| Formal standard | W3C OWL 2 | Normative semantics | T2 ontology reasoning |
| Formal standard | W3C SHACL | Normative graph constraint validation | T2 structural validation |
| Formal standard | W3C PROV-O | Normative provenance vocabulary, not authentication | T1–T8 provenance |
| Formal standard | OGC GeoSPARQL 1.1 | Normative geospatial RDF query semantics; not a voxel engine | T2/T5 spatial predicates |
| Domain convention | ROS REP-103 | Published active robotics coordinate/unit convention | T1/T3 transforms |
| De-facto reference | TrackEval | Official evaluation implementation | T1 metrics |
| De-facto library | OctoMap / Open3D / OpenVDB | Established algorithms + data structures, different semantics | T3 |
| De-facto library | Hydra/Spark-DSG / GTSAM | Semantic spatial graphs / factor graph estimation | T6/T8 |
| Research model | CAPS / SAM / object slots / Dyn-O | Experimental alternative architectures | T7 |

**Internal serialization:** retain Cognitum native Protobuf; do not convert the core to RDF/OWL or ROS messages. Implement dedicated adapters and compare semantic outputs against a standards-compliant reference. Metadata must include units, handedness, camera/world frames, time bases, covariance, confidence calibration lineage, hash/provenance, version, and unknown/not-measured semantics.

## 3. Previously under-specified cross-cutting research questions

1. **Open-world vs closed-world knowledge.** 'Not known to contain a pipe' != 'known not to contain a pipe'. OWL open-world inference, SHACL validation, and occupancy unknown states require different logic. Encode explicit epistemic state and known negatives.
2. **Data association as uncertain evidence.** Correct-looking IDs from single-frame matching can still be physically wrong. Compare single-best matching, JPDA-like association and multiple-hypothesis tracking, scoring probability calibration as well as top-1 identity.
3. **Correlated sensor evidence.** Never multiply correlated appearance/occupancy likelihoods as if independent. Identify sensor, observation and derivative provenance families.
4. **Coordinate frame confidence.** Store SE(3) transform covariance or bounded uncertainty and verify clock/pose registration across time. A precise voxel map in a misregistered frame is not accurate.
5. **Dynamic maps and nonstationarity.** Distinguish static geometry, dynamic occupancy, decayed/stale evidence and persistent object identity. Test moving walls/doors, repeated view-dependent appearances and construction/demolition.
6. **Metric selection.** Use official TrackEval and specialized voxel/scene metrics. A private diagnostic score may be useful but cannot inherit the meaning of HOTA/IDF1 without reference parity.
7. **Learned priors vs observations.** One image may generate a plausible 3D mesh, but it does not observe internal volumes. General biological or architectural knowledge must be tagged as class prior or hypothesis, not individual verified structure.
8. **Domain shift / adversarial calibration.** Synthetic clean fixtures cannot establish real-camera, medical or structural reliability. Report complete abstention/failed-run rates and calibration intervals.
9. **Licensing and provenance.** Track individual dataset terms and pretrained weights; some research downloads require application/approval or noncommercial licenses. Code availability != unrestricted model-weight or dataset rights.
10. **Resource constraints and modularity.** Benchmark CPU costs, VRAM, latency and energy only when metered. External engines belong in optional, versioned research workers; leave Lu and consumer apps out of C15.

## 4. Recommended research sequence (does not reset completed milestones)

**P0R-1 (highest priority): freeze a benchmark manifest.** Define benchmark input schema for frames/detections/ID features, provenance and ground-truth binding; record task type: box MOT vs mask tracking vs 3D identity; select reference TrackEval and pin verified commits of SORT/DeepSORT/ByteTrack/OC-SORT/BoT-SORT/Deep OC-SORT plus a query-based model. Standardize metrics and identical detections. Do not claim completed original-tracker comparison until actually run.

**P0R-2: structural semantics parity.** Pair T2 part-graph fixtures with an independent OWL 2 reasoner and SHACL validator; distinguish open-world unknown from explicit absent. Acquire permitted PartNet/PartNeXt subsets with unobserved parts withheld at inference. Test that a class-level prior cannot become an asserted instance-level hidden component.

**P0R-3: volumetric method parity.** Compare the T3 occupancy reference to OctoMap; compare TSDF to Open3D; compare sparse storage to OpenVDB separately. Implement no more minimal reference code than needed for reproducible parity and interrogable results. Test correlated observations, sensor-model calibration, partial views, frame misregistration and unknown/cavity discrimination.

**P0R-4: geometry/scene baselines.** Add 3DSSG/Hydra-style dynamic scene graph questions and GTSAM reference poses. Check cross-frame identity and part/volume consistency with fully specified coordinate conventions.

**P0R-5: learning ablations.** CAPS vs slot/segmentation/object-centric learned baseline; optional SAM 3/3D with verified accessible weights. Compare object/part discovery, geometric/functional plausibility and long-horizon prediction; exclude invented 'real-world efficacy' scores.

**P0R-6: transition to T4/T5 and C16.** Only after structural and volumetric epistemics have competent independent baselines, test declarative materials/constraints and prediction-error feedback. A simulator remains an independent specialist worker, not a property of a scene graph.

## 5. Gate matrix (status at P0 re-audit)

| Gate | Status | Required proof |
|---|---|---|
| Existing C15 T1 identity reference and synthetic tests | Implemented in prior checkpoints | Existing source/test evidence, not re-run for this document |
| TUD-Campus annotated diagnostic | Completed earlier | Real annotation-derived fixture; not original DeepSORT/ByteTrack result |
| Original trackers on identical real video/detections | **OPEN** | Frames, detector scores, trained features as applicable, pinned implementations, TrackEval |
| Official HOTA/IDF1 parity | **OPEN** | Run official TrackEval against same outputs |
| OWL reasoner + SHACL parity | **OPEN** | Genuine external engines, validated unknown/absence semantics |
| PartNet/PartNeXt held-out parts | **OPEN** | Licensed actual data, split and metric protocol |
| OctoMap/Open3D/OpenVDB parity | **OPEN** | Compiled genuine engines and pinned fixtures |
| Real occupancy sensor calibration | **OPEN** | Independent real measurements and pose uncertainty |
| Learned CAPS vs slots/SAM/other models | **OPEN** | Actual weights, comparable training/inference, held-out benchmarks |
| Real-world and physical-action authority | **OUT OF SCOPE** | Separate host/security/domain validation, not C15 research |

## 6. Primary research and standard sources

**Multi-object tracking:**
- TrackEval reference: https://github.com/JonathonLuiten/TrackEval
- MOTChallenge single-camera benchmark: https://link.springer.com/article/10.1007/s11263-020-01393-0
- 2025 tracking review (TBD vs end-to-end): https://link.springer.com/article/10.1007/s10462-025-11212-y
- SAM 3.1 official release (2026): https://ai.meta.com/blog/segment-anything-model-3/

**Composition and formal semantics:**
- OWL 2: https://www.w3.org/TR/owl-overview/
- SHACL: https://www.w3.org/TR/shacl/
- PROV-O: https://www.w3.org/TR/prov-o/
- OGC GeoSPARQL: https://www.ogc.org/standards/geosparql/
- PartNet: https://partnet.cs.stanford.edu/
- PartNet-Mobility / access requirements: https://huggingface.co/datasets/sapien-sim/PartNetMobility
- PartNeXt (NeurIPS 2025): https://proceedings.nips.cc/paper_files/paper/2025/hash/579636b69390b41fa2d39b744593bfbe-Abstract-Datasets_and_Benchmarks_Track.html
- 3DSSG: https://3dssg.github.io/

**Volumes, state and mapping:**
- OctoMap: https://octomap.github.io/octomap/doc/index
- UFOMap: https://github.com/UnknownFreeOccupied/ufomap
- Open3D TSDF: https://www.open3d.org/docs/latest/tutorial/t_reconstruction_system/integration.html
- OpenVDB: https://www.openvdb.org/documentation/doxygen/
- nvblox: https://github.com/nvidia-isaac/nvblox
- GTSAM: https://gtsam.org/
- Hydra: https://github.com/MIT-SPARK/Hydra
- ROS REP-103: https://reps.openrobotics.org/rep-0103/

**Learning, prediction and validation:**
- Slot Attention: https://research.google/pubs/object-centric-learning-with-slot-attention/
- SAM 3D (CVPR 2026): https://openaccess.thecvf.com/content/CVPR2026/html/Chen_SAM_3D_3Dfy_Anything_in_Images_CVPR_2026_paper.html
- Dyn-O (NeurIPS 2025): https://proceedings.nips.cc/paper_files/paper/2025/hash/b03b9ec80fc599bb5161746edff0f322-Abstract-Conference.html
- BEHAVIOR-1K: https://proceedings.mlr.press/v205/li23a
- HM3DSem: https://aihabitat.org/datasets/hm3d-semantics/
- HSSD: https://3dlg-hcvc.github.io/hssd/

**Research conclusion:** many pieces of C15 are established science already. The legitimate open problem for Cognitum is the correct *composition and uncertainty-preserving interface* between identity, part/whole semantics, volumetric evidence, physical constraints, and predictive models, and whether a learned component improves validated performance at acceptable resource cost.
