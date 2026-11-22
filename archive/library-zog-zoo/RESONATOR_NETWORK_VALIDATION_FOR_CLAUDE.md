# Zog Zoo — Genuine Recurrent Resonator and Claude Audit Follow-up

**2026-10-24 | CPU-only research/prototyping validation.** This report concerns the HDC component, not a production-certified MyAI memory service.

## What changed, and what did not

The previous `resonator_factor(..., max_iters=3)` was **NOT a resonator network**: it invoked `factor_pair_search` (bounded combinatorial search). This remains available unchanged as the *reference oracle*, for compatibility with the prior experimental-suite tests.

New public API in `zogzoo_hdc.resonator`:

- `ResonatorNetwork(model, banks, max_iters=24, restarts=16, soft_steps=4, seed=0, projector='winner' | 'codebook')`
- `resonator_network(model, composite, factor_banks, ...)`
- `ResonatorResult(indices, similarity, converged, iterations, restarts_used, projections, trace)`

Each factor slot has its own candidate item memory. At each recurrent update, the model binds *current estimates of all the other factors*, unbinds that estimate from the composite, projects the resulting cue onto the slot's codebook, and feeds the projection into subsequent slots. The updated estimates are coupled and iterated over multiple sweeps. Optional seeded restarts address local minima. **No pair/triple enumeration occurs in the recurrent code path.**

The two projection rules are:

- **Winner**: WTA cleanup with early soft-to-hard annealing; chooses/feeds back candidate hypervectors.
- **Codebook**: approximate standard resonator-style autoassociative feedback, `Xᵀ X cue`, with sign/phase/L2 normalization depending on VSA. This uses contributions from all entries in a factor bank; it is a recurrent feedback network, not a global solver.

This is a research implementation of coupled-feedback resonator dynamics, **not** a claim of matching every resonator-network variant in the literature. It is not trained, does not learn a projector, and has no global convergence guarantee. Current CPU code is NumPy, with FFT operations for HRR.

### Correctness checks

- **35/35 targeted regression tests passed**, consisting of 16 new resonator checks and 19 earlier experimental-module regression checks. The new tests cover the four VSAs; slot-specific factor banks; deterministic seeds; controlled known fixed points; blind retrieval; trace; bad parameter rejection; four-factor interface; and both projector modes. A test monkeypatches pair search to throw an exception, proving the recurrent path does not call it.
- **20/20 original Zog Zoo self-tests passed** after the module and public API update.
- The only modified source files are `zogzoo_hdc/resonator.py` and `zogzoo_hdc/__init__.py`. Original versions and an offline Git bundle are preserved. None of the historical benchmark rows was overwritten.

## Recurrent benchmark protocol and results

**Three fresh seeds:** `990101`, `990211`, `990331`. `D=256`, *three separate candidate banks*, each with `V=12` or `32` factors; 8 independently sampled ground-truth triples per cell, clean and with 10% perturbation; 1/8/18 random restarts. Per-architecture samples: 3 seeds × 2 V × 8 trials = **48 trials per noise condition at each restart budget**. Noise differs by VSA (binary bit flips, FHRR phase changes, or HRR additive noise), so cross-VSA noise scores are **not** claims of equal-SNR robustness. CPU timings are descriptive only, not tuned throughput results.

### WTA coupled network, 18 restarts

| VSA | Clean exact triple recovery | 10% perturbed recovery | Mean clean decode (ms) | Mean perturbed decode (ms) |
|---|---:|---:|---:|---:|
| BSC | 60.4% | 50.0% | 8.70 | 12.92 |
| MAP | 60.4% | 50.0% | 9.10 | 13.94 |
| HRR | 95.8% | 93.8% | 11.53 | 33.90 |
| FHRR | 62.5% | 64.6% | 7.89 | 11.74 |

The fact that a few noisy scores increase slightly is sampling variability, not evidence that noise helps. **One-restart accuracy was very low** (approximately 2%–23% depending on model and noise); restarts are a significant cost.

The **paired three-factor reference oracle** exhaustively enumerated the first two *slot-specific* banks and cleaned up the third, then ranked reconstruction. It obtained **100%** on its 24 clean V=12 trials; typical CPU times were ~1.5–11.2 ms per query depending on VSA. The oracle is cheaper and more accurate in this small regime; its combinatorial cost scales poorly. The new resonator does *not* beat this baseline in the benchmark.

