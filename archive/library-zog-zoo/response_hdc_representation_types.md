# Response to Reviewer Question: HDC Vector Representation Types

**Context:** External review of the Zog Zoo HDC harness (2026-10-23).
**Question:** "Is the implementation using binary HDC (0/1 vectors), bipolar HDC (−1/+1 vectors), or real-valued hypervectors?"

---

## Short Answer

The harness tests **bipolar ±1** (primary, 9 of 14 pipelines), **complex unit-magnitude** (2 pipelines), and **real-valued L2-normalized** (1 pipeline + baselines). It does **not** use binary 0/1 vectors. The majority of pipelines operate in the bipolar ±1 regime, which is the strictest and most hardware-relevant representation.

---

## 1. Model Families and Their Vector Representations

### BSC — Binary Spatter Codes (Kanerva 1997)

| Property | Value |
|----------|-------|
| **Representation** | Bipolar ±1, stored as `int8` |
| **Generation** | `rng.choice(np.array([-1, 1], dtype=np.int8), size=(n, D))` |
| **Bind (XOR)** | Elementwise multiplication of two ±1 vectors → ±1 result |
| **Bundle (majority rule)** | Sum of vectors → threshold at 0 with deterministic tie-break |
| **Scoring** | Integer inner product `bank.astype(int32) @ query.astype(int32)` |
| **Bit width** | 1 bit per dimension (the absolute minimum) |
| **Pipelines** | `bag_idf`, `bow_flat`, `hybrid`, `ngram`, `ri`, `xor_position` (6 pipelines) |

### MAP — Multiply-Add-Permute (Gayler 1998, bipolar variant)

| Property | Value |
|----------|-------|
| **Representation** | Bipolar ±1, stored as `int8` |
| **Generation** | Identical to BSC (random ±1 assignment) |
| **Bind** | Componentwise multiplication (same as BSC) |
| **Bundle** | Sign of the sum, ties broken to +1 |
| **Scoring** | Same integer inner product as BSC |
| **Pipelines** | `map_bag` (1 pipeline) |
| **Note** | MAP and BSC are mathematically equivalent in the 1-bit case; distinction matters for multi-bit extension (tested in B4 equal-memory diagnostic) |

### FHRR — Fourier Holographic Reduced Representations (Plate 2003)

| Property | Value |
|----------|-------|
| **Representation** | Complex unit-magnitude, stored as `complex64` (8 bytes/dim) |
| **Generation** | `e^{iφ}` where `φ ~ Uniform(0, 2π)` — vectors on the unit circle |
| **Bind** | Complex elementwise multiplication (angle addition) |
| **Unbind** | Multiply by conjugate (angle subtraction) — **near-exact, no deconvolution noise** |
| **Bundle** | Sum then phase-normalize (majority phase rule) |
| **Scoring** | `np.real(bank @ conjugate(query))` — real part of complex inner product |
| **Pipelines** | `fhrr_bag`, `fhrr_hybrid` (2 pipelines) |
| **Key property** | Unbind is algebraically exact (within floating-point precision) |

### HRR — Holographic Reduced Representations (Plate 1995)

| Property | Value |
|----------|-------|
| **Representation** | Real-valued, stored as `float32` (4 bytes/dim) |
| **Generation** | `v ~ N(0, I_D)` then L2-normalized: `v / ‖v‖` |
| **Bind** | Circular convolution via FFT: `irfft(fft(a) * fft(b), D)` |
| **Unbind** | Circular correlation: `irfft(fft(bound) * conj(fft(a)), D)` — **noisy, heavy-tailed** |
| **Bundle** | Sum then L2-normalize |
| **Scoring** | Cosine similarity: `(bank @ q̂) / ‖bank_rows‖` |
| **Pipelines** | `hrr_bag` (1 pipeline) |
| **Key property** | Unbind has heavy-tailed noise (measured 0.77 mean / 0.17 min fidelity in H2) |

### Baselines (not HDC)

| Pipeline | Representation | Notes |
|----------|---------------|-------|
| `dense_cohere` | Real-valued float32, L2-normalized | Pretrained Cohere embeddings (1024-d), exact dot product |
| `emb_cohere` | Bipolar ±1, int8 | Pretrained embeddings projected through random matrix R then sign-binarized |
| `emb_rescore` | Bipolar ±1 + dense rescore | Binarized shortlist (top-k) re-ranked by dense embedding similarity |
| `bm25` | Sparse integer counts | Lexical index, no hypervectors |

---

## 2. Why Bipolar ±1 is the Primary Regime

1. **Strictest information budget:** 1 bit per dimension is the minimum. If HDC can't demonstrate an advantage with 1-bit vectors, it won't with more expensive representations.

2. **Hardware relevance:** The FPGA/ASIC motivation for HDC (Kleyko et al. 2017, 2019; Shrestha et al. 2019) rests on ±1 operations mapping to simple LUTs (XOR for bind, adder-tree + comparator for bundle). A 0/1 or float representation would defeat this hardware mapping.

