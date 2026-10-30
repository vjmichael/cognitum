# C15 T3 P2V — Dynamic scene robustness and validation readiness

**Status:** Offline Protobuf-native research adapter, synthetic/contract validated. It does not estimate camera ego-motion, solve visual occlusion, authenticate identities, certify calibration, or authorize navigation or scene writes.

## Architectural decision

P2Q already converts depth-camera axial observations into the declared world coordinate system. **Do not apply camera compensation twice.** P2V consumes P2U's already re-evaluated T1/T2/T3 world-frame hypotheses and performs an additional camera continuity, object reappearance and stale-static evidence audit. P2U is unmodified and remains the upper bound on evidence; P2V can **remove, never add** static claims.

- `proto/cognitum/spatial/v1/dynamic_scene_robustness.proto` (v1) has a single typed Protobuf request/result. `cognitum/spatial_dynamic_scene_robustness.py` provides `analyze` and deterministic `verify`.
- All 2–8 original P2U windows and their existing source hashes are independently rechecked, including P2T/P2S/P2R and P2Q calibration checks. Source hashes are not sensor attestation.
- The camera continuity contract assumes one camera frame namespace and a common world coordinate system, with a deliberately **single-camera clock**: same-tick different frames are rejected. Quaternion sign symmetry `q` and `-q` is respected. Translation and rotation step bounds are explicit heuristics, not estimated covariance or localization quality.
- If the declared camera pose jumps beyond the threshold, the P2V static handoff is completely withheld. A different camera `frame_id` or camera `calibration_source_ref` is rejected pending a separately verified registration/calibration review. No ungrounded extrapolation or rewarping.
- Every object candidate retains its original caller-supplied ID and all distinct supporting capture IDs. Absence is recorded as **missing unexplained**, not a positive occlusion claim; a long observation gap is **unverified reappearance**, not proven identity continuity.
- Voxels near missing/reappearing object last-known locations can be withheld by a caller-selected physical exclusion radius. P2V also rejects stale evidence based on the latest distinct P2S contributing frame tick, rather than the last window's evaluation tick alone.
- The emitted volume is a filtered copy of P2U's stationary hypothetical predictions. All evidence remains `PREDICTED`, and T2 `classify` still returns `CELL_UNKNOWN`.

## Bounds and security

- P2V serialized request maximum: 8 MB, up to 96 distinct depth captures; P2U's tighter upstream bounds remain in force.
- Camera translation and rotation thresholds must be finite, positive and bounded, static/missing/reappearance age thresholds finite positive integers, exclusion radius in [0, 20] metres.
- Unknown Protobuf fields, version mismatch, invalid scope, redefined captures, forged camera hashes, unregistered frames and output replay tampering fail closed.
- No persistent map writes, Lu authority, camera calibration assurance, navigation safety, actual object-ID verification or hardware integration.
- A moving camera with valid, trustworthy common-frame calibration can pass; P2V **does not itself establish** that calibration, ego-motion accuracy, or registration correctness.

## Reproduction

```bash
PYTHONPATH=. python -m pytest -q tests/test_c15_t3_p2v_dynamic_scene_robustness.py
PYTHONPATH=. python tools/verify_protobuf_schemas.py --require
PYTHONPATH=. python tools/run_c15_t3_p2v_demo.py
PYTHONPATH=. python -m pytest -q tests/test_c13* tests/test_c14* tests/test_c15*
```

## Deferred external tests

Real calibrated RGB-D/LiDAR sequences with camera ego-motion and moving-object identity ground truth are necessary to measure false-static rate, occlusion reappearance, registration integrity and latency. See `C15-T3-P2V-deferred-validation-backlog-v1.json`. Do not substitute MOT17 RGB videos for measured 3D depth/equivalent calibration.
