# Zog Zoo — HDC Strengths Test Matrix

**Version:** 0.2 — revised preregistration candidate  
**Date:** 2026-10-24  
**Status:** REVIEW BEFORE FIRST RUN. Freeze the final thresholds, software versions, and experiment manifest in Git before gathering confirmatory results.  
**Owner:** Project owner  
**Implementer:** Qwen (implementation, tests, measurements, mechanically generated reports; not the scientific verdict)

**Purpose:** Determine where hyperdimensional computing / vector symbolic architectures (HDC/VSA) provide useful algebraic, associative, compositional, robustness, memory, or efficiency capabilities—and whether those capabilities improve a hybrid transformer agent such as MyAI. This is **not** an attempt to beat pretrained semantic embeddings or BM25 at raw text retrieval.

**Relationship to prior work:** Revises `Zog_Zoo_HDC_Strengths_Test_Matrix.md` v0.1 using the owner's `New Test Methodology-10232026.txt` and methodological review. Preserve earlier BEIR/NFCorpus/SciFact/FiQA/SQuAD2 results as a **partial, exploratory retrieval track**; they are not a completed proof that lexical HDC is useless. Wikipedia Parquet scalability remains separate (Appendix A).

---

## 0. Rules, scope, and experimental definitions

1. **Pre-register.** Save this document and a machine-readable manifest with a Git commit hash before confirmatory runs. Mark pilot/diagnostic work distinctly. Never adjust thresholds after seeing confirmatory outcomes without creating a new protocol version.
2. **Primary architectures:** MAP (bipolar), BSC (binary), HRR (real circular convolution), FHRR (complex phase). Do not substitute one encoder or bundling rule for another without naming the variant. GHRR, sparse block codes (including B-SBC), and TrainableHD-style training are **not part of the core comparison**; consider them in a later research phase after the baseline is established.
3. **Dimension sweep:** `D = {512, 1024, 4096, 10000}` for applicable models. Run a small smoke configuration first (`D=512`, one seed, small codebook/load). Allow a documented, pre-specified resource cap to prevent OOM; record skipped combinations rather than silently dropping them.
4. **Seeds and uncertainty:** use at least **5 independent codebook/data seeds in the pilot**. Use **10 or more** for the confirmatory comparisons if practical, especially near a decision boundary. Keep each seed's results. Report mean, SD, median, individual seeds, and 95% intervals; describe five-seed intervals as exploratory. Use paired runs on the *same generated task instances* for all models; bootstrap at the seed/problem-family level rather than treating thousands of correlated queries from one codebook as independent replicates.
5. **Two comparison lenses:** (a) same `D` to study representation behavior; (b) **matched total memory bytes** to study engineering value. Do not imply equal D means equal storage. Also compare at fixed latency/energy budgets where measured.
6. **Baselines:** exact Python dictionary/SQLite or canonical graph where appropriate; a constrained-memory or error-protected alternative; simple structural baselines such as bag-of-symbols or n-gram comparison where applicable. Record where a baseline is irrelevant instead of mechanically inserting it into every test.
7. **Memory accounting:** publish both *representation-only* bytes and *total operational resident* bytes. The latter includes codebooks/role vectors, accumulators, lookup indexes, cleanup codebooks, hash metadata, record payloads, sidecars needed for update/delete, and required working state. Also report peak allocation/temporary buffers separately. A deterministic regenerated codebook uses little stored memory but **its generation time and seed/metadata are counted**. Do not grant HDC a free external oracle or a free value codebook.
8. **Separate operations from encoders:** disclose elementary vector sampling, role/position encoding, bundling, thresholding/normalization, binding, inverse/unbinding, cleanup, and retrieval policy. Compare like-for-like task information; algorithms requiring a learned encoder must be a separate experimental arm.
9. **Failure handling:** no silent repairs, no removal of bad seeds, no manual selection of successful output. Append-only JSONL; checkpoint and resume safely after interruption, with deduplication keyed by run ID. Preserve unsuccessful, timed-out, and OOM runs with statuses.
10. **Hardware and power:** record CPU threads, physical device/backend, RAM/VRAM, batch sizes, warm/cold caches, synchronization, and wall time. CPU comparisons use explicitly controlled thread counts (1 versus 12 where supported). GPU results count host↔device transfers. Energy (J/op) is optional and **only** reported if measured with a documented instrument; never infer energy from wall time alone. Runs can be postponed under low battery power without changing the experiment.
11. **Interpretation:** distinguish (i) algebraic validity, (ii) empirical capacity/robustness, (iii) operational efficiency, and (iv) incremental advantage in MyAI. A failure in one category invalidates its specific claim, **not the entire HDC program**.
12. **Scientific roles:** Qwen builds and reports. Owner adjudicates hypotheses/changes and signs the conclusion. AI reviewers may propose changes but do not rewrite registered criteria after results arrive.

