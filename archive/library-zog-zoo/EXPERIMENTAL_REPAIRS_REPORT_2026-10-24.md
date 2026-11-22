# Zog Zoo — Experimental HDC repairs and independent rerun

**Date:** 2026-10-24 (user local)  
**Status:** six experimental Python modules repaired or extended. Component-level CPU validation, **not production certification**.

## Executive findings

- **Original standard HDC modules remain intact.** Only `zogzoo_hdc/sdm.py`, `resonator.py`, `neuralhd.py`, `lowdisc.py`, `stochastic.py`, and `quantum.py` were changed. Each original has a byte-for-byte Library backup under `/Zog Zoo/Backups/2026-10-24_pre_experimental_repairs/`.
- **Verification:** 19/19 new strict regression tests passed, plus the existing Zog Zoo `selftest` 20/20. Five fresh independent seeds `[121711,121733,121757,121781,121793]`. 100 main results and 40 noisy-decoder result rows (each result row aggregates several queries/trials).
- **Principal measured improvement:** an **explicit pair-enumeration decoder** recovers three bound factors accurately on clean and synthetically noisy controlled problems. This is **not** a trained iterative resonator network, and its increasing query cost precludes treating it as a general fast solver.
- **Practical memory fixes:** SDM no longer overwrites unrelated associations due to unnormalized threshold comparisons; NeuralHD physically stores sliced dimensions; indexed-IID is a reproducible default when quasi-Monte Carlo (QMC) bit codebooks have undesirable correlations.
- **Hardware limitation:** All experiments were CPU-only. Nothing here demonstrates FPGA speed, energy advantage, or working quantum computation.

## 1. Resonator replacement: accurate but not inexpensive

The old `resonator_factor(..., max_iters=3)` greedily matched the composite directly against individual factors, discarded complex phase information along one path, and recovered under 5% of the tested complete three-factor sets. Its algorithm did not correspond to the mathematics of a product of three independently unknown factors.

The new path calls `factor_pair_search`: enumerate candidate pairs, bind each pair, unbind it from the composite, cleanup the third factor, then compare each reconstructed triple against the observed composite. Vocabulary is limited to at most 128 candidate vectors to avoid unbounded cubic search. The older heuristic remains for other `max_iters`, and `resonator_recover` is unchanged.

**Five-seed results at D=256, 16 candidate factors, 24 queries per seed per architecture (120 trials each):**

| Model | Old greedy exact set | New pair-search exact set | New mean query time |
|---|---:|---:|---:|
| BSC | 1.7% | **100%** | 2.25 ms |
| MAP | 0.8% | **100%** | 2.30 ms |
| HRR | 4.2% | **100%** | 9.43 ms |
| FHRR | 1.7% | **100%** | 1.56 ms |

**Larger bank: D=512, 48 candidate factors, 60 clean queries per architecture:** 100% for all four, with mean per-query cost BSC **40.2 ms**, MAP **39.4 ms**, HRR **116.0 ms**, FHRR **21.8 ms**. An additional 60 **noisy** queries per architecture were also all recovered correctly under the tested 15% component corruption (for HRR, a 0.15 mixture). Perturbation definitions vary by architecture; these aren't matched SNR tests.

**What this establishes:** precise recovery from *one clean/noisy bound triple*, when all three factors appear in a small known codebook. **Not tested:** unknown vocabulary factors, superposed triples with competing bindings, real language/scene inference, calibrated abstention, learned resonator convergence, or large V scaling. The new method is a bounded combinatorial decoder, not a general resonator-network breakthrough.

## 2. SDM update correctness

SDM remains a nearest-address array index, not a proven classic multi-address Kanerva Sparse Distributed Memory implementation. Corrections:

- `write(mode='update')` inserts into empty memory; uses **normalized** VSA similarity and `match_threshold=0.9` rather than a raw dot product exceeding 0.9; inserts unrelated addresses instead of overwriting them.
- Added `lookup_checked` for thresholded abstention, `delete`, reuse of holes in single-key writes after reaching append capacity, shape validation and explicit full-capacity errors.
- `write_batch` rejects an oversized batch instead of silently truncating it. Similarity-based lookup/search return normalized confidence scores.

At D=256, N=512, 35% corrupted query bits and 128 sampled queries/seed: **94.1% correct recall** across five seeds, exactly matching brute-force nearest-key retrieval on every sampled query. Novel-key insertion, deletion, and abstention checks passed. The allocated SDM with extra headroom occupies **279,072 B**, approximately **8.52×** the *idealized* bit-packed storage of the original 512 address/content pairs (32,768 B), excluding extra metadata and capacity. This is not a compressed-memory win; production would also need persistence/concurrency engineering.

## 3. NeuralHD physical reduction

`eliminate_dimensions` now returns `bank[:, keep_mask]` as a contiguous array **in the original dtype**, rather than a full-sized `float32` bank with zeros. `NeuralHDPipeline.search` selects the same coordinates from incoming queries; a mismatched input dimension raises. Complex FHRR phases are preserved during feature variance selection. The ablation path now slices coordinates as well.

