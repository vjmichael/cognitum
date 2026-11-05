# Cognitum C15 T3 P2U — Dynamic scene mapping

**Status:** Offline research engineering checkpoint; production / real-sensor accuracy not accepted. Date: 2026-10-29 (UTC archive date).

## Delivered

- Opt-in `dynamic_scene_mapping.proto` contract, compiled `spatial_dynamic_scene_mapping_pb2.py`, deterministic research-only mapper and replay verifier.
- Dynamic/static partition, paired-motion re-entry hypotheses, tentative/persistent/dormant/retired life cycle and bounded sticky dynamic-cell guard.
- Strict conversation / volume / scene / voxel-grid boundary; no canonical writes or host authority.
- Repeated capture hashes are verified and cannot be reassigned; each window needs fresh depth evidence. Static per-cell streaks require new supporting captures; motion links require new destination captures.
- T2 receives only hypotheses. No tested path can promote predicted voxels to certified measured cells.

## Synthetic demonstration (not measured mapping accuracy)

- Unique depth captures: **10**; motion hypotheses: **1**; persistent object state: **P2U_PERSISTENT**.
- Dynamic voxel candidates: **2**; predicted stationary cells: **12**; unresolved cells: **4**.
- Two windows of 5 calibrated synthetic captures, with caller-asserted object identity. Fully deterministic replay, no claimed physical truth.

## Verification (Linux environment, selected tests only)

- `PYTHONPATH=. python -m pytest -q tests/test_c15* tests/test_c13* tests/test_c14*`: **1,311 passed, 39 skipped, 567 subtests passed**, 5 unrelated warnings.
- C07: **218 passed, 71 subtests passed**.
- Focused P2U: **15 passed** (already counted in selected C15 suite).
- Independently compiled **70/70** `.proto` schemas and compared Python bindings.
- P2T archival source comparison: **774 files present**, with exactly one intended prior-source modification (`tools/check_proto_descriptors.py`).
- Archive manifest and clean-extraction test recorded separately.

## Limitations / research debt

These observations are caller assertions; hashes do **not** authenticate cameras or people. "Persistent" means the same asserted object ID has motion candidates in at least two fresh windows, not a validated identity. Static occupancy is a predicted set, **not a safe navigation map**. No real sensor footage, external OctoMap/OpenVDB parity, camera ego-motion, production host security, or bounded long-stream latency measured.

The five additional deferred tests are in `C15-T3-P2U-deferred-validation-backlog-v1.json`. All P2T and earlier T2/T3 and tracking benchmark records remain unchanged. No changes to Lu or GitHub.