### Representation-specific notes to encode in the implementation

| Model | Native binding | Retrieval/updates caveat | Approximate raw vector bytes at D=1,024 |
|---|---|---|---:|
| **BSC** | XOR on binary vectors | Majority-vote bundling and tie-breaking lose information; a packed finalized majority vector cannot simply subtract an old association. Preserve separate accumulator if testing exact deletion. | **128 B** packed (or 1,024 B stored as byte/bool) |
| **MAP** | Componentwise multiplication of ±1 vectors | Exact bind/unbind on isolated bipolar vectors; additive bundle requires a suitable counter accumulator for reversible updates. | **1 KiB** using `int8` (4 KiB if `float32`) |
| **HRR** | Real circular convolution | Correlation/conjugate-spectrum unbinding is generally approximate for ordinary random HRR vectors; document normalization/inverse variants. | **4 KiB** using `float32` |
| **FHRR** | Componentwise multiplication of unit complex phases | Simple pair unbinding by conjugation is exact up to rounding; superposed memories suffer interference. Renormalizing a bundle to unit phases discards information needed for additive reversal. | **8 KiB** using `complex64` |

For matched-memory tests use **actual storage formats**, not these illustrative values. BSC/MAP binding equivalence under bit↔bipolar mapping is a correctness cross-check; bundling and storage are still different design decisions.

---

## 1. Matrix at a glance

| ID | Category | Primary question | Core metrics | Baselines | Decision criterion |
|---|---|---|---|---|---|
| **C1** | Algebraic correctness | Is each implemented operation valid for its specified VSA? | Identity/inverse error, invariants, deterministic reproducibility, cross-implementation differences | Mathematical oracle and Torchhd | **Mandatory validity gate.** Fix deviations before interpreting downstream results. |
| **C2** | Associative capacity | How many role–value associations survive bundling? | Top-1/top-k; N90/N99; bits per correctly retrievable pair; latency | Dict; constrained hash table; stored-vector nearest neighbor | Report capacity and cost tradeoffs; no universal pass threshold. |
| **C3** | Noise and interference | Can HDC recover with damaged memories or cues? | Accuracy-retention curve, interference curve, corruption tolerance at 90% recovery | Dict, approximate matching, dict+ECC/replication at matched memory | Claim advantage only on a **matched fault/budget** with paired uncertainty. |
| **C4** | Compositional structure | Can it distinguish order, roles, and tree shape? | Accuracy against confusables; partial-match recall; similarity ranking | Bag-of-symbols; canonical symbolic representation; n-grams/tree edits | Must beat chance and bag-of-symbols on relevant structure tasks; report cost. |
| **C5** | Relational composition | Can it retrieve chains and apply explicitly specified rules? | Correct answer by hop depth, cleanup dependency, abstention, latency | Graph traversal; rule engine | Keep retrieval, composition, and inference separate; identify where HDC adds value. |
| **C6** | Continual updates | Can it insert, replace, and delete without hidden history? | Current-state correctness, untouched-item retention, cumulative drift, bytes and time/op | Dict/SQLite; alternative index | Evaluate **full accumulator** and **finalized/compact** variants separately. |
| **C7** | Hybrid transformer memory (gated integration) | Does an HDC memory help the *same* local agent? | Task accuracy; recall; abstention; p95 latency; tokens; total memory; update cost | No external memory; SQLite; vector retrieval; HDC | Advance only after C1–C6; value judged on incremental agent results and cost. |

