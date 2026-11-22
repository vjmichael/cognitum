# Zog Zoo — Qwen Follow-Up: Audit, Complete Validation, and BSC-Specific Tests

**Status:** Proposed test plan; no new benchmark results are claimed here.  
**Basis:** `Zog Zoo - Progress Report(1).md`, including §16–§18.6, and HDC Strengths Test Matrix v0.2.  
**Purpose:** Preserve all results, verify uncertain conclusions, and give Binary Spatter Codes (BSC) a fair, independently assessed test program. Keep C7 (hybrid-transformer integration) deferred until an integration environment is available.

## Instructions to Qwen (non-negotiable)

1. **Keep the existing measurements unchanged.** Append new result files with distinct IDs and `backend`, `vsa`, `variant`, `D`, `N`, `V`, `seed`, `config_hash`, `code_version`, `test_id`, `status`, measured metrics, RAM/time, and the data-generator identity. Do not silently change previous pass gates. Snapshot source and results before fixes.
2. **No silent backend fallback.** A custom `zogzoo` test must actually execute the custom implementation, not TorchHD. Assert module identity and trace the functions called. TorchHD is a reference comparison, not a replacement.
3. **Paired trials.** Generate task instances and vectors once, then pass the *same values* to both backends for equivalent operations. Matching seed numbers alone is insufficient. Distinguish legitimately different bundle algorithms explicitly.
4. **Correct terminology:** `0 unhandled errors` means code did not crash; it does **not** mean correct scientific answers. Report `accuracy`, `false positives`, `unsupported`, `timeout`, and `incomplete` separately.
5. **Do not manufacture a BSC win.** BSC may prove weak for dense superposition and still be valuable for compact lookup, noisy matching, online classification, and bitwise computing. Conclude separately for each claim.
6. **Count all memory.** In addition to finalized packed vectors, measure input codebooks, majority-vote counters, cleanup banks, keys/metadata, records required to undo updates, sharding tables, memory-mapped buffers, and peak temporary allocations. Compare both equal D and equal *total resident bytes*.
7. **Five seeds are exploratory, ten or more are preferable for confirmation.** Report per-seed results and uncertainty rather than only means. No cherry-picked seed or threshold.
8. **Report actual CPU thread count, wall time, warm/cold caching, and peak RAM.** On the Ryzen 5 5500 include 1, 6, and 12 threads where useful. Use measured power only if valid instrumentation is available; otherwise omit energy claims.

## A. Validate the new C5/C6 results before assigning production roles

