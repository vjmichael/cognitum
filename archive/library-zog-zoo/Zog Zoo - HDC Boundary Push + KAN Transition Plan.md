# Zog Zoo — HDC Boundary Push + KAN Transition Plan

| Field | Value |
|---|---|
| **Date** | 2026-10-22 |
| **Status** | Planning — no code written, no tests run |
| **Author** | Michael (with LLM assistance) |
| **Companion docs** | `Zog Zoo - Progress Report.md`, `Zog Zoo - Test Rig and Validation Ladder.md`, `refs\HDC_Standards_Checklist.md`, `Groks-response-1022206.md`, `refs\HDC_Web_Research_2026-10-22.md` (new) |
| **Purpose** | Record (a) the path to close out HDC per reviewer consensus, (b) Grok's boundary-pushing recommendations, (c) the transition plan to KAN. No code. No tests. Documentation only. |

---

## 1. Closing HDC — the remaining steps

Per the Progress Report §13 and the consolidated reviewer asks (§12.1), HDC closure requires:

### 1.1 Phase B — the single pass (PENDING USER GO)

- **Command:** `C:\Python314\python.exe C:\Users\UserMN4312\Documents\run_zz.py run`
- **Scope:** 5 datasets × 14 pipelines × 6 D × 3 seeds × 3 noise models + positive control + D=10k diagnostic + equal-memory points.
- **Wall-clock:** ~1.5–3 days. Resumable (rows append to `results\rows_run.jsonl`).
- **Gate question answered:** at each D, does the HDC pipeline tie or beat the binarized-embedding baseline? Where is the measured breakpoint?
- **Harness audit:** dense_cohere nDCG@10 vs published (scifact 71.81, nfcorpus 38.63, fiqa 42.14, android 50.01).

### 1.2 Phase C — record + re-scope

1. Aggregate `rows_run.jsonl` → summary tables (dataset × pipeline × D × noise; multi-seed mean ± spread).
2. Harness audit on all four BEIR sets.
3. Answer the gate question (§11.3).
4. Close §10.5 item 6: reconstruct `h2_original_lastrow_wins.py` as side-by-side reference.
5. Re-scope the verdict in both docs under the locked credit rules.
6. Fresh timestamped backup (before and after doc updates).

### 1.3 Phase D — user confirms HDC closure → KAN unfreeze

- User confirms: "HDC is closed."
- KAN K1 unfreezes per Progress Report §13.4.

**State in one line:** Phase A done · Phase B pending GO · Phase C after B · Phase D after user confirms. KAN K1 FROZEN.

---

## 2. Grok's boundary-pushing recommendations for HDC

Source: `Groks-response-1022206.md` (2026-10-22). Grok validated the FPGA/CPU/ASIC-first decision and suggested techniques beyond the standard checklist.

### 2.1 Techniques ranked by ROI for Zog Zoo's specific weaknesses

| # | Technique | What it does | Why it helps here | Implementation cost |
|---|---|---|---|---|
| 1 | **Resonator networks + iterative cleanup** | Repeatedly unbind best-matching stored item, subtract contribution, re-unbind next factor; converge | Directly fixes H2 failures: XOR+superposed (0.71) and CONV+noisy-unbind (0.77/0.17). Turns "weak in regimes that matter" into "converges with iteration" | ~30 lines NumPy (dot, subtract, normalize, repeat). FPGA: each iteration = dot + subtract + normalize |
| 2 | **FHRR (complex Hadamard binding, conjugate unbind)** | Complex-valued HVs; bind = component-wise multiply; unbind = multiply by conjugate (angle subtraction, no deconvolution) | The CONV noisy-unbind failure is a *known* weakness of circular convolution. FHRR unbinds near-exactly by construction. Already in checklist §F item 11 — Phase B will quantify the gap | Complex-number Hadamard products. Already in harness |
| 3 | **Dynamic / low-discrepancy HV generation** | Generate near-orthogonal vectors on-the-fly from Sobol/Halton sequences instead of static i.i.d. codebook | No need to regenerate when D or vocabulary changes. Structured-random with provable orthogonality bounds. Weakens the "random vectors are a lower bound" critique | Different RNG; no architecture change. Scales cleanly |
| 4 | **Non-uniform error protection / fault-aware design** | Region-wise ECC; Hamming-weight-based sensitivity analysis built into the hardware | HDC is naturally noise-tolerant; making that tolerance *explicit and measurable* in hardware is a differentiator. Relevant to FPGA/ASIC target | Hardware design phase, not software |
| 5 | **Structured entity-attribute-value encoding + ego-binding** | Explicitly separate object identity / parts / state; receiver-centric binding | Pushes HDC from bag-of-features toward hierarchical semantic structure. Maps to "building has an inside" / "person has homeostasis" requirement | Design phase; requires the companion-AI use-case to be concrete |