At D=256, N=256, with 128 deliberately informative columns and 128 constant nuisance columns, 256 noisy held-out cues/seed:

| Method | Top-1 | Stored bank bytes |
|---|---:|---:|
| Full BSC | 30.2% | 65,536 |
| Variance-selected 128 dimensions | **30.2%** | **32,768** |
| Random 128 dimensions | 13.2% | 32,768 |

This synthetic task demonstrates **50% measured storage reduction without further accuracy loss**. It is not evidence of general downstream feature learning. On a pure random D=512 bank the selected threshold retained all 512 dimensions—no savings, and correctly no forced compression. Future validation needs held-out tasks and cross-model feature utility.

## 4. Quasi-Monte Carlo and reproducible indexed vectors

`Sobol` and `Halton` now use SciPy's actual **scrambled QMC engines**, and their `generate(index)` and `generate_batch(n,start)` outputs match exactly. The previously named Sobol routine was plain PCG64. A new `iid_indexed` mode uses seeded per-index PCG64 streams, providing reproducible vector addresses without pretending to be low-discrepancy.

D=256, 96 vectors, mean across 5 seeds:

| Method | Mean abs cosine of distinct pairs (lower better) | 95th percentile | Maximum |
|---|---:|---:|---:|
| Ordinary IID | 0.0494 | 0.1219 | 0.2266 |
| Indexed IID | 0.0502 | 0.1250 | 0.2359 |
| Scrambled Halton, thresholded bits | 0.0498 | 0.1219 | 0.2469 |
| Scrambled Sobol, thresholded bits | **0.0296** | **0.0469** | **1.0000** |

**Critical warning:** Scrambled Sobol had *perfectly antipodal pairs* (absolute cosine = 1) even though its **average** similarity was excellent. Binarization destroys some favorable QMC properties; **do not adopt this as a large HDC item-memory codebook** on mean similarity alone. Use `iid_indexed` for reliable ordinary pseudorandom indexing and add collision/coherence screening before any QMC deployment. SciPy is an optional dependency **only for the experimental QMC methods**, not for `iid_indexed`.

## 5. Stochastic computing

The existing BSC wrapper was already equivalent to standard binary HDC; it made no actual stochastic hardware speedup. Added a `sampled_similarity` CPU experiment: a finite stream samples independent random coordinate matches with replacement, giving an unbiased Monte Carlo estimate of bipolar cosine similarity. Mean RMSE over 5 seeds (80 vector pairs/seed):

| Sampled coordinates | RMSE |
|---:|---:|
| 64 | 0.1283 |
| 256 | 0.0604 |
| 1024 | 0.0315 |
| 4096 | 0.0156 |

More samples cost more CPU time and improve accuracy as expected. This is a **sampling reference**, not a circuit-level stochastic-computing accelerator or a measured FPGA implementation. Exact `BSC.dot_row` remains the preferable software baseline when an exact score is needed.

## 6. Quantum interface

Corrected the **classical amplitude-wise phase-product reference** to normalize its output. Replaced the false CNOT-based "SWAP test" with a **symbolic** CSWAP skeleton containing an ancilla and two data registers; OpenQASM export includes CSWAP operations. The original quantum binding/bundling/cleanup diagrams remain schematic, and there is **no input state-preparation circuit, controlled phase oracle, gate-accurate compilation, QPU run, or measured advantage**. In particular, a normalized elementwise product of amplitudes is not, by itself, a physical unitary circuit for arbitrary input states. QPU production remains blocked.

## Reproducibility and boundaries

The tests use five **new** seeds: `121711,121733,121757,121781,121793`. CPU-only Python 3.13.5, NumPy 2.3.5. Experimental QMC requires SciPy (version 1.17.0 in the test runtime). The benchmark used single-threaded BLAS (`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1`), and times are indicative only.

Files:
- `benchmark_repairs.py`, `benchmark_noise_followup.py` — rerunnable numerical tests.
- `test_repairs.py` — 19 strict green regression checks; ZogZoo's existing selftest also passed 20/20.
- `benchmark_results.jsonl` — 100 independent configurations/measurement rows.
- `noisy_factor_results.jsonl` — 40 rows (5 seeds × 4 architectures × clean/noisy), 480 decoded queries across both conditions.
- `benchmark_summary.json`, `benchmark_run.log`, `noise_run.log` — audit materials.
- `patched_source/` and `original_source/` — before/after six touched modules, plus a two-commit Git history bundle for rollback.

**What remains:** practical SDM compression, transactional persistence and realistic nearest-neighbor workloads; actual scalable resonator/beam factorization over large or superposed codebooks; robust QMC codebook screening; NeuralHD held-out generalization and learned feature selection; FPGA profiling and an actual QPU circuit or simulator. These research components should remain optional for MyAI until supported by task-level ablations.

**Conclusion:** the correctness regressions identified in the previous report are mostly repaired, and the new pair-search decoder is a useful correctness oracle. Zog Zoo's experimental suite is healthier, but claims about efficient general factorization, hardware acceleration, and quantum computation remain unproven.