| Priority | ID | Task for Qwen | Expected deliverable / acceptance evidence |
|---|---|---|---|
| P0 | A1 — Fix result accounting | Recompute counts from raw JSONL by `(test, backend, run_id)` and deduplicate. The progress report lists 2,880 core unique configs + 720 added = **3,600 unique configs**, or **7,200 backend measurements**, while its headline says 4,045 / 8,090. Reconcile the 445-config discrepancy or document extra unlisted configurations. | Reconciliation table, raw file names, config fingerprints, total unique runs, counts of `completed`, `error`, `censored`, and `unsupported`. |
| P0 | A2 — Audit C5.2 versus C5.3 | C5.2 reports ~100% on 1–3 hops, but C5.3 drops from ~99.9% first-hop to ~50% for the repeated `parent→parent` rule. Test same-relation and different-relation chains with **identical graph sizes, load, candidate sets, and cleanup policies**. Inspect key collisions, oracle intermediate nodes, ground-truth leakage, and scoring. | Per-hop confusion matrix; traces of sampled successful and failed queries; 1–6 hops; repeated and mixed relations; both backends. Avoid claiming arbitrary-length inference from a three-hop pilot. |
| P0 | A3 — Audit C6.2 untouched-record scores | Explain why `untouched_top1` is approximately **0%, 50%, 99–100%** as N increases 50→100→200 across almost all architectures. Verify the untouched denominator is nonzero and that selected updated and unaffected keys are disjoint. | Counts (`updated_count`, `untouched_count`), score denominators, per-key outcomes and a small hand-verified test. Zero eligible untouched keys must be `N/A`, not zero accuracy. |
| P1 | A4 — Separate rebuilding from real updates | In C6.2 and C6.3, distinguish full rebundling/rebuild after an edit from incremental removal/addition. Show whether each representation can undo a change using its stored accumulator, and whether compact/normalized form cannot. | Side-by-side accuracy, time/op, temporary RAM, retained counter/old-value storage and limitations. |
| P1 | A5 — Real persistence | The screenshot's 'all additional sub-tests complete' lists C5.1, C5.3, C6.3, C6.4. The supplied report does **not** establish C6.5 serialize→terminate→reload→continue. Add that test and compare state hashes and all retrieval answers with uninterrupted control. Inject interrupted saves. | Byte-identical/defined-tolerance continuation where applicable; durable file size; reload latency; crash-safe error reporting. |
| P1 | A6 — Extend churn to original target | C6.4 ran **1,000 operations**, not the planned **100,000**. Keep 1k result as pilot. Run 10k then 100k with correct 50/25/25 valid insert/update/delete schedule and checkpoints. Track fixed/variable active-set sizes, and avoid changing thresholds after pilot. | Accuracy, false positives, survivor retention, drift and update latency at each checkpoint; explicit resource cap if full run cannot finish. |
| P1 | A7 — Verify missing C5 tasks | The provided report does not show C5.4 (CLUTRR/structured kinship) or C5.5 (held-out analogy/transfer). Do not mark those as complete without run IDs. Test with structured input and known transforms rather than language extraction. | Per-hop kinship accuracy, held-out analogy accuracy, exact graph/symbolic baseline, memory/latency. |
| P1 | A8 — Cross-backend discrepancies | Investigate FHRR C2 at D4096/N500 (**64.4% ZogZoo vs 79.1% TorchHD**), MAP C2 at N500, and TorchHD HRR C1.1 error. For each, test truly identical vectors, native bundling semantics, normalization, cleanup and inverse conventions. | Matched-input difference report and corrected attribution; do not label a 15-point accuracy difference 'equivalent' without analysis. |
| P2 | A9 — Fair scale and cost study | Refine N99/N90 instead of reporting only N=50 or N=100 from a coarse grid. Explore D=10k and 20k in a *targeted* sweep if feasible, and V=100/1k/10k separately. | Accuracy curves with uncertainty; total operational bytes; p50/p95 query and update time; capped/censored cases. |

### A2 special control — diagnose the same-relation rule collapse

Construct two directed graphs with the same nodes, edges, size, degree distribution and answer ambiguity. In one, a two-hop question uses `r1` then `r2`. In the other it uses `parent` then `parent`. Use distinct fields for **edge type, source, destination, and hop position**; test role-/direction-tagged keys and cleanup after each hop. Compare against exact graph traversal. A repeated relation is not inherently impossible for HDC: a 50% failure may be a limitation of this encoding, key schema or cleanup policy, not an intrinsic prohibition on multihop reasoning. Do not improve the score by letting the retrieval procedure peek at the gold intermediate answer.

### A4 special control — why this matters

Deletion-by-rebuild can produce excellent correctness and low false-positive rates, but it does **not** measure affordable online deletion. Likewise, a compact finalized majority/phase bundle can discard information needed to undo additions. Measure compact-only, counter/accumulator-retaining, and rebuild approaches as different systems.

## B. BSC-specific benchmark suite — do not reuse the flawed assumption that 'XOR everything' is proper BSC bundling

### B0 — Representation audit / correctness hard gate

**Definition:** Binary Spatter Codes (BSC) have binary `{0,1}` hypervectors; binding is bitwise XOR; canonical bundling across multiple vectors is **coordinate-wise majority vote with explicit tie policy**; cleanup can use Hamming similarity. XOR-reducing all stored items is a parity combination, **not majority bundling**. Both have uses, but must never be reported as the same operation.

Test: (i) `unbind(bind(a,b),a)==b` exactly; (ii) XOR identity/self-inverse; (iii) permutation inverse; (iv) randomized and deterministic ties; (v) bit-packed/unpacked numerical equivalence; (vi) reproducibility across processes; (vii) hand-made 8-bit and 16-bit majority examples. **Do not start downstream BSC claims until the audit passes.**

