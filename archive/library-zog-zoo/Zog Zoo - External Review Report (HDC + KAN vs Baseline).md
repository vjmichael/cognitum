# Zog Zoo — External Review Report

## Can HDC and KAN perform at baseline or better?

- **Date:** 2026-10-20 (final run 17:47 UTC)
- **Prepared for:** Claude (Anthropic) and Gemini (Google) — independent analysis
- **Status:** results final and reproducible; verdict **pending reviewer input** (Section 6)
- **Companion docs:** `Zog Zoo - Progress Report.md` (decision log), `Zog Zoo - Test Rig and Validation Ladder.md` (design doc)

---

## 0. Executive summary

- We tested whether two "alternative AI" components in the Zog Zoo hybrid model — **HDC** (hypervector/cognitive algebra) and **KAN** (Kolmogorov–Arnold networks) — can perform **at the level of current AI, or better**, in their assigned roles.
- **HDC: measured.** On four public BEIR retrieval benchmarks (banks 3,633–57,638 docs) plus SQuAD 2.0 dev (11,873 questions), HDC text encoding with random word vectors sits **at chance level (top-1 0.0–0.03) at every dimension (D = 32–1024) under every noise model** (clean, 20% bit-flip, 20% mixture). A flat bag-of-words index using the *same encoder family* (top-1 0.0–0.21) beats it **in every single cell** — position binding is destructive in the question→passage regime.
- **The true baseline** (dense 1024-d learned embeddings + exact nearest-neighbor — the closest offline proxy for "current AI" on these tasks): **top-1 = 40.7%–60.3%**. Binarizing those embeddings into HDC's native ±1 format retains **91–95%** of baseline at 1024 bits, drops to **~30–48%** at 128 bits (clean), and to **~7–15%** at 128 bits under 20% bit-flip noise.
- **KAN: not yet measured.** In Zog Zoo, KAN is designed as sub-function heads for numeric/logic computation (its baseline question: "K1: approximation error ≤ same-size MLP"). KAN K1 is **on hold** until this HDC review closes; we ask reviewers to confirm the K1 design (Q6).
- **Our honest reading (subject to reviewer pushback):** in the measured regime, random-vector HDC **cannot reach** the baseline for text retrieval, and adds nothing over a flat bag index. The recipe that *does* work — credited to the learned encoder + binary quantization + NN index (standard binary quantization, **not** an HDC contribution) — is: **learned encoder → binarize to ≥ 128 bits (≥ 256 bits under bit-flip-like noise) → nearest-neighbor side-channel** — 16–32 bytes per document. HDC's validated value remains its **compositional algebra** (synthetic benchmarks passed), not raw text retrieval.

---

## 1. Background

Zog Zoo builds a hybrid model: a commodity transformer+SSM backbone plus three research components — **HDC**, **KAN**, **Capsules**. The test-rig policy: prove the *unknown* parts cheaply in isolation (Tier A, no backbone) before scaling the *known* backbone. HDC is the first component.

Its Tier A verdict was **GO (contested)** after an external review, which required two closing empirical tests:

1. a **downward D-sweep under bit-flip noise** (the reviewer-prescribed real-world noise model), and
2. **real-data retrieval vs a binarized-embedding baseline**.

**This report contains the results of both tests.** Every number below is a measured value from a fixed-seed run; interpretations are explicitly labeled as such.

**What "baseline" means here.** The closest offline, reproducible proxy for "current AI" on retrieval tasks: a modern text-embedding model (1024-d; per the dataset provenance description, *Cohere embed-english-v3* — **we did not independently verify the generating model**) plus brute-force nearest-neighbor search. This is a strong baseline — embedding-based systems are top-tier on these benchmarks. We note for accuracy: a frontier LLM doing relevance judgment is a different (on some tasks, stronger) system; "at baseline" in this report means "at the level of a current embedding-based retrieval system."

---

## 2. Test protocol (exact definitions)

### Datasets (all public, used read-only)

| Dataset | Bank (documents) | Queries | Gold standard |
|---|---|---|---|
| BEIR fiqa | 57,638 | 648 | qrels |
| BEIR cqadupstack-android | 22,998 | 699 | qrels |
| BEIR nfcorpus | 3,633 | 323 | qrels |
| BEIR scifact | 5,183 | 300 | qrels |
| SQuAD 2.0 dev | 1,204 unique contexts | 11,873 | context match |

The four BEIR splits ship with precomputed 1024-d dense embeddings; the SQuAD mirror does not (hence no embedding baseline on that track).