3. **Exact arithmetic:** Integer inner products on ±1 vectors have no floating-point accumulation error. The only "noise" is intrinsic interference from superposition, not numerical precision.

4. **Reproducibility:** PCG64 seeded streams produce identical ±1 assignments across platforms and Python versions. Float32/complex64 BLAS operations can have platform-dependent rounding.

---

## 3. Why Not Binary 0/1?

1. **No self-inverse bind:** XOR bind requires both operands to be ±1. A 0/1 vector has no multiplicative inverse — you cannot "unbind" a 0/1 bound vector. The entire compositional algebra (H1/H2 test suite) depends on unbind.

2. **Non-uniform noise:** With 0/1 vectors, the "background" (uninformative dimensions) is 0, not −1. This creates asymmetric noise where zero-dimensions contribute nothing to the dot product, effectively reducing dimensionality. The interference analysis (H3) assumes uniform random ±1.

3. **Not in the literature:** None of the standard HDC text-encoding papers (Kanerva 1997; Plate 1995, 2003; Gayler 1998; Kleyko 2016; Joshi 2016; Sahlgren 2005) use 0/1 vectors. Using them would make results incomparable to published work.

---

## 4. Scoring and Similarity Metrics by Family

| Family | Score function | Normalization | Tie-breaking |
|--------|---------------|---------------|--------------|
| BSC/MAP | `dot = Σ bank[i,d] * query[d]` (integer) | Divide by D for cosine | Deterministic per-dimension tie vector (seeded) |
| FHRR | `real(bank @ conj(query))` | Inherent (unit magnitude) | N/A (continuous) |
| HRR | `(bank @ q̂) / ‖bank_row‖` | Explicit L2 normalization | N/A (continuous) |
| dense_cohere | `bank @ q` (both L2-normalized) | Inherent | N/A |
| emb_cohere | `dot / D` (same as BSC) | Divide by D | Same as BSC |

For the retrieval metric (top-1, nDCG@10), only the **ranking** matters, not absolute score values. The normalization choice affects only the `mean_cos` diagnostic column.

---

## 5. Implications for Fairness Assessment (Reviewer Q2)

The HDC pipelines are tested at their **most constrained representation** (1-bit, no learned parameters, random word-to-HV assignment):

- If HDC pipelines score at chance level, it's because the representation genuinely cannot capture the retrieval signal in the question→passage regime — not an implementation artifact.
- `emb_cohere` (binarized pretrained embeddings) provides the **upper bound** for 1-bit vectors with a *learned* encoding. The gap between `emb_cohere` and `bag_idf`/`hybrid` isolates: learned word representations vs. HDC compositional algebra.
- `dense_cohere` provides the **upper bound** for full-precision learned representations. The gap between `dense_cohere` and `emb_cohere` isolates: the cost of binarization.
- The three-way comparison (dense → binarized-learned → random-HDC) decomposes the total performance gap into:
  - (a) learned vs. random encoding
  - (b) full-precision vs. 1-bit
  - (c) HDC algebra vs. flat dot product

This decomposition is what allows the re-scoped verdict: "HDC compositional algebra has a defensible niche in the H2 regime map, but random-word HDC text encoding is NO-GO for retrieval" is a **representation** conclusion, not an implementation artifact.

---

## 6. Summary Table

| Question | Answer |
|----------|--------|
| Binary 0/1? | **No** — not used anywhere |
| Bipolar ±1? | **Yes** — 9 of 14 pipelines (BSC×6, MAP×1, emb_cohere×1, emb_rescore×1) |
| Complex unit? | **Yes** — 2 pipelines (FHRR) |
| Real-valued continuous? | **Yes** — 1 pipeline (HRR) + baselines (dense_cohere) |
| Multi-bit? | **Yes** — in B4 equal-memory diagnostic (2-bit, 4-bit BSC levels) |
| Learned encodings? | **Yes** — `emb_cohere`/`emb_rescore` use pretrained Cohere embeddings (credited to encoder, not HDC) |

---

## 7. Source Code References

All code in `Zog Zoo Dev\zogzoo_hdc\`:

| File | Relevant content |
|------|-----------------|
| `models.py` | `BSC`, `MAP`, `FHRR`, `HRR` classes with `atomic()`, `bind()`, `bundle()`, `dot_row()` |
| `text.py` | `TextEncoder` with schemes: `bag_idf`, `hybrid`, `ngram`, `xor_position`, `ri` |
| `runner.py` | `PIPELINE_DEFS` dict mapping pipeline names → (kind, model, scheme, multi_bit) |
| `core.py` | `make_streams()` — deterministic PCG64 seeded RNG |
| `selftest.py` | 19 selftests including encoder consistency, determinism, positive control |