**Exploratory engineering targets, not established facts:** Try C3 accuracy at 10% corruption ≥90% of clean accuracy at 0.5×N99; C4 ≥95% discrimination against 10 confusables; C5 ≥90% at 3 clean hops; C6 ≥95% retention of untouched items after a 100k-operation stress test. Freeze or revise these *before* confirmatory runs; do not let arbitrary thresholds supersede the conventional-baseline comparison.

---

## 2. Detailed test protocols

### C1 — Algebraic correctness (hard gate; no kill rule)

| Test | Procedure | Acceptance / report |
|---|---|---|
| **1.1 Isolated bind/unbind** | For each VSA, generate **identical input hypervectors** for implementation and Torchhd; measure `unbind(bind(a,b),a)` against `b` on up to 10,000 pairs per configuration. | BSC/MAP exact; FHRR within numerical tolerance for unit phases; HRR **distribution of cosine/error** under documented inverse/correlation choice. Don't incorrectly demand exact HRR recovery. |
| **1.2 Mathematical invariants** | Identity, commutativity/associativity where defined, applicable self-inverse rules, similarity preservation under binding with a fixed vector. | Verify only properties actually guaranteed by that representation and normalization. Report documented exceptions. |
| **1.3 Permutation / role order** | Forward/inverse permutation, shifts, role encoding; verify that permuting and reversing are not accidentally identical. | Round-trip exact for pure permutations; characterize empirical random-vector similarity rather than imposing a deterministic `4/sqrt(D)` bound. |
| **1.4 Distribution sanity** | Random-vector pairwise similarity histograms and moments over D and seeds. | Report mean, SD, tails, and theoretical reference where available. |
| **1.5 Reproducibility** | Same fixed vectors/inputs, repeated runs and separate processes; canonical serialization plus hashes. | Identical integer/binary outputs; floating-point repeatability within declared device/precision policy. Cross-device bitwise identity is *not* assumed. |
| **1.6 Cross-library equivalence** | Sample vectors **once**, pass the same values to own code and Torchhd; normalize operand ordering, dtype, FFT scaling, bundle/tie rules, and similarity metric. | Bitwise equality for equivalent integer operations. For floats record max/mean absolute **and relative** errors with operation- and dtype-specific predeclared tolerances. A mismatch first triggers a convention audit—not an automatic bug verdict. |
| **1.7 BSC–MAP correspondence** | Map bits to signs; compare XOR to multiplication and inverse on the same operands. | Exact agreement under the chosen mapping before bundling. |
| **1.8 Bundle interference** | Test unbinding after bundling 1, 2, …, N pairs. | No universal exactness claim; characterize interference before C2. |

**Gate:** Do not proceed to performance/capacity conclusions for an implementation failing a required algebraic property. Archive failures and fixes with separate run IDs.

### C2 — Associative memory capacity

| Test | Procedure | Report |
|---|---|---|
| **2.1 Role–value storage** | Store N distinct role–value pairs in a specified HDC bundle; query by role; cleanup against the same eligible value set. Sweep N geometrically, extend until recovery falls below target or a registered resource cap. | Top-1/top-5 versus N, `N90` and `N99` (largest tested N with ≥90%/99% recovery, plus uncertainty). Mark out-of-range as **censored**, not zero. |
| **2.2 Codebook growth** | `V={100,1k,10k,100k}` candidates, only when memory cap allows; same candidate distribution for baselines. | Recovery versus V, cleanup time, codebook bytes, resident and peak bytes. Explicitly record skipped V/D combinations. |
| **2.3 Memory partitioning** | Compare one bundle with k shards / collections under equal **actual total bytes**, including shard index and codebooks. | Accuracy, latency, total bytes. Account for representation byte-width; don't automatically assume `D/k` means equal memory across VSA types. |
| **2.4 Matched-memory alternatives** | Exact dict, bounded hash table including collision/fingerprint checks, and retained key/value-vector index; enforce the same allowed record information and memory budget. | Bits per **correctly recoverable association**, hash collisions, retrieval throughput and p95 latency. |
| **2.5 Cleanup dependence** | Oracle-cleanup (diagnostic only), realistic stored/regenerated codebook, and approximate cleanup if available. | Report separately. **Never** use uncounted oracle codebooks in headline comparisons. |

