# Zog Zoo — HDC Strengths Test Matrix

| Field | Value |
|---|---|
| **Version** | 0.1 — Draft |
| **Date** | 2026-10-24 |
| **Status** | Starting targets. Lock (commit to git) before the first run. |
| **Replaces** | Lexical-retrieval Phase B1 (closed: HDC word encodings trail BM25 and binarized learned embeddings) |
| **Separate from** | BEIR retrieval results (archived) and the Wikipedia scalability track (Appendix A) |

---

## 0. Ground rules

1. **Pre-register.** Commit this file and its thresholds before any run. Thresholds are not edited after seeing results. A change means a new version and a re-run.
2. **Reference first.** Run Torchhd's own examples and the cross-implementation test (1.6) before trusting your own code.
3. **Models:** MAP (bipolar), BSC (binary), FHRR (complex), HRR (real, circular convolution).
4. **Dimensions:** D ∈ {512, 1024, 4096, 10000}. **Seeds:** at least 5. Report mean ± SD and a 95% bootstrap CI.
5. **Every category has two baselines:** (a) an exact conventional structure (dictionary or SQLite), and (b) a matched-memory baseline (same total bytes).
6. **Exactness is expected to favor the dictionary.** The question is where HDC is better: noise, fixed memory, graceful degradation, or hardware cost. Report both.
7. **Corruption definition (p):** the fraction of components independently corrupted. Binary/bipolar: sign flip. Real/complex: replaced by a fresh random draw. Always state which.
8. **Logging:** one JSONL row per run with category, test_id, model, D, seed, parameters, metrics, memory_bytes, time_s, config fingerprint, and library versions. Never delete files. Everything goes in git.
9. **Roles:** Qwen implements, runs, and reports numbers only. The owner writes the verdict text after the run.
10. **Time cap:** 5 working days for the whole matrix. Per-category kill rules are in section 2.

---

## 1. Matrix at a glance

| # | Category | Core question | Sweep | Baselines | Primary metric | Starting pass criterion |
|---|---|---|---|---|---|---|
| 1 | Algebraic correctness | Do the operations behave as the algebra says, deterministically? | model × D × 10k trials | Torchhd (reference); own code | Correctness and numerical error | All identities within tolerance. Own vs Torchhd agree. |
| 2 | Associative memory capacity | How many role–value pairs can one bundled vector hold? | N pairs × V values × D × model | Exact dict; fixed-size hash table at equal bits; kNN over stored keys | Top-1 recovery vs memory load; N90 and N99 | Monotone, theory-consistent curve; report bits per recoverable pair |
| 3 | Noise and interference | How gracefully does recovery degrade under corruption and clutter? | p ∈ {0, 1, 2, 5, 10, 20, 30, 40}% × load × distractors | Dict (unprotected); dict + simple ECC at equal total bits | Accuracy vs corruption; p at 90% accuracy | At p=10%, ≥ 90% of clean accuracy at N = 0.5·N99 |
| 4 | Compositional representation | Can it tell structures apart that use identical symbols? | structure type × edit distance × p | Bag-of-symbols (must hit chance on permutations); canonical-form dict; n-gram overlap | Structure discrimination accuracy; similarity vs edit distance | ≥ 95% at p=10%, K=10 confusable alternatives; Spearman ≥ 0.9 |
| 5 | Relational composition | Can it follow multi-step relations from stored triples? | depth 1–6 × entities × D × cleanup on/off × p | Exact adjacency-dict traversal; same dict under the same corruption | Correct-answer rate vs depth | ≥ 90% at depth 3 (p=0); ≥ 80% at depth 3 (p=10%) |
| 6 | Continual memory updates | Do insert, update, delete, and retrieve stay accurate over time? | op mix × working-set size × ops count | SQLite key–value store; vector index with periodic rebuild | Accuracy over time, interference, update cost | ≥ 95% accuracy on untouched items after 100k mixed ops; per-op cost no worse than baseline |

---

## 2. Detailed tests

### Category 1 — Algebraic correctness (unit tests; cross-check against Torchhd)

