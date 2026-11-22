# Cognitum C15 — T3 P2R: Correlation-aware sparse volumetric fusion

**Milestone date:** 2026-10-28 (America/Phoenix)  
**Status:** Offline research implementation and smoke/regression checkpoint **PASS**. External calibration, physical sensor covariance, real-world occupancy accuracy, Windows host authority, OctoMap and OpenVDB parity **NOT VERIFIED**.

## Rationale

T3 P2Q previously provided a bounded pinhole-depth-to-ray-to-voxel bridge. Its existing P2C temporal occupancy engine assumes ray log-odds updates are conditionally independent, even when multiple pixel rays share a declared frame. P2R is a separate additive evaluator, preserving P2Q's independent baseline and introducing *explicit* user-provided within-frame correlation sensitivity.

The user requested continuation of T3 P2Q; since P2Q was already complete and archived, the next milestone P2R was implemented rather than redoing P2Q.

## Implemented

- `proto/cognitum/spatial/v1/correlated_fusion.proto` and compiler-derived Python descriptor.
- `cognitum/spatial_correlated_fusion.py`: validates research flag, bounded input, rho `[0,1]`, unknown-field rejection, exact provenance binding to validated P2Q rays, independent baseline parity at `rho=0`, derived voxel counts, and predicted-only T2 volume.
- Per-voxel event groups `(caller_source_ref, caller_frame_sha256)`. Exact same hash replay across timestamps is correlated rather than silently treated independent.
- Transparent equicorrelation **heuristic** `sum(logodds_i)/(1+(n_g-1)*rho)`, applied per shared-image group, with P2C temporal decay retained. Five tabulated sensitivity settings (0, .25, .5, .75, 1) and no false confidence-interval claims.
- Read-only verification that recomputes every result, SHA-256 claim binding, malicious/tampered result rejection, no canonical mutations.
- Correlated and conflicting cells remain tentative. T2 sees only `VOLUME_PREDICTED_*` rather than measured occupancy.
- Reproducible CPU-only synthetic study, adversarial tests and separate deferred-experiment backlog.

## Synthetic two-ray study

For overlapping free-space rays with `hit_probability=.8`, `free_probability=.3` and all samples from the same caller-asserted frame hash, occupancy probabilities are:

| Assumed rho | Independent baseline | Correlation-adjusted |
|---:|---:|---:|
| 0.00 | 0.155172 | 0.155172 |
| 0.25 | 0.155172 | 0.204944 |
| 0.50 | 0.155172 | 0.244211 |
| 0.75 | 0.155172 | 0.275211 |
| 1.00 | 0.155172 | 0.300000 |

The shift reduces overconfident **free**-cell inference for repeated correlated observations; it is **not** an accuracy estimate. Independent frames and sources still may be correlated, and the chosen correlation factor is not authenticated or learned. The five-point range is *not* a confidence/credible interval.

## Verification provenance

- `pytest tests/test_c15_t3_p2r_correlated_fusion.py`: **18 passed**; includes an additional 48 randomized independent numeric-oracle checks inside a test.
- `pytest tests/test_c13* tests/test_c14* tests/test_c15*`: **1,254 passed, 39 skipped, 567 additional subtests passed**, 5 warnings. Selected suite; unrestricted repository not run.
- `pytest tests/test_c07*`: **218 passed, 71 additional subtests passed**.
- `verify_protobuf_schemas.py --require`: **67/67** independently compiled/compared using Torch's vendored `protoc`.
- Clean-extraction focused cross-component tests: **90 passed, 8 additional subtests passed**.
- ZIP CRC passes; **753 source-file SHA-256 hashes match** after clean extraction.
- Previous tracking, T2 and T3 P2Q backlog files remain **byte-for-byte unchanged**. Three P2R-specific external validation experiments were added.

## Limitations

No real camera has been used. Camera calibration, frame hashes, source ownership and correlation values are caller assertions, not attested. The heuristic is not a valid probabilistic fusion law under arbitrary nonuniform spatial correlation or sensor bias. P2Q's output included as baseline is still an independent-model prediction; only the separate P2R volume is adjusted. No Lu-native host permission lease or Windows validation was run. No real dataset/OctoMap/OpenVDB benchmark is claimed. Previous negative identity-tracker results remain unchanged.

## Files and reproducibility

- Source archive: `Cognitum_C15_T3_P2R_Correlated_Volume_2026-10-28.zip`.
- SHA-256 source manifest: `P2R_SHA256SUMS.json` inside archive.
- Synthetic study: `Cognitum_C15_T3_P2R_Synthetic_Study_2026-10-28.json`.
- Benchmark backlog: `Cognitum_C15_T3_P2R_Benchmark_Backlog_2026-10-28.json`.
- Source patch: `Cognitum_C15_T3_P2R_Changes_2026-10-28.patch`.
- Entry point: `P2R_START_HERE.md`.

**No Lu, Jan, GitHub or original dataset modifications.**