**Cross-check with MAP:** Map each bit `b` to `(-1)^b`. Then BSC XOR binding maps exactly to bipolar elementwise multiplication, and BSC majority vote maps to the sign of the bipolar sum **under the same tie policy and source hypervectors**. This is a powerful property test. If equivalent BSC and MAP majority-vote trials disagree, investigate implementation/scoring before ranking the architectures. Do not compare compact majority BSC against MAP's full-precision unthresholded accumulator without labeling different information retention.

### B1 — Correct bundled associative capacity

Use unique role–value pairs and a fixed cleanup vocabulary. For D `{512,1024,4096,10000,20000}` and pilot N `{1,3,5,10,25,50,100,200,500,1000}`, run 5 paired seeds; extend to 10+ after pilot, narrow near 90%/99% boundaries. Hold V=1,000 first; vary V later. Evaluate variants separately:

- `bsc_majority_global`: majority across all bound pairs with deterministic or seeded tie-breaking; finalized `D` packed bits.
- `bsc_majority_sequential`: successive pairwise bundle operations; **diagnostic** for known order-dependent information loss; do not treat as equivalent to global majority.
- `bsc_counter`: retain per-bit vote counts, threshold only at retrieval; count counter bytes.
- `bsc_xor_parity`: XOR over every stored binding as a **negative/control encoding**, not the canonical bundle.
- `map_sign_majority`: sign-mapped cross-check with identical input vectors.

Report top-1/top-5, N90/N99 with uncertainty, collision/tie rate, false positives, codebook size, finalized and resident bytes, and lookup speed. Don't assume D20k wins; characterize the cost curve.

### B2 — Noisy and incomplete cues

Corrupt **the query** and **the stored memory** independently with bit flips p=`{0,1,2,5,10,20,30,40}%`; then test masked unknown bits at `{10,25,50}%`. Use a masked Hamming metric for erasures (otherwise erasure vs flip is confounded). Separate memory-corruption before/after bundling; test a fixed common N and N normalized by each method's own measured N99. Compare to exact-match dictionary, approximate Hamming lookup, and a comparable-budget ECC-protected store. Report clean accuracy, retained percentage, false-positive rate, abstention and measured pre/post corruption similarity.

### B3 — Ordering, role labels, and structural composition

Encode ordered pairs and short sequences with reversible permutation/role tags: `ABC/ACB/CBA`, `Rocio→Lu / Lu→Rocio`, nested mini-trees, a scene containing the same props in a different spatial arrangement. Include identical bag-of-symbols controls to ensure correct answers depend on order. Test K=5/10/20 confusables; 1–3 roles or slots removed; add noisy cues and repetitions. Report top-1, separation margin, rank, and retrieval cost. Compare against MAP with the **same** bit/sign vectors and a deterministic exact-symbol baseline.

### B4 — Binary prototype classification / online learning

Evaluate a workload for which compact binary hypervectors may be useful, rather than judging BSC solely by dense key–value superposition. Use controlled synthetic sensor/state vectors with held-out prototypes, varying class overlap, imbalance, bit corruption, and number of classes. Optional NVP-like task: classify a known film-production state/event from structured symbolic features (e.g., camera attachment, actor movement, prop interaction)—**not** classify free-form language without a separate encoder. Train via majority prototypes, then implement prediction/error-driven corrections with retained vote counters. Compare with nearest neighbor over packed bits, MAP prototype encoding, and a simple conventional classifier. Measure accuracy vs size, update speed, peak RAM, and forgetting after distribution shifts. Do not claim a learning advantage without a held-out dataset.

### B5 — Sharding and sparse distributed / addressable memory

Compare one overloaded BSC majority bundle against k independently addressable shards and (as a distinct method) a sparse distributed memory / addressable binary-memory scheme with explicit addresses and counters. Use the same total **resident** memory budget for all arms, including shard metadata and address storage. Test clean and 20% bit-flipped cues, N growing beyond a single bundle's capacity, and update/delete support. Report top-1/top-k, miss rate, p95 lookup and actual memory. Attribute gains to sharding or the selected memory algorithm, not 'BSC algebra' alone.

### B6 — Bit-packed CPU efficiency and bandwidth