### 2.2 Techniques noted but NOT actionable now

| Technique | Why deferred |
|---|---|
| Nyström / kernel approximations (HyperX/NysX) | Graph/structured data domain; not the current retrieval task |
| Gaussian Polygon / multiscale interpolation | Image / remote-sensing domain |
| In-memory compute (FeFET/RRAM/SOT-MRAM) | Requires university or foundry partnership |
| ASIC tape-out | Research stage; no commodity HDC ASIC available |

### 2.3 Hardware target (recorded for later)

**KR260-G** (AMD XCK26 Zynq UltraScale+ MPSoC on robotics carrier):
- Quad Cortex-A53 + dual Cortex-R5F
- 256K logic cells, 1.2K DSP slices, 4 GB DDR4
- SLVS-EC camera interface, USB 3.0, 4× GbE + SFP+
- Power: ~8–16 W under load
- Cost: ~$350 (DigiKey)
- Use: PL accelerators for bind/bundle/Hamming/resonator; A53 for golden reference; camera pipeline for companion-AI embodiment

**FPGA-relevant HDC facts (from Grok):**
- Published accelerators: AXI-HDC (Zynq), nano_hamming (single-cycle), RouteHD (Alveo U200), HyperX/NysX
- Typical vs GPU: 4–60× lower latency, 100–300× better energy/inference at edge scale
- Routing congestion (not logic) is the limit at high D / high class parallelism
- KAN on FPGA: KANELÉ flow (QAT + pruning → LUT evaluation) = up to 2700× speedup vs prior KAN-on-FPGA

### 2.4 Grok's concrete next steps (recorded, not yet executed)

1. Buy KR260; get Ubuntu + ROS 2 running; confirm camera + PL acceleration workflow.
2. Port HDC primitives to C++/HLS; accelerate Hamming + bind/bundle in PL; measure vs R9700.
3. Build smallest "object file + part-whole" demo (camera → HDC scene graph with persistence).
4. Layer on KAN heads + tiny language interface.
5. Keep validation ladder discipline throughout.

---

## 3. The recommended sequence (what to do, in order)

| Step | Action | Dependency | Status |
|---|---|---|---|
| 1 | Run Phase B (the single pass) | Phase A done ✓ | **PENDING USER GO** |
| 2 | Phase C (aggregate, audit, re-scope verdict) | Phase B complete | queued |
| 3 | User confirms HDC closure | Phase C complete | queued |
| 4 | Add resonator cleanup as "beyond standard" pipeline; re-run affected cells | Phase C baseline numbers (to show improvement) | planned |
| 5 | FHRR results from Phase B already quantify the CONV-gap; no extra run needed | Phase B | included in step 1 |
| 6 | Dynamic HV generation as "beyond standard" pipeline | Phase C baseline | planned |
| 7 | KAN K1 (parameter-matched tuned MLPs, multiple seeds, extrapolation test) | Step 3 (HDC closure confirmed) | FROZEN |
| 8 | KAN K2 (objective: does learned edge recover ground-truth formula?) | K1 done | queued |
| 9 | KAN K3 (auditable sub-computation with readable trace) | K1 done | queued |
| 10 | KR260 hardware: PL accelerator for bind/bundle/Hamming/resonator | Steps 4–6 done in software (golden model) | later |
| 11 | FPGA-vs-GPU benchmark (latency / energy / accuracy delta) | Step 10 | later |

