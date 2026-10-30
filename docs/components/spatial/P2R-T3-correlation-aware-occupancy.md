# C15 T3 P2R — Correlation-aware research-only volume fusion

## Scope and ancestry

This is an **additive** offline research interface layered on P2Q's validated
rectified-pinhole projection, P2C's independent-ray temporal occupancy engine,
and T2's predicted-only voxel structural-audit path. **No Lu modifications**.

P2R uses an explicit `P2RFusionRequest` (Protobuf). Caller declares an
assumed `rho in [0,1]`; P2R does not measure or calibrate correlation.

## The correction

For voxel `v`, P2Q produces ray log-odds contributions `l_i =
exp(-dt*ln 2/half_life_ticks) * log(p_i/(1-p_i))`. P2C assumes independence
and sums these values, clamping log odds to `[-8,8]`.

P2R groups events **per voxel** by `(source_ref, depth_frame_sha256)` (without
`tick`, preventing replay of a claimed identical frame from gaining full
independent weight). For group `g` with `n_g` events and assumed equicorrelation
`rho`, P2R uses

`L_v(rho) = clamp(sum_g sum_{i in g} l_i/(1+(n_g-1)*rho), -8, 8)`.

This heuristic borrows an effective-sample-size factor from equicorrelation
under simplified assumptions; it is **not** a probabilistically calibrated
inverse sensor model, a general Bayesian observation model, or a sound claim
about arbitrary spatially correlated noise. Mixed-sign evidence retains its
conflict flag, and its cell is excluded from T2 handoff. Other correlated
sources can still be counted independently because their provenance keys differ.

For every cell P2R reports independent baseline, adjusted value, group count,
largest repeated group, conflict flag and a **five-point sensitivity grid**
`rho = {0,.25,.5,.75,1}`. The reported min/max refer to these five tested
settings; they are **not** confidence/credible intervals nor guaranteed extrema
for arbitrary continuous correlation. At `rho=0`, the result must match the
existing P2C baseline (hard gate).

P2R includes the unmodified P2Q result as explicitly labeled **baseline**,
plus a **distinct** P2R hypothetical `VolumeGrid` using only
`VOLUME_PREDICTED_OCCUPIED` or `VOLUME_PREDICTED_FREE`. No measured/verified
geometry is emitted, and any T2 structural claim remains indeterminate.

## Data and authorization limits

- Camera geometry and depth are caller-supplied and not measured here.
- Depth-frame SHA-256 is a caller claim; no raw pixel-byte attestation.
- There is no host lease or source-owner authentication. Cross-sensor and
  cross-frame correlation is not solved.
- Unknown wire fields, malformed camera geometry, unauthorized modes, invalid
  rho and mismatched P2Q replay are rejected.
- Explicit resource bounds include P2Q's depth/voxel caps and P2R request size.
- No canonical scene mutation, real-world mapping certification, or action
  authority; no Lu installation or GPU worker execution.

## Validation

Run from the packaged Cognitum root:

```bash
PYTHONPATH=. python -m pytest -q tests/test_c15_t3_p2r_correlated_fusion.py
PYTHONPATH=. python tools/run_c15_t3_p2r_demo.py
PYTHONPATH=. python -m pytest -q tests/test_c13* tests/test_c14* tests/test_c15*
PYTHONPATH=. python -m pytest -q tests/test_c07*
PYTHONPATH=. python tools/verify_protobuf_schemas.py --require
```

Real-world confidence, independent OctoMap and OpenVDB parity, correlated
frame statistics, and Windows Lu security gates stay deferred and separate.
