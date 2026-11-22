# Zog Zoo — HDC Strengths Benchmark Execution Plan

| Field | Value |
|---|---|
| **Date** | 2026-10-24 |
| **Status** | PLANNED — awaiting GO for Phase 1 |
| **Authoritative protocol** | `Zog_Zoo_HDC_Strengths_Test_Matrix_v0.2.md` (C1–C7) |
| **Companion docs** | `Zog Zoo - Progress Report.md`, `Zog Zoo - Test Rig and Validation Ladder.md` |
| **Working folder** | `C:\Users\UserMN4312\Documents\Zog Zoo Dev\` |
| **Results directory** | `Zog Zoo Dev\results\` (JSONL, append-only, resumable) |
| **Schema** | `zog-zoo-hdc-v0.2` (per Test Matrix §4 JSONL shape) |

---

## Purpose

This document breaks the Test Matrix v0.2 run plan (9 stages) into **14 benchmark phases** with **37 sub-phases**. Each sub-phase is a contained, verifiable unit that produces JSONL rows conforming to the v0.2 schema.

**Execution rule:** After each **phase** completes, stop and wait for the owner's explicit GO before proceeding to the next phase. Within a phase, sub-phases execute sequentially.

**Prior work preserved:** Phase B1 (BEIR exploratory) results in `results\rows_run.jsonl` and `results\rows_smoke.jsonl` are historical. They are NOT superseded — they inform baselines but the C1–C7 tests are the authoritative measurement.

---

## Phase Overview

| Phase | Matrix Stage(s) | Sub-phases | Focus | Gate to proceed |
|-------|----------------|-----------|-------|-----------------|
| **P1** | 0 + 1 | 6 (P1.1–P1.6) | Foundation + smoke | All smoke files `status: ok` |
| **P2** | 2 | 6 (P2.1–P2.6) | C1 hard gate — algebraic correctness | All 4 VSAs pass required properties |
| **P3** | 3a | 3 (P3.1–P3.3) | C2 — associative capacity | Feasible grid identified, baselines set |
| **P4** | 3b | 3 (P4.1–P4.3) | C3 — noise & interference | Noise curves + matched baselines |
| **P5** | 4a | 3 (P5.1–P5.3) | C4 — compositional structure | Structural advantage quantified |
| **P6** | 4b | 3 (P6.1–P6.3) | C5 — relational composition | HDC value vs graph traversal clear |
| **P7** | 5 | 3 (P7.1–P7.3) | C6 — continual updates | Update interference characterized |
| **P8** | 6 | 4 (P8.1–P8.4) | Confirmatory C2–C6 (≥10 seeds) | Full uncertainty-quantified results |
| **P9** | 7 + 8 | 3 (P9.1–P9.3) | C7 integration + closeout | Final report + HDC closure sign-off |

---

## Phase 1 — Foundation & Smoke (Matrix Stages 0 + 1)

> **Goal:** Verify the environment, tooling, and end-to-end pipeline before any scientific measurement. No verdict.

### P1.1 — Environment Manifest

- Pin and record: Python version, NumPy version, PyTorch version, Torchhd version (if installed), OS, CPU model + core count, RAM total, GPU model + VRAM (if any).
- Record thread control strategy (single-threaded for reproducibility; 12-thread for throughput measurement).
- Record device/backend (CPU vs GPU), batch size policy.
- Archive prior results: `results_hdc_tierA.json`, `results_realdata_rows.jsonl`, `rows_smoke.jsonl`, `rows_run.jsonl`.
- Create `manifest.json` in `Zog Zoo Dev\results\`.

**Deliverable:** `results\manifest.json`

### P1.2 — Torchhd Install & Convention Verification

- Install `torchhd` (verify compatibility with Python 3.14 + PyTorch version).
- Import test: `import torchhd; print(torchhd.__version__)`.
- Generate one random BSC vector (D=512). Run bind(XOR) + unbind(XOR) in Torchhd. Confirm exact roundtrip.
- Generate one random MAP vector (D=512). Run bind(mul) + unbind(mul). Confirm exact roundtrip.
- Generate one random HRR vector (D=512). Run circular conv + correlation unbind. Record error magnitude.
- Generate one random FHRR vector (D=512). Run complex mul + conjugate unbind. Record error magnitude.
- Document: FFT scaling convention, normalization policy, dtype handling, bundle/tie-breaking rule.

**Deliverable:** `results\torchhd_conventions.json` + notes in `results\manifest.json`

### P1.3 — Smoke C1 (Algebraic)

- BSC + MAP at D=512, 1 seed, 100 pairs.
- Tests: isolated bind/unbind roundtrip, identity element, reproducibility (run twice in same process + separate process).
- Write JSONL rows with `phase: "smoke"`, `category: "C1"`.

**Deliverable:** `results\smoke_c1.jsonl`

### P1.4 — Smoke C2 (Capacity)

- MAP at D=512, N=50 role-value pairs, V=100 candidates.
- Pipeline: encode 50 pairs → bundle → query 20 roles → cleanup against V=100 → measure top-1/top-5.
- Write JSONL rows with `phase: "smoke"`, `category: "C2"`.

**Deliverable:** `results\smoke_c2.jsonl`

### P1.5 — Smoke C6 (Updates)

- MAP accumulator at D=512.
- 10 inserts, 5 updates (replace value), 5 deletes (if supported; otherwise document limitation).
- After each batch, query all live items + a random sample of deleted items. Verify live=correct, deleted=absent.
- Write JSONL rows with `phase: "smoke"`, `category: "C6"`.

**Deliverable:** `results\smoke_c6.jsonl`

### P1.6 — Smoke C4/C5 (Structure + Relations)

- C4: 3-permutation discrimination task (ABC / ACB / CBA) using BSC position binding at D=512. 1 seed. Verify top-1 distinguishes all 3.
- C5: 2-hop chain A→B→C using stored (subject, relation, object) triples. Query "what is C related to A via B?" Verify correct retrieval.
- Write JSONL rows with `phase: "smoke"`, `category: "C4"` / `"C5"`.

**Deliverable:** `results\smoke_c4c5.jsonl`

### Phase 1 Gate

- All 6 JSONL files exist.
- All rows have `status: "ok"` (or documented `error` with explanation for known limitations).
- No scientific verdict. The gate is: **pipeline works end-to-end, JSONL serializes correctly, results are recoverable after interrupted process.**

---

## Phase 2 — C1 Hard Gate (Matrix Stage 2)

> **Goal:** Validate algebraic correctness for all 4 VSAs. This is a **mandatory gate** — no downstream capacity/noise/structure tests are interpretable for a VSA that fails its algebra.

### P2.1 — C1.1: Isolated Bind/Unbind (All 4 VSAs)

- VSAs: BSC, MAP, HRR, FHRR.
- D: 512, 1024.
- Pairs: up to 10,000 per configuration.
- BSC: XOR bind, XOR unbind → expect **exact** (bitwise identity).
- MAP: mul bind, mul unbind → expect **exact** (bitwise identity on ±1).
- HRR: circular convolution bind, correlation unbind → record **distribution of cosine error** (not exact by construction).
- FHRR: complex mul bind, conjugate unbind → expect within **floating-point tolerance** for unit phases.
- 1 seed (algebraic tests are seed-independent; use seed for vector generation only).

**Deliverable:** `results\c1_bindunbind.jsonl`

### P2.2 — C1.2: Mathematical Invariants

- Identity element (bind with identity = identity for each VSA).
- Commutativity where defined (BSC XOR is commutative; HRR convolution is commutative; MAP mul is commutative; FHRR mul is commutative).
- Associativity where defined.
- Self-inverse rules (BSC: XOR is self-inverse; MAP: mul is self-inverse; FHRR: conjugate is inverse).
- Similarity preservation: bind a fixed vector to N random vectors; measure pairwise similarity distribution vs original.
- Report documented exceptions (e.g., HRR unbind is approximate, not exact inverse).

**Deliverable:** `results\c1_invariants.jsonl`

### P2.3 — C1.3 + C1.4: Permutation/Role Order + Distribution Sanity

- C1.3: Forward/inverse permutation roundtrip. Verify permuting ≠ reversing (not accidentally identical). Characterize random-vector similarity under permutation.
- C1.4: Pairwise similarity histograms over D ∈ {512, 1024, 4096} and 5 seeds. Report mean, SD, tails. Compare to theoretical reference (e.g., BSC expected |cos| ≈ 1/√D).

**Deliverable:** `results\c1_perm_dist.jsonl`

### P2.4 — C1.5: Reproducibility

- Same fixed input vectors (hardcoded seed).
- Run 1: in-process, 3 repeated calls. Verify bitwise identical output.
- Run 2: separate Python process (spawn subprocess). Verify bitwise identical output.
- Canonical serialization (JSON with sorted keys) + SHA-256 hash of serialized output.
- Record hash in JSONL.

**Deliverable:** `results\c1_repro.jsonl`

### P2.5 — C1.6: Torchhd Cross-Library Equivalence

- Sample vectors **once** (fixed seed), pass the **same values** to both our implementation and Torchhd.
- BSC: bitwise equality on bind/unbind.
- MAP: bitwise equality on bind/unbind.
- HRR: record max/mean absolute AND relative error. Pre-declare tolerance (e.g., 1e-6 for float32).
- FHRR: record max/mean absolute AND relative error. Pre-declare tolerance.
- **If mismatch:** trigger convention audit (FFT scaling, normalization, operand order, dtype). Document resolution. Do NOT auto-fail.

**Deliverable:** `results\c1_torchhd.jsonl`

### P2.6 — C1.7 + C1.8: BSC↔MAP Correspondence + Bundle Interference

- C1.7: Map bits to signs (0→−1, 1→+1). Verify XOR ≡ multiplication on same operands. Inverse agreement.
- C1.8: Bundle 1, 2, 4, 8, 16, 32, 64, 128 pairs. Measure unbind accuracy after bundling. Characterize interference growth. (No exactness claim — this is a characterization, not a pass/fail.)

**Deliverable:** `results\c1_bsc_map_bundle.jsonl`

### Phase 2 Gate (HARD)

- All 4 VSAs pass their **required** algebraic properties for their representation type.
  - BSC: XOR exact, self-inverse.
  - MAP: mul exact, self-inverse.
  - HRR: conv/correlation within declared tolerance.
  - FHRR: complex mul/conjugate within declared tolerance.
- Torchhd cross-validation: no unexplained mismatches beyond convention differences (documented).
- **If a VSA fails:** archive failure, fix implementation, rerun with new code hash. Do NOT proceed to Phase 3 with a failing VSA.

---

## Phase 3 — C2 Capacity Pilot (Matrix Stage 3a)

> **Goal:** Measure how many role-value associations survive bundling, with baselines.

### P3.1 — C2.1: Role-Value Storage Sweep

- VSAs: all 4 (those passing Phase 2).
- D: {512, 1024} (pilot; 4096/10000 in Phase 8 confirmatory).
- N sweep: 50, 100, 500, 1,000, 5,000, 10,000 (geometric, extend until recovery < 10% or resource cap).
- V (cleanup candidate set): 1,000.
- 5 seeds.
- Metrics: top-1, top-5, N90, N99 (largest N with ≥90%/99% recovery), bits per correctly retrievable pair.
- Mark out-of-range as **censored**, not zero.

**Deliverable:** `results\c2_capacity.jsonl`

### P3.2 — C2.4: Matched-Memory Baselines

- For each VSA × D combination:
  - Exact Python dict (key=role vector hash, value=value vector).
  - Bounded hash table with collision handling (same byte budget as HDC bundle).
  - Stored key/value vector nearest-neighbor index (same total bytes).
- Enforce same allowed record information and memory budget.
- Report: bits per correctly recoverable association, hash collisions, p95 latency.

**Deliverable:** `results\c2_matched.jsonl`

### P3.3 — C2.5: Cleanup Dependence

- Three modes per VSA × D:
  1. **Oracle cleanup** (diagnostic only — full codebook available).
  2. **Stored codebook** (codebook bytes counted in memory).
  3. **Regenerated codebook** (seed stored, codebook recomputed; generation time counted).
- Report accuracy + time separately for each mode.
- **Never** use uncounted oracle in headline comparisons.

**Deliverable:** `results\c2_cleanup.jsonl`

### Phase 3 Gate

- Feasible grid identified: which (VSA, D, N) combinations complete within declared memory/time limits.
- Baselines established: dict/hash/NN numbers available for comparison.
- N90/N99 computed for each VSA at D=512 and D=1024.

---

## Phase 4 — C3 Noise Pilot (Matrix Stage 3b)

> **Goal:** Measure corruption/erasure/interference tolerance under per-architecture native noise models.

### P4.1 — C3.1: Stored-Memory Corruption

- VSAs: all passing Phase 2.
- Load: N ≈ 0.5 × N99 (per-architecture, from P3.1).
- Corruption levels p: {0%, 1%, 2%, 5%, 10%, 20%, 30%, 40%} of components.
- **Per-architecture native noise models:**
  - BSC: random bit flips.
  - MAP: random sign flips.
  - HRR: (a) Gaussian noise (σ = p × original magnitude), (b) component replacement with random values.
  - FHRR: (a) phase jitter (uniform ±p×π), (b) random phase replacement.
- 5 seeds.
- Metrics: accuracy vs p, retained performance ratio (accuracy_at_p / accuracy_clean), effective pre/post corruption similarity.

**Deliverable:** `results\c3_corruption.jsonl`

### P4.2 — C3.2 + C3.3: Query Corruption + Bundle Interference

- C3.2: Damage query role components. Erasure levels: 10%, 25%, 50% of role components masked/erased.
- C3.3: Add unrelated role-value pairs (distractors) while preserving declared memory budget. Measure degradation vs clutter count.

**Deliverable:** `results\c3_query_interf.jsonl`

### P4.3 — C3.6: Fair Baselines

- Exact lookup (dict) with corrupted key → measure failure rate.
- Partial/noisy-key approximate lookup (same corruption level).
- ECC/replication with same **resident-byte budget**:
  - Replicate each vector 2× or 3×.
  - Apply same corruption; decode via majority vote or Hamming correction.
- Report: checksum/decoder failures, loss of relationship vs loss of container.

**Deliverable:** `results\c3_baselines.jsonl`

### Phase 4 Gate

- Noise curves characterized for all 4 VSAs at native noise models.
- Matched-baseline comparison available (ECC/replication at same byte budget).
- Clear statement: where HDC adds robustness value, where ECC/replication matches or beats it.

---

## Phase 5 — C4 Compositional Structure Pilot (Matrix Stage 4a)

> **Goal:** Test whether HDC's binding/superposition distinguishes order, roles, and tree shape better than bag-of-symbols.

### P5.1 — C4.1: Order and Roles

- Permutations with identical symbols: ABC / ACB / CBA (and 4! = 24 permutations for K=20).
- Role encoding: (Rocio, commands, Lu) vs (Lu, commands, Rocio).
- Hierarchical: ((A B) C) vs (A (B C)).
- K ∈ {5, 10, 20} confusables.
- VSAs: all 4. D: {512, 1024, 4096}. 5 seeds.
- Metrics: K-way accuracy, confusion matrix, noise robustness (10% bit/component flip on query), cost.

**Deliverable:** `results\c4_order.jsonl`

### P5.2 — C4.2 + C4.3: Graded Similarity + Incomplete Cues

- C4.2: Generate 1-edit, 2-edit, 3-edit structure changes (swap, insert, delete a symbol). Measure rank correlation with edit distance.
- C4.3: Omit 1 or 2 structure slots. Attempt top-k retrieval from S stored records (S=100, 500, 2000). Compare unknown placeholders vs genuinely absent slots.

**Deliverable:** `results\c4_sim_cues.jsonl`

### P5.3 — C4.4: Baselines

- **Bag-of-symbols:** orderless set comparison (should be at chance on permutations).
- **N-gram overlap:** 1-gram (bag) vs 2-gram vs 3-gram sequence comparison.
- **Canonical-form exact dict:** perfect on complete clean keys (upper bound).
- **Tree edit distance** (if computable at scale): structural edit metric.
- Report where each baseline sits relative to HDC.

**Deliverable:** `results\c4_baselines.jsonl`

### Phase 5 Gate

- HDC's structural advantage (or lack thereof) over bag-of-symbols is quantified.
- Confusion matrices available for K=5, 10, 20.
- Clear statement: in which regimes (D, K, noise) does HDC's compositional binding add value over flat comparison?

---

## Phase 6 — C5 Relational Composition Pilot (Matrix Stage 4b)

> **Goal:** Test multi-hop retrieval and rule-based inference. Identify where HDC adds value vs graph traversal.

### P6.1 — C5.1 + C5.2: Fact Retrieval + Multi-Hop

- C5.1: Store (subject, relation, object) triples. Query direct relation. Measure accuracy + cleanup false positives.
- C5.2: Compose r2(r1(entity)) across depths 1–6.
  - With cleanup between hops.
  - Without cleanup (error propagation).
  - Measure: accuracy vs hop depth, latency per hop, codebook cost.

**Deliverable:** `results\c5_facts_hops.jsonl`

### P6.2 — C5.3 + C5.4: Rule Inference + CLUTRR-Style

- C5.3: Apply supplied rule: `parent(A,B) & parent(B,C) → grandparent(A,C)`. Separate memory retrieval from rule execution.
- C5.4: Generate CLUTRR-style synthetic kinship chains (2–8 hops, systematic generalization). Use structured relations (no natural language parsing).
- VSAs: all 4. D: {512, 1024}. 5 seeds.

**Deliverable:** `results\c5_rules_clutrr.jsonl`

### P6.3 — C5.6: Baselines

- **Adjacency list + BFS/DFS:** exact graph traversal (upper bound on clean data).
- **Symbolic rule engine:** explicit rule matching on stored facts.
- **Imperfect graph matching:** add noise to stored edges; measure degradation.
- Report: accuracy + cost for complete vs incomplete data.

**Deliverable:** `results\c5_baselines.jsonl`

### Phase 6 Gate

- Where HDC adds value vs graph traversal is clear (expected: HDC wins on noisy/approximate; graph wins on exact/complete).
- Multi-hop error propagation characterized.
- Rule inference separated from memory retrieval.

---

## Phase 7 — C6 Continual Updates Pilot (Matrix Stage 5)

> **Goal:** Test insert/update/delete under two modes: full reversible accumulator vs compact/finalized.

### P7.1 — C6.1–C6.3: Basic Insert/Update/Delete (1k ops)

- Two modes:
  - **(A) Full reversible accumulator:** all state preserved (counter arrays, old-value sidecars).
  - **(B) Finalized compact:** majority vote / phase normalization after each batch.
- 1,000 operations: 500 inserts, 250 updates, 250 deletes.
- After each batch of 100 ops: query all live items + random sample of deleted/never-stored items.
- VSAs: all 4. D: {512, 1024}. 5 seeds.
- Metrics: live-item recall, false positives, sidecar bytes, p95 latency per op.

**Deliverable:** `results\c6_basic.jsonl`

### P7.2 — C6.4: Churn (10k ops)

- 10,000 operations: 50% inserts, 25% updates, 25% deletes.
- Active working set maintained near 0.5 × N99.
- Checkpoints at 1k, 5k, 10k.
- Measure: accuracy over time, drift vs control (no-op run), failure type, p95 per-op latency.
- VSAs: all 4. D: {512, 1024}. 3 seeds (10k ops is expensive; 5 in Phase 8).

**Deliverable:** `results\c6_churn.jsonl`

### P7.3 — C6.5 + C6.6: Persistence + Baselines

- C6.5: Serialize state → kill process → reload → continue same operation stream. Verify equivalence to uninterrupted run. Report file size, recovery time.
- C6.6: In-memory dict + SQLite (report durability mode/transaction policy). Same operation stream. Throughput, latency, peak resident bytes, bytes modified.

**Deliverable:** `results\c6_persist_baseline.jsonl`

### Phase 7 Gate

- Update interference characterized for full vs compact modes.
- Deletion support (or lack thereof) documented per VSA.
- Baseline comparison (dict/SQLite) available.
- Clear statement: which mode (full/compact) is viable, at what cost.

---

## Phase 8 — Confirmatory Runs (Matrix Stage 6)

> **Goal:** Replicate pilot findings with full D grid and ≥10 seeds for statistical confidence.

### P8.1 — C2 + C3 Confirmatory

- Full D grid: {512, 1024, 4096, 10,000}.
- ≥10 independent seeds.
- Full N sweep (C2) and full p sweep (C3) as feasible within resource caps.
- Matched-memory baselines at all D points.
- Report: mean ± SD, median, 95% CI (bootstrap at seed level), paired contrasts.

**Deliverable:** `results\c2c3_confirm.jsonl`

### P8.2 — C4 + C5 Confirmatory

- Full D grid: {512, 1024, 4096}.
- ≥10 seeds.
- Full K sweep (C4) and hop-depth sweep (C5).
- All baselines.

**Deliverable:** `results\c4c5_confirm.jsonl`

### P8.3 — C6 Confirmatory

- 100k operations if feasible (time/memory permitting).
- ≥10 seeds.
- Both modes (full + compact).

**Deliverable:** `results\c6_confirm.jsonl`

### P8.4 — Statistical Aggregation & Summary

- Aggregate all JSONL → summary tables per (category × VSA × D × seed).
- Compute: mean ± SD, median, 95% CI, effect sizes, paired model contrasts.
- Generate: `summary_all.json` (machine-readable) + human-readable tables.
- Identify decision-boundary cells (where VSA A ≈ VSA B) for targeted re-runs.

**Deliverable:** `results\summary_all.json` + `results\summary_tables.md`

### Phase 8 Gate

- Full uncertainty-quantified results for C2–C6.
- Capability-specific verdict per category (not a single "HDC GO/NO-GO").
- All decision-boundary cells resolved or documented as exploratory.

---

## Phase 9 — C7 Integration + Closeout (Matrix Stages 7 + 8)

> **Goal:** Test whether HDC memory helps the actual MyAI agent. Then close out.

### P9.1 — C7 Arms (T0–T4)

- Entry gate: C1 validated; C2–C6 written up; select ≤2 promising HDC variants WITHOUT peeking at reserved eval set.
- Arms:
  - **T0:** Transformer only (no external memory).
  - **T1:** Transformer + SQLite key-value memory.
  - **T2:** Transformer + standard vector retrieval.
  - **T3:** Transformer + selected HDC memory.
  - **T4 (optional):** Transformer + HDC + vector memory (hybrid complementarity).
- Tasks: stored-fact recall, reversed roles, 2–4 hop queries, noisy cues, updates/retractions, contradictory facts, calibrated abstention.
- Measures: accuracy, hallucinated-answer rate, p50/p95 latency, tokens, total bytes, peak RAM.
- Paired seeds/cases, confidence intervals.

**Deliverable:** `results\c7_integration.jsonl`

### P9.2 — Appendix A (Wikipedia Shards, if requested)

- 5 Parquet shards ingestion throughput.
- Native HDC encoding timing vs reading Cohere embeddings.
- 1-thread vs 12-thread comparison.
- Warm vs cold cache.

**Deliverable:** `results\appendix_a.jsonl`

### P9.3 — Final Deliverables + Closeout

- Machine-readable run table (all JSONL consolidated).
- Six-category scientific summary (C1–C6).
- One-page architecture/cost tradeoff.
- Separate MyAI integration result (C7).
- Owner writes substantive conclusion (AI does not self-grade).
- Fresh timestamped backup: `backup_YYYYMMDD_HHMMSS\`.
- Update `Progress Report.md` and `Test Rig and Validation Ladder.md` with final verdicts.
- **Owner signs HDC closure** → unfreeze KAN K1.

**Deliverable:** Final report package + backup + updated docs.

---

## Execution Rules

1. **One phase at a time.** After each phase completes, STOP. Report results summary. Wait for owner GO.
2. **No code edits mid-run.** Config fingerprint (`config_fp`) protects comparability.
3. **Resumable.** JSONL is append-only. Restart re-reads file and skips completed cells.
4. **Power-loss safe.** Rows flushed after each cell.
5. **No silent failures.** All errors, OOM, timeouts recorded with status + error message.
6. **No cherry-picking.** All configurations run (or explicitly marked `resource_censored`).
7. **Pre-registered thresholds.** Freezed in this document. Changes require new protocol version.
8. **Credit rule.** HDC results credited to pipeline (algebra + encoding). Baselines credited to their respective methods. Never credit HDC for being a search engine.

---

## Resource Estimates (rough, to be calibrated in Phase 1)

| Phase | Est. time | Peak RAM | Notes |
|-------|----------|---------|-------|
| P1 | 1–2 hrs | <1 GB | Smoke only |
| P2 | 2–4 hrs | <2 GB | 10k pairs × 4 VSAs × 2 D |
| P3 | 4–8 hrs | 2–4 GB | N up to 10k × 5 seeds |
| P4 | 4–8 hrs | 2–4 GB | p up to 40% × 5 seeds |
| P5 | 3–6 hrs | 1–2 GB | K up to 20, S up to 2000 |
| P6 | 3–6 hrs | 1–2 GB | 6 hops, CLUTRR chains |
| P7 | 6–12 hrs | 2–4 GB | 10k ops × 3 seeds |
| P8 | 1–3 days | 4–8 GB | Full grid × 10 seeds |
| P9 | 1–2 days | Variable | Depends on transformer size |

---

## Version History

| Date | Change |
|---|---|
| 2026-10-24 | Initial creation. 9 phases, 37 sub-phases defined from Test Matrix v0.2 §3. |