**Decision rule:** If an equal-memory hash table dominates exact association storage, close **the claim that HDC is a better exact software key–value store**. Keep testing noisy cues, approximate matching, compression, and composition.

### C3 — Noise, erasure, and interference

| Test | Procedure | Report |
|---|---|---|
| **3.1 Stored-memory corruption** | Run both a **common N across architectures** and a per-architecture capacity-normalized load (`N ≈ 0.5×N99`); corrupt `p={0,1,2,5,10,20,30,40}%` of components under a **named native noise model**. BSC/MAP: flips; HRR: replacement and Gaussian noise (separate); FHRR: phase jitter and random phase replacement (separate). | Accuracy versus p, matched clean baseline, retained performance ratio, effective pre/post corruption similarity. |
| **3.2 Query corruption and erasure** | Damage query role components; separately test masking/erasing 10%, 25%, 50%. | Accuracy/false-positive/abstention versus p and erasure level. |
| **3.3 Bundle interference** | Add unrelated role–value pairs/distractors while preserving fixed or declared memory budget. | Degradation versus clutter and load. |
| **3.4 Component failure** | Stuck-at and dropout fault models; specify whether simulated faults target logical values, memory bytes, or a hardware model. | Accuracy and recovery speed. Avoid calling logical corruption a measured physical failure. |
| **3.5 Matched-signal analysis** | In addition to equal `% components corrupted`, compare at matched measured cosine/correlation loss. | Allows cross-architecture comparison when a bit flip and a phase replacement have unequal effects. |
| **3.6 Fair baselines** | Exact lookup, partial/noisy-key approximate lookup, and ECC or replication with the same **resident-byte budget**, corrupting data/payloads in a controlled manner. | Report checksum/decoder failures; distinguish loss of a serialized file container from loss of stored relationships. |

**Decision rule:** Robustness advantage requires a replicated gain under stated corruption/budget assumptions. If ECC or approximate conventional retrieval matches HDC, close only the corresponding robustness claim.

### C4 — Compositional structure

| Test | Procedure | Report |
|---|---|---|
| **4.1 Order and roles** | Present permutations with identical symbols: `ABC/ACB/CBA`; `A above B / B above A`; `(Rocio, commands, Lu) / (Lu, commands, Rocio)`; distinct hierarchical structures `((A B) C)` / `(A (B C))`. **Use explicit role and position encodings** for applicable VSAs, including commutative binders. | K-way accuracy with `K={5,10,20}`, confusion matrix, noise robustness, cost. |
| **4.2 Graded similarity** | Generate controlled one-, two-, and three-edit structure changes with unambiguous edit definitions and balanced counterexamples. | Rank correlation with edit distance, retrieval accuracy, breakdown by edit type. High correlation is a *hypothesis*, not a guaranteed VSA property. |
| **4.3 Incomplete cues** | Omit one or more structure slots/roles; attempt top-k retrieval from S stored records. Compare unknown placeholders versus genuinely absent slots. | Top-1/top-k versus missing fraction, S, and distractor similarity. |
| **4.4 Baselines** | Bag-of-symbols, n-gram overlap, canonical-form exact dict, and (if allowed) tree edit distance with matched resources. | Bag-of-symbols should be at chance on genuinely indistinguishable permutations; exact canonical lookup should be perfect on complete clean keys. |

**Decision rule:** A structural advantage means recovering information not preserved by bag-of-symbols and/or useful partial-match behavior at a competitive measured cost; it does not require beating an exact structure parser on fully specified clean input.

### C5 — Relational retrieval, composition, and inference