### Matched projector comparison

96 rows: four VSAs × two V × three seeds × two corruption levels × two projector types, 8 identical trials per row, all with 18 restarts.

| VSA | WTA exact recovery | Codebook exact recovery | WTA ms | Codebook ms |
|---|---:|---:|---:|---:|
| BSC | 55.2% | **60.4%** | 10.08 | 5.13 |
| MAP | 55.2% | **60.4%** | 10.03 | 5.08 |
| HRR | **94.8%** | 80.2% | 21.88 | 11.87 |
| FHRR | **63.5%** | 60.4% | 10.13 | 3.77 |
| **Overall** | **67.2%** | **65.4%** | 13.03 | 6.46 |

The codebook rule is faster here, but sometimes less accurate. These results are *not* directly comparable to earlier C5 relational test accuracies: here the true factors were independently drawn from three separate slot-specific codebooks, and the task is blind factor recovery rather than graph traversal.

**Scope boundaries:** Maximum tested V=32 for the complete matched confirmation; no claim of 100/1,000+ candidate scaling, large D, real-world semantic factors, or GPU/FPGA energy improvements. A larger exploratory sweep was stopped by the runtime limit and is not included as a complete confirmation dataset.

## Claude audit — independent checks

1. **Negative test on pre-fix TorchHD adapter:** re-ran the unchanged `test_torchhd_adapter.py` (17 cases) against both adapter versions. Old adapter: **7 failed, 10 passed**; fixed adapter: **17 passed**. The failures included BSC XOR/majority/bitflip and the independent HRR circular-convolution guard. Thus the regression tests actually detect the historical bug.
2. **Third independent C1 oracle:** newly ran **51/51** tests spanning HRR direct **O(D²)** circular convolution (the reference does not call NumPy FFT, TorchHD, or Zog Zoo), native TorchHD bind, independent cosine computation, and TorchHD permutation shift signs compared with `np.roll` for shifts `+1, -1, +3`. This closes those particular *mathematical* gaps, but not every C1 permutation/encoder variant.
3. **C6 exactly-zero error:** original stress test used **D=1024**, maximum 64 active records, and a fixed pool of 256 keys/512 values. Binary BSC/MAP accumulators were `int32` (exact integer sums), HRR accumulators `float64`, FHRR `complex128`, while HRR contributions were rounded to `float32` and FHRR to `complex64` **before** addition/subtraction. With at most 64 active quantized contributions, the high-precision accumulators can reproduce the same sums with *exactly zero observed residual* in this bounded workload. This is plausible arithmetic and a measured max-difference against a rebuilt accumulator, **not** a claim that unbounded float updates are drift-free. Larger ranges, arbitrary float64 contributions, and nonreproducible ordering require independent tests.
4. **C6 durability / abstention:** **not solved here**. Earlier test verified process reload, deterministic state replay and checksum rejection—not transactional crash consistency, missing-key abstention, power-loss durability, or larger live key sets. HDC remains an optional, rebuildable derived index.
5. **C2 equal total working bytes, V≥1000:** **not run** in this update. Prior tests used 256 KiB stored-index budgets with V=64, and a separate V=1000 conventional comparison without equal total bytes. No claim of HDC superiority under Claude's preferred final contract.

## Research/engineering recommendation

Keep `factor_pair_search` as a **small-bank correctness oracle** and `ResonatorNetwork` as an opt-in **experimental recurrent factorizer**. Require bounded compute, observable convergence, per-slot candidate semantics, restarts, and a fall-back/abstention policy. The current data does **not** justify replacing exact structural traversal, nearest-key retrieval, or the transformer with this decoder. No new resonator-related barrier to integrating MyAI or beginning KAN work was observed; durable C6 memory claims and production HDC value need the additional ablations Claude requested.

## Reproduce

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -q benchmarks/test_recurrent.py benchmarks/test_repairs.py
python -m zogzoo_hdc selftest
python benchmarks/benchmark_recurrent.py --compact --out results/recurrent_compact.jsonl
python benchmarks/benchmark_projection_modes.py
python benchmarks/audit_c1_oracles.py
```

The tests need the full Zog Zoo source and, for the C1 oracles, the user-uploaded TorchHD 5.8.4 source on `PYTHONPATH`.