### Pipelines (D = vector dimension)

1. **`dense_cohere` (the baseline):** precomputed 1024-d float embeddings, L2-normalized, exact dot product. *Full dimension only.*
2. **`emb_cohere`:** the same 1024-d embeddings projected through a seeded ±1 random matrix to D bits, then signed. *HDC-format (±1) storage of a learned representation.*
3. **`bow_flat`:** word → seeded ±1(D) random vector, bag superposition (sum), sign. *Flat-index control — same encoder family as (4), isolates position binding.*
4. **`hdc_text`:** word → seeded ±1(D) random vector, **bound to position** (XOR = elementwise product), superposed, sign. *The HDC text algebra under test.*

### Noise models (applied to the *query* vector at inference; strength a = 0.2)

- **clean** — no perturbation.
- **bit-flip** — flip exactly ⌊0.2·D⌉ coordinates (dense: sign-flip 20% of components). *The reviewer-prescribed real-world model.*
- **mixture** — (1−a)·q + a·u in float space, never re-signed (u = random ±1 vector; dense: Gaussian unit vector scaled to ‖q‖). *Re-signing ±1 would be a no-op for a ≤ 0.5 — a latent bug we caught and fixed.*

### Grid, metrics, reproducibility

- **Dimensions:** D = 1024, 512, 256, 128, 64, 32 (dense baseline at 1024 only).
- **Metrics:** top-1, top-10 (best gold document), mean best-gold rank, cosine to best gold. Chance level = 1/N (N = bank size).
- **Seeds:** word 20261020 · position 20261021 · emb-projection 20261022 · run 20261023 · dense-run 20261024 (separate stream).
- **Environment:** Windows, Python 3.14.6, numpy 2.5.0, pyarrow 26.0.0, openpyxl 3.1.5. Full run: **352 s, exit 0.**
- **Credit rule (locked):** `dense_cohere`/`emb_cohere` credit = "learned embedding model + vector index" — **never credited to HDC**. Nearest-neighbor = generic index, not an HDC contribution. `hdc_text`/`bow_flat` = the HDC-algebra family.

---

## 3. Results

### 3.1 Headline comparison — top-1, clean, D = 1024

| Dataset (bank N) | **dense baseline** | emb binarized @1024 | bow_flat | **hdc_text** | chance (1/N) |
|---|---|---|---|---|---|
| fiqa (57,638) | **0.4074** | 0.3858 (95% of dense) | 0.0355 | 0.0000 | 0.000017 |
| cqadupstack-android (22,998) | **0.4034** | 0.3734 (93%) | 0.1631 | 0.0072 | 0.000044 |
| nfcorpus (3,633) | **0.5139** | 0.4675 (91%) | 0.1920 | 0.0124 | 0.00028 |
| scifact (5,183) | **0.6033** | 0.5467 (91%) | 0.1500 | 0.0000 | 0.00019 |
| SQuAD 2.0 dev (1,204) | — (no embeddings in mirror) | — | 0.2097 | 0.0068 | 0.00083 |

**hdc_text is ≤ ~2.5% of the baseline wherever a baseline exists; bow_flat is 9–40%; emb-binarized@1024 is 91–95%.**

### 3.2 Dimension degradation — binarized learned embeddings (`emb_cohere`), top-1

D =        1024     512     256     128     64      32
**clean:**
fiqa       0.3858   0.3194  0.2546  0.1219  0.0340  0.0093
android    0.3734   0.3433  0.2675  0.1588  0.0658  0.0215
nfcorpus   0.4675   0.4118  0.3375  0.2477  0.1610  0.0433
scifact    0.5467   0.4833  0.3767  0.2433  0.1133  0.0400

**20% bit-flip (reviewer-prescribed stress model):**
fiqa       0.2855   0.2022  0.0741  0.0262  0.0031  0.0015
android    0.3133   0.2246  0.0944  0.0315  0.0129  0.0029
nfcorpus   0.3529   0.2879  0.1486  0.0495  0.0402  0.0217
scifact    0.4400   0.3433  0.1767  0.0767  0.0100  0.0033

As a fraction of the dense baseline: at D = 128 clean, **30–48%**; at D = 128 bit-flip, **7–15%**; at D = 256 bit-flip, **18–32%**; at D = 32, ≤ ~8% in every condition.

### 3.3 Baseline robustness and the HDC-family under stress (top-1)

