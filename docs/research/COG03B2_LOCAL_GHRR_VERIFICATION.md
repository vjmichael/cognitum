# COG-03B2 — GHRR matrix algebra and flattened inference, local evidence (2026-11-17)

Owner directed B2 development ahead of B1 integration. Exact branch base `d5f90f34a0826494f9fa3f29674828a5f378352d`: B1 files not in Git tree, prior candidate archive intact. B2 developed against unchanged local B1 source, not a second production engine. No runtime publication, CI or canonical source changes; group B1 and B2 only after remaining B1 survey operations and source/admission/test harness integration are ready. FHRR remains the initial compositional hypothesis; GHRR optional specialist.

## Mathematical fidelity and implementation
Reviewed primary [GHRR revised May 2026](https://arxiv.org/html/2405.09689v2), sec III–IV and [flattened inference November 12](https://arxiv.org/html/2611.16363v1), sec 2.4–2.6. The independent NumPy implementation supports U(m) blocks (Haar QR with phase correction), ordered block-matrix multiplication, unitary adjoint and explicitly left/right unbinding, additive bundles (not assumed unitary), block permutation, Q times diagonal exp(i theta x) encoding, fixed trace normalization and separately norm-normalized cosine. Fixed inner product and cosine equal on unit atoms, not generally on bundles. Flat real interleaved dot product exactly corresponds to real Frobenius inner product in exact arithmetic; actual native precision checked. Flat representation preserves scoring, not noncommutative binding by elementwise multiplication. Bounded dimension/width/precision/shape/finite operand checks; immutable resident bank storage copies and stable index ties. Reference complex128 and native complex64/128 paths, no native device or physical acceleration claim. Paper's training and accelerator experiments not reproduced. No automatic HDC routing.

## Actual isolated local verification
Python 3.13.5, NumPy 2.3.5, actual reviewed TorchHD 5.8.4 hash `734a2d4673af4418dd75908402c81d0221335bc96a9b8c07cfba4d86db6dd175`, original October 25 Zog Zoo archive. 121 unchanged B1 tests +58 new GHRR +17 historical native adapter =196 passed, no skips/failures. New tests include independent scalar-loop matrix product, trace and component inner product, adjoint sides, unitary rejection, identity, associativity, noncommuting Pauli matrices, scalar reduction against B1 FHRR, Q/Lambda direct matrix oracle/kernel, bundle magnitude/zero controls, native-precision bank scoring, deterministic ties and budget negatives. Full repository and native Windows not run.

## Ordered retrieval pilot
336 ordered triples of distinct symbols drawn from 8 atoms. Three seeds, three cells (D,m)=(32,2),(128,2),(32,4); 48 sampled queries per seed and noise level; 1728 total paired query cases, with four additive complex noise ratios 0,1,2,4 relative to encoded L2 norm. Same tuple IDs, different-dimensional noise arrays. No learning or generalization task. All three GHRR scoring implementations agree top-1 on every query; max score error 1.1921e-6. Direct contraction included so the comparison does not credit avoidance of unnecessary full product solely to flattening. Single-thread Linux CPU; equal nominal D and equal retained atom+index array bytes, complex64; no full RSS per arm or physical power measurements. Exact known-tuple lookup is a strong different-information-contract clean baseline, not measured in this pilot.

Severest synthetic perturbation (ratio 4), each 144 sampled queries:
| D,m | GHRR correct | Positional FHRR equal D | Positional FHRR equal bytes | GHRR/equal-byte FHRR retained arrays |
|---|---:|---:|---:|---:|
| 32,2 | 124 | 18 | 120 | 352256 B |
| 128,2 | 144 | 120 | 144 | 1409024 B |
| 32,4 | 144 | 18 | 144 | 1409024 B |

Resident score latency, median of three seed medians in ms at ratio 4:
| D,m | naive matrix trace | direct contraction | flattened GHRR | equal-byte FHRR |
|---|---:|---:|---:|---:|
| 32,2 | 1.0875 | 0.0679 | 0.0239 | 0.0157 |
| 128,2 | 4.3814 | 0.2363 | 0.0633 | 0.0504 |
| 32,4 | 1.4645 | 0.2265 | 0.0624 | 0.0503 |

All methods recovered clean tuples in this pilot. Native flattened score 2.8–3.7x faster than direct Frobenius contraction on this workload; naive full trace significantly slower, not a strong optimized baseline. Equal-byte FHRR remained faster for resident scoring; GHRR only four additional correct severe-noise queries in first cell, ties in others. Equal-D comparison uses m² larger matrix storage and cannot establish intrinsic superiority. Timings exclude artificial noise generation, argmax, IPC and host verification; FHRR raw scoring path lacks the GHRR query validation overhead. Data are exploratory, not acceptance of superior accuracy, generic efficiency, hardware or reasoning. Need held-out topology and composition, equal whole-system budget, optimized fused paths, more seeds and independent exact/graph baselines in later C–G groups.

During pilot preparation fixed JSON serialization of NumPy integer counts and console summary scoping; final run exited normally; source hash verified against report. No arithmetic changes from those harness fixes.

## Artifact and exact source identities
COG-03B2_GHRR_Research_Candidate.zip, file ID `file_000000009c4c81fda9f0d70c10832666`, SHA256 `6353f16e6e5ad5795dca1b5a723176a4b7cc2cb0d82869a7a0bdf9f0fe418199`; original B1 source unchanged and archived original October 25 code included. CRC passed, manifest contains per-file SHA256 and Git blob hashes, actual test log, raw per-seed aggregate timings/counts and reproducible pilot source. Report SHA256 `50e59a0053dd9c4a939694d5d2f281567936ffe6331559d757e5d6ea20f9f1a8`.
- `cognitum/research/hdc_ghrr.py` — `1b05d98c87e9bacea9e8548b56261d7a30fb28b6`
- `tests/test_cog03b2_ghrr.py` — `5b6d867475d3551c20f7d91ed907cbd55a780901`
- `tools/cog03b2_ordered_retrieval.py` — `f55e806574c0e565ab9727418aa0e07dc3cec9f0`

## Next grouped engineering task
Finish B1 remaining survey representation semantics and integrate the locally tested B1 + B2 into the actual current source and grouped native acceptance harness. Preserve existing accepted gates and explicit missing-dependency failures in dedicated research suite rather than introducing mandatory experimental dependencies into production. Then COG-03C advanced encoders/capacity and compression. No COG-03B consolidated acceptance or production designation yet. All 85 research entries remain.