| Test | Procedure | Report |
|---|---|---|
| **5.1 Stored fact retrieval** | Given explicitly encoded `(subject, relation, object)` triples, retrieve a direct relation. Train no text parser in this stage. | Direct-fact accuracy, cleanup false positives, abstention. |
| **5.2 Multihop traversal** | Compose `r2(r1(entity))` across depths 1–6; document precise representation of directed edges. Evaluate with and without cleanup between hops. | Accuracy versus hop depth, error propagation, latency, codebook cost. |
| **5.3 Explicit rule-based inference** | Apply a **supplied** rule such as `parent(A,B) & parent(B,C) → grandparent(A,C)`. Separate retrieving stored facts from executing a rule. | Inferred-answer accuracy; errors from memory versus rule application. |
| **5.4 Structured kinship** | Use CLUTRR **structured relations/graphs if obtainable**; otherwise generate a fully specified synthetic equivalent. Exclude natural-language relation extraction in this test. | Accuracy by hop count, distractors, and relation pattern. |
| **5.5 Transfer/analogy** | Begin with held-out pairs generated by a **shared, explicitly known algebraic transformation**. Only then try learned relations. | Held-out accuracy; do **not** assume that one arbitrary country–capital example can recover unrelated random pairs. |
| **5.6 Baselines** | Explicit adjacency lists, graph traversal, symbolic rules, and (for noise) comparable imperfect-input graph matching. | Accuracy and cost under complete/incomplete data. |

**Decision rule:** On complete, exact data, expect conventional graph traversal and symbolic rule engines to excel. Evaluate HDC as an approximate/memory-constrained component; do not claim HDC inherently performs free-form logical inference.

### C6 — Continual memory updates

**Two mandatory modes:** (A) **full reversible accumulator** with all required state; (B) **finalized compact representation** after quantization, majority vote, or phase normalization. If a mode cannot support exact deletion, classify it as *unsupported without extra state* rather than fabricate subtraction. Count all old-value sidecars, counter arrays, and logs required for reversible updates.

| Test | Procedure | Report |
|---|---|---|
| **6.1 Insert stream** | Insert batches into fixed operating memory; query all live items and a random sample of deleted/never-stored items. | Live-item recall, false positives, capacity, insertion latency. |
| **6.2 Update / replace** | Replace stored `(key, old)` with `(key, new)` using an implementation-valid method; preserve old pair only if its retention is accounted for. | Correct new value, false retrieval of old value, effect on unrelated items, sidecar bytes. |
| **6.3 Delete** | Remove chosen pairs where supported; otherwise measure rebuild/reconstruction cost and declare limitation. | Correct remaining items, deleted-item false positives, deletion latency/bytes. |
| **6.4 Churn** | Registered deterministic sequence: target 100k operations (illustrative mix 50% inserts, 25% updates, 25% deletes) with valid keys. Run 1k and 10k checkpoints first. Manage active working set near 0.5×N99. | Accuracy over time, drift versus control, failure type, p95 per-op latency. |
| **6.5 Persistent recovery** | Serialize, restart process, reload state, continue exactly the same operation stream. | Equivalence to uninterrupted run; file size, recovery time, corruption handling. |
| **6.6 Baselines** | In-memory dict, SQLite (report durability mode/transaction policy), and rebuilt vector index if applicable. | Comparable durability and memory modes; throughput, latency, peak resident bytes, bytes modified. |

**Decision rule:** Repeated errors in untouched records are evidence of update interference for **that storage mode**. Do not generalize a failure of compressed BSC majority bundling to MAP accumulator or vice versa.

### C7 — Hybrid transformer-agent integration (separate, gated stage)

**Entry gate:** C1 validated; C2–C6 results and implementation tradeoffs written up; select at most two promising HDC variants *without peeking at the reserved evaluation set*.

Use the **same** frozen local model, quantization, system prompt, tools except memory, temperature/decoding settings, factual inputs, output schema, and task cases across arms:

| Arm | Memory arrangement | Interpretation |
|---|---|---|
| **T0** | Transformer only, no external memory | Model/context baseline; specify facts supplied in current context. |
| **T1** | Transformer + exact SQLite/structured key–value memory | Exact symbolic lookup baseline. |
| **T2** | Transformer + standard vector retrieval | Approximate semantic retrieval baseline; embedder/model resources counted. |
| **T3** | Transformer + selected HDC associative/structured memory | HDC treatment. |
| **T4 (optional)** | Transformer + hybrid HDC + exact or vector memory | Tests complementarity, **not** the standalone HDC win. |

**Tasks:** stored-fact recall, reversed roles, two- to four-hop relational queries, noisy and incomplete cues, updates/retractions, contradictory facts, and calibrated abstention for genuinely absent facts. Start with structured fact ingestion; evaluate language-to-fact extraction as a separate later test.

**Measures:** exact answer accuracy and hallucinated-answer rate; top-k fact recovery; failure-to-abstain rate; p50/p95 wall-clock latency; preprocessing/ingest/update cost; token usage; total bytes and peak working memory; optional measured joules/query. Keep source facts and retrieval budget identical; prevent the baseline from seeing extra gold facts in the prompt. Run paired seeds/cases and report confidence intervals.

**Decision rule:** Integrate HDC into MyAI if it provides a **replicated practical gain** (quality/robustness at competitive cost, or lower cost at equivalent quality) over the strongest applicable conventional arm. A win over T0 alone is insufficient. A complementary T4 win is still valuable but must be labeled hybrid.

---

## 3. Run plan and checkpoint policy

| Stage | Run | Gate / output |
|---|---|---|
| **0 — Environment & manifest** | Pin package versions and device/backend; record Git commit, datasets/seed plan, data hashes, CPU thread controls, available memory. Archive v0.1 and existing BEIR records. | `manifest.json`; initial run ID; check available battery/power. |
| **1 — Smoke** | C1 at D=512, one seed; C2 at small N and V; C6 ten inserts/updates/deletes; one tiny C4/C5 problem. | Must run end-to-end, serialize JSONL, recover after interrupted process. No scientific verdict. |
| **2 — Reference validation** | C1 all four VSAs, agreed fixed vectors, cross-library tests, declared numeric tolerances. | Hard algebraic correctness gate. |
| **3 — Capacity + noise pilot** | C2 and C3, 5 seeds, subset of D/V/load. | Select feasible grid **before** confirmatory run; compute memory footprint. |
| **4 — Structural and relational pilot** | C4 and C5 on the same 5-seed problem families. | Verify task semantics, no label leaks, calibrated distractors. |
| **5 — Updates pilot** | C6 full vs compact memory, 1k then 10k ops. | Verify accurate live/deleted state; no oracle old values. |
| **6 — Confirmatory strengths** | Pre-registered feasible C2–C6 grid, ideally ≥10 independent seeds. Continue 100k-op C6 where feasible. | Paired results, uncertainty, resource accounting; capability-specific verdict. |
| **7 — Integration** | Gated C7 arms, frozen local transformer, held-out tasks. | Answer whether and how HDC adds value to MyAI. |
| **8 — Independent scaling** | Optional Appendix A (Wikipedia shards; threading/GPU/throughput). | Engineering profile **not** substituted for scientific-capability results. |

**Work/time budget:** No blanket five-day promise. Make Stage 0–2 small, then use observed times to allocate CPU/GPU hours. If power is limited, stop at a checkpoint and resume with identical run IDs/configuration. Heavy confirmatory and GPU jobs may wait for abundant solar/battery reserve. A low-power interruption is **not** a failed scientific result.

**Stop/continue rules:**
- Stop a failing **architecture–operation** pair after verified C1 incompatibility; repair and rerun with new code hash.
- Stop a **specific unsupported claim** (e.g., superior exact key–value density) when a well-matched baseline consistently dominates; keep the measurements.
- Do **not** stop all HDC tests merely because three unrelated categories underperform.
- If a full sweep exceeds the declared runtime/RAM/VRAM limit, label that configuration `resource_censored`; do not cherry-pick faster dimensions.
- Add a new architecture/encoder only in a new protocol revision or separate exploratory track.