- **dense_cohere** (clean / mixture / bit-flip): fiqa 0.4074 / 0.4120 / 0.3796 · android 0.4034 / 0.4020 / 0.3834 · nfcorpus 0.5139 / 0.5170 / 0.4706 · scifact 0.6033 / 0.6000 / 0.5433. → 20% sign-flips cost dense vectors only **5–10%** top-1. (Two mixture cells exceed clean by 1–3 queries — within sampling noise, shown for transparency.)
- **emb_cohere @1024** under bit-flip costs **16–26%** top-1 — binarized vectors are more sensitive to bit-level noise than float vectors.
- **bow_flat** (clean → bit-flip, D=1024): fiqa 0.0355 → 0.0247 · android 0.1631 → 0.1259 · nfcorpus 0.1920 → 0.1579 · scifact 0.1500 → 0.1100 · SQuAD 0.2097 → 0.1293.
- **hdc_text:** top-1 0.0–0.03 in **all 72 cells** (5 datasets × 6 D × 3 noise, SQuAD included). SQuAD dev: 0.0068 at D=1024 (≈8× chance) → 0.0007–0.0011 (≈1× chance) at D ≤ 64.

**Full 264-row results:** `results_hdc_realdata.json` (config + all rows) and `results_realdata_rows.jsonl` (per-row stream) — paths in Section 7.

---

## 4. Findings (observation → interpretation, kept separate)

- **F1 — Random-word HDC text encoding is at chance in this regime.** *Observation:* top-1 0.0–0.03 in all 72 cells, every dataset, every D, every noise model. *Interpretation:* with random word vectors the only available signal is word overlap, and in question→passage pairs overlap is sparse and partial; the encoding cannot exploit it better than the flat index. This is a **regime finding** (random vectors, retrieval task, N = 1.2k–57.6k, D = 32–1024) — not a claim that HDC is universally weak.
- **F2 — Position binding is the ablation that hurts.** *Observation:* `bow_flat` > `hdc_text` in **every cell**. *Interpretation:* XOR position-binding is designed for sequence similarity; for set/semantic matching it makes shared words at different positions near-orthogonal, destroying the one signal available without a learned encoder. (Standard HDC text practice is bag-of-words — we measured both, which is why the ablation is clean.)
- **F3 — Binarization is cheap at full dimension.** *Observation:* D=1024 ±1 storage retains 91–95% of dense top-1 (−2.2 to −5.7 points). *Interpretation:* 128 bytes/document in HDC-native ±1 format is a viable storage format for a learned representation.
- **F4 — Measured cliff (the requested D-sweep answer).** *Observation:* binarized baseline retains ≥ 30–48% of dense at D=128 clean, but ≤ 8% by D=32; under 20% bit-flip the cliff moves up one grid step (18–32% at D=256; 7–15% at D=128). *Interpretation:* for HDC-format text memory at bank sizes 3.6k–57.6k, the practical operating point is **D ≈ 128 (clean) to D ≈ 256 (bit-flip-like noise)**.
- **F5 — Noise model matters for ±1 vectors more than for float vectors.** *Observation:* 20% sign-flips cost dense 5–10% top-1 but binarized 16–26% at D=1024. *Interpretation:* if actual storage/channel noise is bit-flip-like, the dimension budget must be larger than the clean case suggests; the two noise models bound a realistic range.
- **F6 — Reproducibility.** *Observation:* two latent harness bugs (cosine not normalized by D; mixture noise re-signing = no-op) were caught and fixed **before** the final run; after adding the dense baseline, all 252 ±1 rows reproduced **bit-identically** (independent RNG stream). *Interpretation:* the reported numbers are stable under harness modification, which we take as evidence the pipeline — not the noise — drives the results.

---

## 5. What this report does NOT show (limitations — read before judging)

- **L1 — Random word vectors are a lower bound on "HDC for text."** We did not test learned HDC encoders (no encoder model was downloaded in this environment), n-grams, or attention over bindings. If a *learned* encoder + HDC algebra could approach baseline, that is the next test to run — it is not in this report.
- **L2 — Baseline provenance.** "Cohere embed-english-v3" is the dataset's own description; we did not independently verify it. Baseline strength is proportional to that model's quality.
- **L3 — SQuAD track** has no embedding baseline (the mirror carries none) — that track is HDC-family vs chance only.
- **L4 — No BM25/TF-IDF baseline** (the standard lexical IR reference). `bow_flat` is a binarized random-hash cousin of it, but real BM25 would bracket the lexical ceiling better.
- **L5 — Single seed per pipeline.** Reproducible, but no multi-seed variance bands.
- **L6 — KAN has zero results here** (Section 8) — by design: its gate is on hold pending this review.
- **L7 — "Baseline" ≠ frontier LLM.** It is a 2024-generation embedding model + brute-force NN — the strongest *reproducible offline* measure we can produce in this environment.