| ID | Test | Method | Pass |
|---|---|---|---|
| 1.1 | Bind/unbind identity | unbind(bind(a, b), a) vs b over 10k random pairs | MAP, BSC, FHRR: exact within float tolerance. HRR: report the similarity distribution (approximate by design). |
| 1.2 | Binding properties | Commutativity, associativity, self-inverse (where applicable), similarity preservation: sim(bind(a, c), bind(b, c)) ≈ sim(a, b) | Within tolerance, or the documented exception for that model |
| 1.3 | Permutation | Exact invertibility of ρᵏ; ρ(a) quasi-orthogonal to a; order encoding via shifts | Invertible exactly; |cos| ≲ 4/√D |
| 1.4 | Quasi-orthogonality | Mean and SD of cosine between random vectors | Mean ≈ 0, SD ≈ 1/√D |
| 1.5 | Determinism | Same seed gives bit-identical results across runs and across separate processes (check hash-randomization effects) | Identical hashes |
| 1.6 | Cross-implementation | Own code vs Torchhd at the same seeds and models | Binary: exact. Float: ≤ 1e-5 max abs difference. **Any mismatch is a bug; resolve before continuing.** |

**Kill rule:** none. Failures here are fixed, not dropped.

### Category 2 — Associative memory capacity

| ID | Test | Method | Metric |
|---|---|---|---|
| 2.1 | Role–value store | Bundle N role⊗value pairs. Query by unbinding a role, then clean up against a codebook of V values. N from 10 up to 3× the expected N90. | Top-1 recovery vs N; N90 and N99 |
| 2.2 | Codebook size | V ∈ {100, 1k, 10k, 100k} | N99 vs V |
| 2.3 | Sharding | Split N pairs across k bundles of D/k bits (equal total bits) | Recovery vs k at fixed total bits |
| 2.4 | Equal-memory comparison | Same total bits for: HDC bundle, fixed-size hash table with key fingerprints, kNN over stored key vectors | Bits per recoverable pair at 99% recovery |

**Kill rule:** if the hash-table baseline recovers more pairs per bit at 99%, drop the capacity claim. HDC's value must then come from categories 3, 4, or 6.

### Category 3 — Noise and interference resistance

| ID | Test | Method | Metric |
|---|---|---|---|
| 3.1 | Corrupted memory | Corrupt a fraction p of the stored bundle's components, then query. Fixed N = 0.5·N99. | Accuracy vs p |
| 3.2 | Corrupted cue | Corrupt p of the query role vector; separately, erase 50% of its components | Accuracy vs p and vs erasure |
| 3.3 | Interference | Add M unrelated bound pairs to the bundle | Accuracy vs M |
| 3.4 | Hardware-fault emulation | Stuck-at faults in q% of dimensions; random dimension dropout | Accuracy vs q |
| 3.5 | Baselines under the same corruption | (a) serialized dictionary with unprotected bits; (b) dictionary + repetition or Hamming ECC at the same total bits as the HDC memory | Accuracy vs p for each |

**Kill rule:** if dict + ECC at equal total bits matches HDC's accuracy-vs-corruption curve, HDC has no robustness advantage in software.

### Category 4 — Compositional representation

| ID | Test | Method | Metric |
|---|---|---|---|
| 4.1 | Order and role sensitivity | Encode structures with identical symbols: sequences ABC / CBA / ACB; (A above B) vs (B above A); trees ((A B) C) vs (A (B C)). Classify a noisy encoding among K = 5, 10, 20 confusable alternatives. | Discrimination accuracy vs K and p |
| 4.2 | Graded similarity | Structure pairs at controlled edit distance (1, 2, 3 swaps). Compare HDC similarity to edit distance. | Spearman correlation |
| 4.3 | Partial structure | Query with a structure missing one role; retrieve the full structure from a store of S structures | Top-1 accuracy vs fraction missing and S |
| 4.4 | Baselines | Bag-of-symbols (**sanity: must score chance on permutations**); canonical-form dict (exact); n-gram overlap | Same metrics |

**Kill rule:** if only the exact canonical-form dict matches the results and HDC has no advantage on 4.2 or 4.3 (graded or partial matches), compositional representation adds nothing beyond exact structures.

### Category 5 — Relational composition

| ID | Test | Method | Metric |
|---|---|---|---|
| 5.1 | Relation chains | Store triples (e, r, e′) as role–filler bindings. Query r₂(r₁(e)) for depth d = 1..6, decoding step by step. Run with and without cleanup. | Correct-answer rate vs depth |
| 5.2 | Composition rules | Kinship-style composition (parent∘parent = grandparent, etc.). Use the relation inventory from CLUTRR in its **structured/graph form** if available. If not, use a synthetic equivalent. Text-to-relation extraction is out of scope; test the algebra only. | Accuracy vs hops |
| 5.3 | Analogical mapping | Learn a mapping vector from one pair (e.g., country→capital) and apply to held-out pairs | Held-out accuracy |
| 5.4 | Baselines | Exact adjacency-dict traversal (expect 100%); same dict under the same corruption p | Accuracy vs depth and p |