---

## 4. Statistical and reporting contract

1. **Independent unit:** codebook/problem-family seed; queries within one seed are correlated. Pair architectures on identical instances and noise masks whenever appropriate.
2. **Report:** per-seed CSV/JSONL, mean ± SD, median, 95% interval and the method used; for paired model contrasts report effect size and paired interval, not just raw ranks. For pilot n=5, label uncertainty estimates exploratory.
3. **Capacity thresholds:** `N90`/`N99` require a clear operational definition (e.g., lower confidence bound versus observed point accuracy). Publish both empirical crossing and interval; mark `not reached` rather than inventing extrapolation. Nonmonotone noisy samples remain in the results.
4. **Hardware and clocks:** wall-clock latency, CPU process time if possible, warm-up iterations, cold/warm cache, GPU synchronization, transfers, and backend. No unsupported GPU speedup claims if the available PyTorch backend cannot run on the R9700.
5. **Failure taxonomy:** algebraic mismatch, bad task data, memory exhaustion, timeout, missing backend, serialization failure, non-reproducibility, and genuine low accuracy. Never silently drop failures.
6. **Result provenance:** frozen input generation code, dataset/version hash, full argument manifest, code revision and experiment ID. State which metrics are exploratory versus confirmatory.
7. **Final deliverables:** machine-readable run table, six-category scientific summary, one page of architecture/cost tradeoffs, and a **separate** MyAI integration result. Owner writes the substantive conclusion.

### Required JSONL shape (one record per measured configuration and seed)

```json
{
  "schema_version": "zog-zoo-hdc-v0.2",
  "run_id": "C2-MAP-D1024-S17-N100-V1000",
  "track": "core_strengths",
  "phase": "pilot",
  "category": "C2",
  "test_id": "2.1",
  "architecture": "MAP",
  "representation": "bipolar_int8",
  "bundle_mode": "int32_accumulator",
  "D": 1024,
  "seed": 17,
  "params": {"N": 100, "V": 1000, "cleanup": "stored_codebook"},
  "task_hash": "sha256:<actual hash>",
  "config_hash": "sha256:<actual hash>",
  "git_commit": "<actual commit>",
  "library_versions": {"python": "<actual version>", "torch": "<actual version>", "torchhd": "<actual version>"},
  "hardware": {"device": "cpu", "threads": 1, "batch_size": 1},
  "metrics": {"top1": null, "top5": null, "n_queries": null},
  "memory_bytes": {"representation": null, "codebooks": null, "metadata": null, "resident_total": null, "peak": null},
  "timing_s": {"encode": null, "query_total": null, "elapsed_total": null},
  "status": "pending",
  "error": null
}
```

Fields containing `<actual ...>` are placeholders in this *schema example only*. A real measured record must replace them with values; metrics and memory/timing fields must not remain `null` for a successful measurement. For failures, `null` is allowed with a status and explanatory error.

---

## 5. Decision matrix (after all relevant runs)

| Evidence | Defensible conclusion | Next action |
|---|---|---|
| Algebra wrong in an architecture | Implementation or specification requires correction. | Fix C1 first; rerun downstream tests affected by the fix. |
| Strong retrieval under clean role–value queries, poor matched-memory efficiency | Useful HDC capability, not a better exact software dictionary. | Retain for relevant compositional/noisy experiments; avoid overclaiming. |
| Higher noise/partial-query recovery at matched quality, bytes, latency | HDC may add approximate/fault-tolerant memory value. | Test in C7 against realistic memory alternatives. |
| Clear role/order/partial-structure advantages versus bag-of-symbols and competitive alternatives | Representation worth integrating for structured cues. | Test real MyAI workflows with matched facts and retrieval budget. |
| Reliable updates only with expensive full accumulators | Updating is feasible but may not justify RAM cost. | Examine append-only/sharded/indexed variants; avoid compact-state claims. |
| C7 T3 or T4 improves practical agent results on held-out tasks | Evidence for HDC or hybrid HDC contribution to MyAI. | Implement an optional backend behind stable interfaces and evaluate operational safety. |
| No advantage after fair C2–C7 comparisons | No demonstrated benefit **for the tested workloads**. | Archive results; defer the relevant backend until new hypotheses justify testing. |