**Key principle:** Steps 1–6 close and push HDC in software. Steps 7–9 are KAN. Step 10–11 is hardware. Each step has a clear gate before the next begins.

---

## 4. KAN transition notes (from Progress Report §13.4 + reviewer Q6)

Per the locked reviewer consensus (Claude + Gemini concur):

- **K1:** Parameter-matched **tuned** MLPs (not just "error ≤ MLP"), **multiple seeds**, **extrapolation test**. Baseline = KAN (FP) vs MLP (FP) vs KAN (QAT+pruned) on formula/symbolic task sets. Report accuracy + resource proxy (params, LUT-equivalent).
- **K2:** Replace human "readable?" rating with the **objective test** — does the learned spline edge recover the ground-truth univariate function? (KANELÉ's LUT view makes this directly measurable: read the truth table off and compare to f.)
- **K3:** Auditable sub-computation with a human-readable trace.
- **KANELÉ reference (FPGA '26):** B-spline basis (grid G, domain [a,b], order S) + base activation; QAT (Brevitas, n-bit uniform, STE) + norm-based pruning → LUT truth tables → VHDL. Up to 2700× speedup, >4000× fewer resources vs prior KAN-on-FPGA. Best in class on symbolic/physical formula tasks. 8-bit quantized KAN RL actor beats ~5× larger MLP.
- **Practical hyperparameters (KANELÉ defaults):** G = 6–40, [a,b] ∈ {[-8,8], [-2,2]}, S = 3–10. LUT usage drops exponentially with bit-width; diminishing returns below 6 bits.

**KAN is FROZEN until the user confirms HDC closure (Step 3 above).**

---

## 5. New literature findings (web research 2026-10-22)

Three papers + one field survey found during research. All directly relevant to the project.

### 5.1 Stochastic-HD (Morris, Hao, Gupta, Khaleghi, Aksanli, Rosing — Frontiers in Neuroscience, 2022)

**Key insight:** The accumulation (reduction) step is THE bottleneck for HDC in parallel hardware (PIM, FPGA, crossbar). Dot products require sequential accumulation over D dimensions, killing parallelism.

**Their fix:** Deterministic stochastic computing (SC) converts ALL HDC operations into parallel bitwise ops (AND, XOR, MUX). No accumulation. No ADCs. No floating point.

**Results (45 nm CMOS, RRAM crossbar, D=2048):**
- 70× speedup and 456× energy efficiency gain over naive PIM (Gupta et al. 2018)
- 43.1× more energy-efficient than SearcHD (the prior best HDC PIM design, Imani et al. 2019)
- 4.4% more accurate than SearcHD
- Only 0.3% accuracy loss vs exact HDC (with integrated retraining)
- Supports classification AND clustering
- End-to-end: encoding + training + retraining + inference all in stochastic domain

**Why this matters for Zog Zoo:**
- The KR260 has 1.2K DSP slices — but this paper argues DSP/FPU is *overkill* for HDC. Bitwise ops are the right primitive.
- The PL (programmable logic) fabric is where the speedup lives: AND/XOR/MUX gates in parallel across all D dimensions.
- This is a concrete, published, 45nm-validated architecture for exactly the kind of hardware target the user chose.
- **Actionable as a "beyond standard" pipeline** in software first (deterministic SC is just structured bitstreams + AND/XOR — implementable in NumPy), then as the PL accelerator spec.

**Reference:** doi: 10.3389/fnins.2022.867192. Code/data: UCI ML repo (ISOLET, UCIHAR, PAMAP2, etc.)

### 5.2 Teeters, Kleyko, Kanerva, Olshausen — "On separating long- and short-term memories in HDC" (Frontiers in Neuroscience, 2023)

**Key insight:** For large memories (1000+ key-value pairs), a **Sparse Distributed Memory (SDM)** requires dramatically less storage and computation than a superposition vector, while achieving the same recall reliability.

**Their comparison (1000 items, 110 item-memory vectors):**

| Metric | Superposition (S1, 1-bit) | Superposition (S2, 8-bit) | SDM (A1–A4) |
|---|---|---|---|
| Storage (full item memory present) | 25–35× more than SDM | 15–25× more than SDM | **baseline** |
| Computations per recall (serial) | 37–135× more than SDM | 51–135× more than SDM | **baseline** |
| Vector width needed for 10⁻⁶ error | ~9879 components | ~9062 components | **512 components** (capacity from #locations, not width) |

**The architecture principle:**
- **Superposition vector = working memory** (short-term, ~7 items, compositional, fast, small D)
- **SDM = long-term memory** (large capacity, address-based, fixed vector width, scales by adding locations not width)
- They are **complementary**, not competing. The superposition vector handles composition and manipulation; the SDM handles storage and lookup.

**Why this matters for Zog Zoo:**
- **This directly explains the H3 results.** The user's CAM (superposition) broke at N≈D/18 because superposition capacity IS limited by D. The NN index held to N=20k because it's effectively doing address-based lookup (like SDM) — not superposition.
- The "NN nearest-key side-channel" that the user identified as the workhorse for large banks is conceptually the same architecture as SDM. The Teeters et al. paper gives it a theoretical foundation and shows it's 15–35× more efficient than forcing superposition to do the job.
- **The correct HDC architecture for the companion AI:**
  - Working memory (superposition, D=512–1024, ≤7–20 items): holds the current context, active bindings, short-term state
  - Long-term memory (SDM, D=512, N=10k–1M locations): stores all learned associations, object files, persistent knowledge
  - The two communicate: working memory recalls from long-term memory, composes results, writes back
- This is also the biological model: cerebellum = associative memory (SDM analog); cortex = compositional working memory (superposition analog)

**Reference:** doi: 10.3389/fnins.2022.867568. Code: https://github.com/jeffteeters/hdfsa

### 5.3 QHDC — Quantum Hyperdimensional Computing (Cumbo, Blankenberg — npj Unconventional Computing, 2026)

**What it is:** First implementation of HDC mapped onto quantum hardware. Uses quantum superposition to natively represent the high-dimensional vector space.

**Results:** 500× speedup over alternative methods for symbolic reasoning and image classification. Tested on classical computer, quantum simulator, and a real quantum computer.

**Key quote:** "I had the idea to explore a type of computation that works naturally on a quantum computer, rather than forcing it to fit a classical framework."

**Relevance to Zog Zoo:**
- Confirms that HDC's core operations (bind, bundle, similarity) map naturally to hardware substrates beyond just FPGA — quantum is next.
- Not actionable now (no quantum hardware target). Recorded as a future direction.
- Validates the user's intuition that HDC is a *hardware-native* paradigm, not a software abstraction.

**Reference:** doi: 10.1038/s44335-026-00064-6

### 5.4 Field status (Frontiers Research Topic, 2022–2023, closed)

**The field's own words:** "HDC is still in its infancy and is expecting major advancements both theoretically and practically."

**Open questions the field is actively working on:**
1. What are the killer applications of HDC vs DNNs?
2. What are the optimal encoding methods for arbitrary tasks?
3. How can HDC be combined with DNNs/neuromorphic/evolutionary to create accurate yet efficient machines?

**Published in the topic (4 articles):**
- Stochastic-HD (above) — hardware
- Separating long/short-term memory (above) — architecture
- EventHD (Zou et al. 2022) — neuromorphic event sensors + HDC (28 citations)
- Multi-Centroid HDC (Pale et al. 2022) — biomedical (epileptic seizure detection)

**Editor:** Dr. Abbas Rahimi, IBM Research (Zurich). Other editors: Villanova U, U. of Maryland.

**Implication for Zog Zoo:** The user's project (HDC + KAN + Capsules + small transformer, FPGA target, companion AI) is at the frontier of what the field is asking. The integration question (item 3) is exactly the Tier B test. The hardware question is exactly the KR260 target. This is not a niche project — it's the field's stated direction.

---

## 6. Updated "beyond standard" technique table (incorporating all findings)

| # | Technique | Source | ROI for Zog Zoo |
|---|---|---|---|
| 1 | **SDM as long-term memory tier** | Teeters, Kleyko, Kanerva, Olshausen (2023) — §5.2 | **Highest architectural ROI.** Decouples capacity from D. Explains H3. 15–35× efficiency gain for large banks. Two-tier architecture. |
| 2 | **Resonator networks + iterative cleanup** | Grok + survey (Kent 2020, Frady 2020) | Directly fixes H2 failures (XOR+superposed 0.71, CONV+noisy 0.77). ~30 lines NumPy. FPGA-friendly. |
| 3 | **FHRR (complex Hadamard, conjugate unbind)** | Survey Part I §2.3; Plate 2003; Salik 2026 §3.3 | Already in harness. Phase B quantifies the gap. Near-exact unbind by construction. |
| 4 | **Deterministic stochastic computing** | Morris et al. 2022 — §5.1; Heddes 2024 (Schmuck ref) | Hardware-path enabler. ALL ops bitwise-parallel. 70×/456× gains. Single-clock-cycle associative memory on FPGA. |
| 5 | **NeuralHD — dimension elimination** | Salik 2026 §3.8; Zou et al. 2021 | Remove irrelevant dimensions after training. Use D=512 instead of D=1024 for same accuracy. Reduces FPGA resources. |
| 6 | **TP-HDC (task-projected multi-task)** | Salik 2026 §3.5; Chang et al. 2020 | Multiple AMs in same hyperspace for different tasks (identify + track + predict). 12.8% accuracy gain. |
| 7 | **Circular-hypervectors** | Heddes 2024 (Nunes et al. 2023) | Encode time-of-day, rotation, angular state. Needed for companion AI temporal awareness. |
| 8 | **HD hashing (HDC as data structure)** | Heddes 2024; Heddes et al. DAC 2022 | Internal data management. 0% mismatch at 10-bit errors. O(1) on hardware. Stack machine for working memory. |
| 9 | **Dynamic / low-discrepancy HV generation** | Grok (ID-VSA / DystoHD) | No static codebook. Scales with D/vocab. Provably near-orthogonal. |
| 10 | **Non-uniform error protection / ECC** | Grok | Hardware design phase. Hamming-weight sensitivity. |
| 11 | **Structured entity-attribute-value + ego-binding** | Grok | Companion-AI semantic structure. "Building has an inside." |
| 12 | **QHDC (quantum HDC)** | Cumbo 2026 — §5.3; Salik 2026 §7.3 | Future direction. Validates hardware-native HDC across substrates. |

---

## 7. Field validation (2026-10-22 web + PDF research)

### 7.1 The 2026 survey confirms your project is the field's stated goal

**Salik et al. 2026** (Khalifa University + Abu Dhabi University, Results in Engineering) explicitly lists as future directions:
- Hybrid HDC + DNN → **your Tier B**
- Dynamic/adaptive encoding → **your "beyond standard" items**
- Quantum + HDC → **validates QHDC**
- Vision-language models → **your companion AI**
- XAI for HDC → **your KAN K2/K3**
- Custom hardware → **your KR260**

Their §7 on vision-language: *"The integration of HDC's HD encoding with vision-language models is very promising... context-aware robotics, visual question answering and image captioning."* This is your project.

### 7.2 Hardware landscape confirmed (Salik 2026 §3.12)

| Implementation | Platform | Result | Relevance |
|---|---|---|---|
| F5-HD (Salamat 2019) | FPGA | 12× energy, 1.7× speedup vs GPU | Same class as KR260 |
| PULP-HD (Montagna 2018) | RISC-V ultra-low-power | 18.4× speedup, 2× energy | Low-power HDC proven |
| tiny-HD (Khalegi 2021) | ASIC (IoT) | Ultra-low power, configurable | Your eventual ASIC target |
| FELIX (Gupta 2018) | Memristive PIM | Single-cycle Boolean in memory | Your Stochastic-HD path |
| GenieHD (Kim 2020) | FPGA, **D=100,000** | 44.4× speedup, 54.1× energy | D-scale validated |
| Eggimann 2021 | 5 μW standard cell | Always-on sensing | Ultra-low-power reference |
| 3D VRRAM (Li 2016) | 3D memory | 50× energy | In-memory compute |
| **Schmuck 2019** | FPGA | **Single-clock-cycle inference** (deep adder trees) | **Your KR260 PL accelerator spec** |

**Key insight:** Your KR260 target is not novel. It's the F5-HD / PULP-HD / Schmuck pattern on a modern Zynq. You're using a proven architecture pattern, not inventing one.

### 7.3 Architecture taxonomy confirmed (Salik 2026 §3)

Your HDC checklist (BSC + FHRR + MAP) matches the standard three. The survey adds context:
- **TPR** (Smolensky 1990): forerunner, dimension-growth issue — not HDC proper
- **MBAT** (Gallant 2013): matrix binding — overkill for your use case
- **QuantHD** (Imani 2019): quantization framework — relevant for your FPGA bit-width choices
- **SearcHD** (Imani 2019): binary stochastic training — "bitwise substitution instead of addition"
- **NeuralHD** (Zou 2021): adaptive dimension elimination — **new "beyond standard" item**
- **TP-HDC** (Chang 2020): task-projected multi-task — **new "beyond standard" item**
- **SecureHD** (Imani 2019): MPC-based privacy — not relevant to your project

### 7.4 HDC as data structure (Heddes 2024)

Beyond classification, HDC is used for:
- **HD hashing** — dynamic hash tables, robust to bit errors, O(1) on hardware
- **Stack machine** — push/pop with permutation + bundling, differentiable
- **Bloom filter** (generalized) — capacity-adjustable
- **Service discovery** — decentralized, noise-robust
- **Graph isomorphism** — distributed representations
- **Set similarity estimation** (Jaccard, Adamic-Adar) — for link prediction, dedup

**Relevance to Zog Zoo:** Your companion AI needs internal data management. HDC hash tables + stack machine = noise-robust, hardware-efficient internal state. This is the "object file system" Grok described, now with published algorithms.

### 7.5 Circular-hypervectors (Heddes 2024, Nunes et al. DAC 2023)

New basis-hypervector type for circular data (angles, time-of-day, seasons, rotation). Built from level-hypervectors with forward/backward transitions to eliminate the discontinuity at 0/2π.

**Relevance to Zog Zoo:** Your companion AI needs temporal awareness (time-of-day, circadian patterns, rotational state of objects). Circular-hypervectors are the standard HDC encoding for this. Add to the encoder options.

### 7.6 TorchHD confirmed as standard library

Heddes 2024 uses TorchHD for implementation. This confirms it's the field standard. But:
- Your NumPy reference implements the same operations (XOR, majority, Hamming, permutation)
- Your target is FPGA/CPU, not GPU — TorchHD's PyTorch dependency is irrelevant
- Your `hdc_reference.py` (~150 lines) is functionally equivalent for BSC
- The concepts (not the library) are what matter: basis-hypervector types, encoding patterns, associative memory

**You don't need TorchHD. You have the same operations. You have the correct target hardware.**

---

## 7. What this document is NOT

- Not a code specification.
- Not a test plan (that's in the Progress Report §13.1–13.2).
- Not a commit to execute any of the above without explicit user GO at each gate.
- Not a replacement for the Progress Report or Test Rig doc.

This is the **bridge document** connecting the reviewer closure (what to run) to the boundary push (what to add) to the KAN transition (what comes next) to the hardware path (what the KR260 enables). All four are gated.