Implement optimized packed `XOR`, `popcount`, permutation and Hamming cleanup using a clearly documented backend; cross-validate against unpacked BSC. Compare `packed 1-bit`, `byte/bool`, and MAP sign data with correct counter accounting. Use the Ryzen 5 5500 with 1/6/12 threads (pin and document library thread behavior). Measure cold/warm cache, queries/sec, insert/update latency, peak RSS, and end-to-end task latency **including cleanup-bank scans**. For fair energy analysis, use a wall meter and report joules/completed correct result; do not infer energy from TDP or elapsed time. Also compare to a conventional packed-bit similarity index to isolate what, if anything, HDC adds.

### B7 — Continual learning / deletion / persistence

For BSC, compare:

1. **Compact-only finalized majority** (limitations of in-place exact deletions made explicit).
2. **Full vote counters + old-item metadata** (replace/delete by counter subtraction/addition, then rethreshold for lookup).
3. **Full rebuild on each revision** (correctness reference, with measured cost).

Run 1k → 10k → 100k operations where feasible with 50% insert, 25% update, 25% delete, reproducible valid key selection and controlled active-set size. Interleave serialization/restart at predetermined checkpoints. Compare to SQLite and a packed-binary retrieval index, measuring memory, correct live/deleted status, precision, latency, recovery equivalence and storage durability.

### B8 — Optional NVP/MyAI task-level demonstration (NOT C7)

Encode a small **structured** scene roster with actors, prop ownership, parent/child attachments and location changes. Ask noisy partial-cue questions; update wardrobe/prop states and retrieve changed items. Keep exact scene state in SQLite, use BSC only as an auxiliary lookup or compositional encoding. Compare BSC, MAP, FHRR, exact lookup, and Hamming NN at matched storage/retrieval budgets. This is an integration *prototype*, not evidence of improved transformer reasoning. C7 remains deferred.

## C. Run order and stopping rules

1. **First:** A1, A2, A3, and B0. These are correctness blockers; don't spend days on scalability until they are resolved.
2. **Then:** A4–A8 and B1–B3 (small pilots), independent scripts and run IDs. Document whether C5.4/C5.5/C6.5 actually exist; don't silently infer they passed.
3. **Next:** B4–B7 only if the representation/controls are validated. Optimize packed operations only after a correct unpacked oracle works.
4. **Finally:** A9 and B8, if measured value justifies the computation. Keep C7 deferred.

**Proposed decision criteria, preregister before confirmatory runs:**
- **Correctness:** 100% hand-oracle XOR/permutation tests and correct BSC↔MAP bit/sign correspondence under identical variants; no silent backend fallback.
- **Associative capacity:** report N90/N99 with uncertainty and honest censoring; no arbitrary requirement to beat FHRR in raw top-1 accuracy.
- **Efficiency:** evaluate *correct associations retrieved per MiB* and correct queries/sec, not just average accuracy; compare total resident bytes, not only packed final HVs.
- **Continual learning:** accuracy, false positives, and memory/latency under each update mode, including 100k checkpoint or predeclared resource cap. An immutable compact bundle cannot be assumed to support reversible updates.
- **Disposition:** 'BSC rejected for dense bundled associative capacity' may be warranted; 'BSC useless for MyAI' requires failure on its other relevant, fairly evaluated roles too.

## D. Qwen's deliverables

- `audit_findings.md`: discrepancy register, original and adjusted conclusions, and which claims remain unverified.
- `audit_results.jsonl`: append-only targeted C5/C6 reproducibility and stress tests.
- `bsc_test_manifest.json`: frozen definitions, variants, seeds, D/N/V grids, memory budgets and code revision.
- `bsc_results.jsonl`: each test cell with backend and *actual implementation* IDs.
- `bsc_summary.md`: accuracy/capacity curves, confidence intervals, equal-memory tables, efficiency results, and a recommendation **by task**, not a single universal ranking.
- `open_issues.md`: unresolved software defects, methods needing different variants, and deferred C7 dependencies.

**Scientific conclusion to preserve unless the new data changes it:** FHRR leads the previously tested bundled-memory/noise configurations. The new C5.3 and C6.4 results warn against claiming mature multi-hop reasoning or production-grade continual memory. BSC deserves a correctly implemented and fairly attributed specialized evaluation before broad exclusion.