**Never equate:** “FHRR > MAP on BEIR retrieval” with “FHRR is universally superior”; “HDC can bind roles” with “HDC can infer arbitrary logical facts”; or “a simulator performs faster” with “the physical hardware is more energy efficient.”

---

## Appendix A — Wikipedia shard engineering/scalability (independent track)

The owner has five Parquet shards out of the 414-file `wikipedia-2023-11-embed-en-v3-int8-binary` collection. Do not download the remainder for this phase. The supplied Cohere embeddings are **learned-embedding baselines, not native HDC outputs**.

| Measure | Protocol |
|---|---|
| Ingestion | Shards 1–5 incremental; Parquet read throughput, ingest wall time, peak RAM, persisted bytes. |
| Native HDC encoding | Time native encoding separately from reading already-pretrained Cohere embeddings. |
| Scale | Bank growth versus resident memory, disk size, approximate-retrieval quality, p50/p95 query time. |
| Binary storage | Packed BSC versus byte/int8 storage; equal-memory comparisons and exact bit-operation correctness. |
| CPU | 1 versus 12 threads; pin identical input order, batch size and cache state; control library-internal threads. |
| GPU | R9700 only if a verified compatible compute backend exists; report upload/download, synchronization, VRAM and fallback paths. |
| Updating | Append, replace, delete, rebuild/reindex costs; account for sidecars and durable state. |
| Warm versus cold | Separate OS/page-cache and pre-loaded-query measurements; document methodology. |

This appendix is **not a seventh proof of VSA algebra** and must not be conflated with C7 (the transformer-integration study).

## Appendix B — Deferred extensions (future protocol version)

- **Sparse block codes / B-SBC:** compare associative storage and recoverability at matched memory, with suitable cleanup and block-size sweeps.
- **GHRR:** compare directional/ordered compositions against FHRR **with explicit role/permutation encodings**, and account for matrix memory and compute.
- **TrainableHD / trainable encoders:** separate learned representation quality from algebra; use held-out training/validation/test splits.
- **Quantum HDC:** separate classical reference, ideal simulation, noisy simulation, and physical QPU validation; no quantum-advantage claim from classical simulation.
- **FPGA / embedded implementation:** only after CPU profiles identify a bottleneck and a defensible quality/cost tradeoff.

## Appendix C — References and implementation anchors

1. Schlegel, Neubert, Protzel, **“A Comparison of Vector Symbolic Architectures,”** *Artificial Intelligence Review* 55, 4523–4555 (2022): https://doi.org/10.1007/s10462-021-10110-3 — basis for bundle capacity, unbinding approximation, and interference experiments.
2. Kleyko et al., **“A Survey on Hyperdimensional Computing aka Vector Symbolic Architectures,”** Parts I and II: https://arxiv.org/abs/2111.06077 and https://arxiv.org/abs/2112.15424 .
3. **Torchhd** documentation and reference code: https://torchhd.readthedocs.io/ and https://github.com/hyperdimensional-computing/torchhd — verify exact model conventions and versions pinned in the manifest.
4. **CLUTRR** diagnostic relational-reasoning tasks and generation code: https://github.com/facebookresearch/clutrr — inspect whether structured intermediate relations can be extracted under the selected license/version.
5. Local source documents (for design provenance): `Zog_Zoo_HDC_Strengths_Test_Matrix.md` v0.1 and `New Test Methodology-10232026.txt`.

**Sign-off checklist:** architecture/variant definitions frozen; memory accounting policy frozen; C1 oracle/tolerances frozen; task generator and holdout split fixed; resource caps and exploratory targets fixed; seeds registered; benchmark code commit recorded; all baseline arms runnable; append-only JSONL recovery tested.