---

## 6. Questions for the reviewers (numbered; answers will be recorded in the project log)

- **Q1 — Baseline fairness.** Is "1024-d learned embeddings + exact NN" an acceptable proxy for "current AI performance" on these tasks? What else would you require (BM25? zero-shot LLM relevance judgments?)?
- **Q2 — HDC representation fairness.** Is the pair (`bow_flat`, `hdc_text`) with random vectors a fair representation of standard HDC text encoding — or is there a standard text-HDC recipe (n-grams, learned vectors, attention over bindings, other superposition order) that we are missing?
- **Q3 — Breakpoint.** We measured the binarized-baseline cliff at **D ≈ 128 (clean) / D ≈ 256 (bit-flip)** for N = 3.6k–57.6k. Does this agree with your theoretical expectation? (A prior estimate of ~D 64–128 at N ≈ 10k was within a factor of 2 of the measured cliff.)
- **Q4 — Credit.** Given `hdc_text` ≤ chance in every cell, do you agree that in this regime "random-word HDC adds no value over a flat bag index"? What observation would change your mind?
- **Q5 — The practical recipe.** Binarized learned embeddings + NN at D ≈ 128–256 (16–32 bytes/document) retains ~30–48% of dense top-1 (D=128 clean) — do you consider this a defensible "HDC-compatible external memory" claim, or an overclaim?
- **Q6 — KAN baseline.** We define KAN's baseline as **K1: function-approximation error ≤ same-size MLP** on a specified numeric task set, with K2 = human-readable learned edge functions and K3 = auditable sub-computation. Is that the right baseline and the right *first* test? Which task set would be most informative?
- **Q7 — Missing pieces.** What must be shown before a claim "HDC ≈ baseline" could be supported (learned encoders? more datasets? larger D? other noise models? integration with a backbone?)?
- **Q8 — (Gemini)** Do you see the same picture? Where do you most disagree — particularly on Q2/Q4?

---

## 7. Reproducibility appendix

- **Code:** `C:\Users\UserMN4312\Documents\Zog Zoo Dev\realdata_retrieval.py` — single file, numpy-only, ~470 lines.
- **Run:** `C:\Python314\python.exe realdata_retrieval.py` (≈352 s) · smoke subset: `realdata_retrieval.py smoke` (seconds).
- **Results:** `C:\Users\UserMN4312\Documents\Zog Zoo Dev\results_hdc_realdata.json` (config + 264 rows) · `results_realdata_rows.jsonl` (per-row stream, power-loss safe).
- **Data (read-only):** `C:\Users\UserMN4312\Downloads\{fiqa, cqadupstack-android, nfcorpus, scifact}\{corpus, queries, qrels}\*.parquet` and `C:\Users\UserMN4312\Downloads\SQuAD_v2.0_Dataset-main\squad_2.0_dev_complete_11873.xlsx`.
- **Seeds:** 20261020 (word) · 20261021 (position) · 20261022 (emb projection) · 20261023 (run) · 20261024 (dense run).
- **Environment:** Windows, Python 3.14.6, numpy 2.5.0, pyarrow 26.0.0, openpyxl 3.1.5.
- **Final run:** 2026-10-20 17:47 UTC, exit code 0, 352 s.
- **Verifications performed:** (a) smoke run validated before the full run; (b) after the dense baseline was added, all 252 prior ±1 rows reproduced bit-identically (independent RNG stream for dense cells); (c) two latent harness bugs found and fixed before the final run (F6).

---

## 8. KAN status (for completeness)

Per the test-rig design, KAN's role in Zog Zoo is **sub-function heads for numeric/logic tasks** (not text retrieval). Tier A gates: **K1** function approximation (error ≤ same-size MLP), **K2** interpretability (learned edge functions humans can read), **K3** auditable sub-computation.

**Status: design complete; implementation ON HOLD** per the locked build order (waiting on closure of this HDC review). **No KAN numbers exist yet** — reviewer input on Q6 will shape the K1 test before it starts.

---

*Prepared for external review. Every tabled number is a measured value from the final run; every interpretation is labeled as interpretation. We welcome disagreement with the credit rule (Section 2) and with F1–F5 — the goal of this report is to be wrong in a checkable way, not to be impressive.*