**Kill rule:** for exactly defined relations the dict wins at p = 0 by definition. HDC survives this category only if it degrades more gracefully under corruption or a fixed memory budget (use 5.4 at p > 0), or if 5.3 shows something the dict can't do.

### Category 6 — Continual memory updates

| ID | Test | Method | Metric |
|---|---|---|---|
| 6.1 | Insert stream | Insert N associations in batches into a fixed-size store; after each batch query everything stored | Accuracy vs number inserted |
| 6.2 | Update and replace | Overwrite a key's value (subtract old binding, add new) | Accuracy of new value; residual of old; effect on other items |
| 6.3 | Delete | Remove M items by subtracting their bindings | Accuracy of the remaining items |
| 6.4 | Churn | 100k mixed ops (50% insert, 25% update, 25% delete) over a working set at 50% of N99 | Accuracy of untouched items over time |
| 6.5 | Cost | Per-operation latency and bytes touched. Optional: wall-power energy with a plug-in meter. | µs/op, bytes/op, J/op |
| 6.6 | Baselines | SQLite key–value store (exact); vector index with periodic rebuild | Same metrics |

**Kill rule:** if accuracy of untouched items falls below 90% before 100k ops at 50% of N99, continual updates are not an HDC strength at this scale.

---

## 3. Run order and budget

| Stage | Work | Budget |
|---|---|---|
| 0 | Install Torchhd in a clean environment; run its tutorials. Check Python and PyTorch version compatibility. Git-init. Lock this document. | 0.5 day |
| 1 | Category 1 (including 1.6) | 0.5 day |
| 2 | Categories 2 and 3, run as one capacity-vs-corruption sweep | 1 day |
| 3 | Category 6 | 1 day |
| 4 | Category 4 | 1 day |
| 5 | Category 5 | 1 day |
| 6 | Results tables, one-page verdict (owner-written) | 0.5 day |

**Total cap: 5 working days.** Stop and write the verdict if three or more categories hit their kill rules.

---

## 4. Decision rules after the run

| Outcome | Interpretation |
|---|---|
| Wins in 3, 4, or 6 against the matched baselines | HDC has a defensible role as a noise-tolerant, fixed-size associative memory or structure encoder. Next: efficiency measurement on target hardware (CPU first, FPGA only if the CPU profile justifies it). |
| Wins only under corruption (3, 5.4) | The value is fault tolerance. Relevant to low-power or in-memory hardware, not to a software coprocessor. |
| Loses to dict + ECC and the hash table everywhere | Park HDC. Record the result, with the numbers, as a closed finding. |

---

## Appendix A — Separate track: Wikipedia shard scalability (not part of the pass/fail matrix)

Five Parquet shards of `wikipedia-2023-11-embed-en-v3-int8-binary` are already downloaded (5 of 414). No need to download the rest for this phase. Keep this track separate from BEIR retrieval and from the six categories above.

| Measure | Notes |
|---|---|
| Ingestion | Parquet read speed, encoding throughput, peak RAM |
| Memory scaling | Actual memory for 1 to 5 shards |
| Associative search | Query latency and throughput as the bank grows |
| Binary representation | Packed-bit vs int8 performance |
| Multithreading | 1 thread vs 12 threads, identical workload |
| GPU | Batch encoding and large similarity calculations on the R9700, including transfer overhead |
| Incremental updates | Add or replace associations without a full rebuild |

**Labeling rule:** the Cohere int8 and packed-binary representations are **baselines, not native HDC results.** Report cold-cache and warm-cache runs separately.

---

## Appendix B — References

- **Torchhd** (JMLR 2023, MIT license): reference implementation for MAP, BSC, HRR, FHRR and others.
- **Kleyko et al., "A Survey on Hyperdimensional Computing aka Vector Symbolic Architectures," Parts I and II** (arXiv 2111.06077, 2112.15424).
- **Schlegel, Neubert, Protzel, "A Comparison of Vector Symbolic Architectures" (2022):** per the owner's note, compares 11 VSA implementations on bundling capacity, binding/unbinding accuracy, interference, and recognition tasks. Verify the exact test protocols against the paper before copying parameters.
- **CLUTRR** (`github.com/facebookresearch/clutrr`): kinship-reasoning benchmark. The text version requires an extraction step that is not HDC's job. Check whether a structured form is available.