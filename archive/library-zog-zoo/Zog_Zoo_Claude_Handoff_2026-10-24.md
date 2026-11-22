# Zog Zoo — Independent Review & TorchHD Adapter Handoff for Claude

**Prepared:** October 24, 2026 (user-local research session)  
**Audience:** Claude, Qwen, and the MyAI research team  
**Purpose:** Resolve what the TorchHD adapter bug was, summarize the experiments completed, separate reliable findings from invalidated results, and define the minimum remaining work before MyAI integration.  
**Status:** HDC exploratory/component-level results are useful. **Do not call cross-backend verification, online memory qualification, or MyAI integration complete.**

## Executive conclusions

1. **TorchHD works without a GPU.** The user's source copy at `/torchHD-main` was successfully imported and executed on **CPU** as TorchHD **5.8.4** with PyTorch 2.10.0+cpu. The TorchHD package is PyTorch-based but does not require a GPU for the HDC operations reviewed.
2. **The old ZogZoo TorchHD adapter had a real software defect.** It cast every non-complex NumPy hypervector to `float32` without preserving the TorchHD VSA tensor subclass. Consequently, **BSC Boolean/XOR** and **HRR real-convolution** operations could silently become default **MAP** operations. This was **not a GPU compatibility requirement**. We cannot establish why the original author wrote the conversion; the effect is visible in the code.
3. **The adapter was corrected and tested.** The revised `/Zog Zoo/hdc_backend/torchhd.py` preserves explicit VSA types, Boolean BSC values, native bundle semantics and native HRR operations; **17/17 targeted CPU regression tests passed**. Native BSC bit flip and majority-vote bundle tests are included. The uploaded TorchHD library itself was not edited.
4. **Historical TorchHD HRR and BSC benchmark metrics must be treated as contaminated by the old adapter.** Preserve them as historical records; rerun before using them as evidence of native TorchHD HRR/BSC behavior. A small repaired-adapter C2 smoke test **is not** a matched-input implementation validation.
5. **HDC has useful measured behaviors; no universal architecture winner is established.** At equal D, FHRR shows strong synthetic bundled capacity. At equal **stored-index** bytes, packed BSC/MAP are compelling compact read-mostly encodings. But packed nearest-key retrieval was still more accurate in the particular random-key benchmark, and exact hashing wins for known clean keys. Different use cases and information contracts mean these do not refute HDC's compositional use case.
6. **Do not force the transformer, HDC and KAN into one physical memory format.** Share authoritative persisted facts/entity IDs, with HDC associative indexes, transformer context/KV cache, and KAN learned parameters as specialized derived states.

## 1. The original adapter issue — direct source evidence

The original preserved adapter is at:

`/Zog Zoo/Backups/2026-10-24_pre_TorchHD_adapter/torchhd.py`

Its conversion path was essentially:

```python
def _to_th(self, arr):
    if np.iscomplexobj(arr):
        return torch.tensor(arr.astype(np.complex128))
    return torch.tensor(arr.astype(np.float32))
```

The same file described BSC and MAP as `np.float32` in `dtype`, and its `bundle()` simply returned `vectors.sum(axis=0)` with the comment that addition was suitable for all VSAs. That assumption is wrong for **BSC**, where standard binding is XOR and bundling is majority vote with an explicit tie policy. In addition, converting HRR arrays to generic `torch.Tensor` discarded the information needed for TorchHD's native HRR subclass to perform circular convolution rather than an elementwise MAP-style operation.

**This is not an inference about GPU hardware.** PyTorch can represent Boolean tensors on CPU and supported GPU devices. The reviewed package runs on CPU, and BSC fundamentally benefits from Boolean/bit representations. The issue was an adapter-level **loss of representation/type semantics** at a NumPy–PyTorch boundary.

The corrected adapter uses `hd.ensure_vsa_tensor(..., vsa=...)` explicitly, handles BSC as Boolean, and uses native VSA-specific functions. This is also an architectural lesson for MyAI's JSON/Protobuf and heterogeneous model boundaries: carry representation metadata (model type, dtype, dimension, seed/provenance and bundling policy), not just a raw array.

**Diagnostic evidence:** the integration review records an old-adapter BSC round-trip similarity of approximately 0.697, versus exact native BSC round-trip. It also includes a targeted guard that HRR binding must match TorchHD's circular-convolution operation rather than elementwise multiplication.

## 2. What is tested, with boundaries

| Workstream | Completed evidence | Limit / action |
|---|---|---|
| Custom HDC algebra and original C1–C4 pilots | Isolated bind/unbind, capacity, noise and positional composition measured; custom component selftests ran successfully | Old TorchHD HRR/BSC comparisons require rerun; paired-input C1.6 remains open |
| C5 relational composition | Historical apparent 100% multihop accuracy audited: each chain was in a tiny separate bundle. Revised C5 shares a single graph memory and makes direction explicit for C5.3 | Need broader graph structures, held-out transfers, shared-memory C5.4/C5.5 and matched baselines |
| C6 updates | Revised scripts perform accumulator deltas, distinguish no untouched items from 0% accuracy, and report rebuild vs true deletion; **18 regression checks** passed for this local correction set | No demonstrated 100,000-operation workload, restart/recovery or complete live/deleted-key abstention measurement |
| C2 high-D pilot | Custom backend tested D=20k, 40k, 100k, variable N, V=1,000 | Only **one seed, 64 queries** per cell. Last successful N is not a certified N90/N99 |
| C2 conventional baselines | Custom backend versus dictionary, fixed fingerprint hash and nearest-key index, plus limited noisy-cue and toy ECC controls; three new seeds for core small/mid-D workloads | Some baselines have different key contracts; run strict total-byte/accuracy comparisons before production selection |
| C2 equal stored-index budget | Packed BSC/MAP, FHRR phase8, HRR float16, packed nearest-key and fingerprint hash under 64/256 KiB; five-seed/128-query confirmation at 256 KiB | **V=64**, synthetic random codebook, stored-index bytes only, not total transient RAM or reversible update state; no TorchHD in this experiment |
| TorchHD source import / adapter | TorchHD **5.8.4** imported on CPU; four VSAs execute; repaired adapter passed **17/17 regression checks** | No paired-input full C1; two-seed D=1024 N=50 smoke only |
| KAN and hybrid C7 | Architecture discussed: KAN parameters/functions and transformer context are distinct from durable knowledge | No KAN K1–K3 performance qualification or transformer/HDC/KAN integrated ablation yet |

### Representative capacity observations, custom backend

**High-D pilot**, V=1,000, one seed, 64 queries: at D=100,000 and N=4,000, clean top-1 recall was **FHRR 100%, HRR 96.9%, MAP 68.8%, BSC 64.1%**. At N=8,000 it was **89.1%, 62.5%, 34.4%, 37.5%**, respectively. These are exploratory single-seed results, **not** hard capacity limits.

**Equal stored-index benchmark**, 256 KiB, V=64, N=1,024, five fresh seeds and 128 queries/seed:

| Representation | Clean top-1 | 10% corrupted-role cue |
|---|---:|---:|
| Packed BSC | **96.9%** | 86.6% |
| Packed MAP | **96.6%** | 86.7% |
| FHRR, 8-bit phase | 55.5% | 45.3% |
| HRR, float16 | 18.8% | 16.7% |
| Packed nearest-key index | **100%** | **100%** |
| Fixed 64-bit fingerprint hash | **100%** | **0%** |

**Interpretation:** For *this specific read-mostly random associative task* packed BSC/MAP are effectively tied and highly efficient in the stated stored-index budget. The packed NN retains all keys and attains higher accuracy. The hash handles pristine known keys but is not tolerant of altered vector keys. These cases use different representation and information contracts; no single result proves the utility or futility of HDC's structural algebra.

**Important engineering caveat:** A finalized packed BSC/MAP bundle generally cannot support exact incremental deletion/update without counters, sidecars, an event log, or rebuilding. Those bytes and update times were **not** included in the 256 KiB stored-index budget. Nor were total process RSS, input-role generation, or GPU/FPGA transfer costs. Noise models vary across VSAs and should not be compared as an equal-energy or equal-SNR corruption level.

## 3. Remaining work before confidently declaring HDC qualified

**P0 — Verify the corrected TorchHD adapter on shared operands.**
- Execute paired-input C1: generate one deterministic operand set per VSA, feed exactly the same values to custom ZogZoo and native TorchHD; compare XOR/multiplication/circular convolution, inverse, permutation, majority/sum/normalization policies and similarity measures.
- Record explicit dtype, VSA subtype, operand normalization, seeds, tie-break rules and accepted tolerances. Do not mistake intentionally different bundling conventions for backend defects. Do not demand exact HRR inverse when the operation is approximate.
- Save corrected results under new filenames; keep old TorchHD HRR/BSC records marked **historical invalid for native-type comparison**.

**P1 — Confirm practical C2 and memory costs.**
- Re-run selected C2 capacity knees with 5–10 paired seeds, ≥200 queries/cell, especially around threshold changes; include BSC and MAP under genuinely bit-packed representations and quantized FHRR.
- Use equal **complete** resident and working budgets: codebooks, role generation/retention, candidate pool, accumulators, metadata, sidecars and serialization, not only compact finalized bundles.
- Compare exact hash/dict, packed approximate key retrieval, HDC and error-correction under task-matched clean/noisy conditions. Keep the report of equal-D results separate from equal-byte results.

**P2 — C6 operational memory qualification.**
- Test 1k → 10k → 100k insert/update/delete streams with an explicit active-set capacity target, realistic absent/deleted queries, p95 latency, process restart + reload + continuation, deterministic reconstruction equality and durability settings.
- Benchmark both reversible accumulator and finalized read-mostly compact modes; measure rebuild/deletion costs and failure-to-abstain.

**P3 — C4/C5 structured-value demonstration.**
- Shared graph memory, directed relationships, held-out structured kinship/analogy, incomplete cues and task-matched conventional graph/list baselines. Avoid per-chain private memories or hidden candidate restrictions that trivialize traversal.

**P4 — Move to MyAI and KAN integration rather than endlessly repeating C2.**
- KAN component tests: parameter-matched tuned MLPs, multiple seeds, formula recovery/interpretability and extrapolation. KAN's weights are learned numerical computation, not automatically a third fact database.
- C7: freeze backbone, fact inputs, tool budgets and prompts. Compare transformer only; transformer + exact persistent store; + conventional approximate retrieval; + HDC; and a hybrid arrangement. Track correctness, abstention, cost, latency, provenance and failure recovery.

**Engineering priorities:** For CPU-only HDC, PCIe 3.0 does **not** explain algebraic correctness, associative recall or benchmark bugs. PCIe will matter for future device transfers (GPU/FPGA), which should be characterized only when those pathways exist.

## 4. Suggested MyAI memory design

- **Canonical truth:** SQLite or equivalent transactional structured records plus durable asset/doc storage, with entity IDs, revisions, source/provenance, events and explicit deletion semantics. Rebuildable materialized views.
- **HDC:** representation-specific associative / compositional cache or derived index. Pack BSC/MAP for read-mostly bytes-constrained deployments; consider quantized FHRR where relational composition justifies it; do not assume all HDC tasks should use one VSA.
- **Transformer:** weights, inference context and KV cache; receives relevant facts and their IDs through a retrieval interface. KV cache is not canonical durable memory.
- **KAN:** trained numerical functions and checkpointed parameters; receives entity attributes and computes results. It need not own an independent episodic fact store.
- **Interop:** typed Protobuf adapter contract with entity ID, schema version, index revision, confidence/calibration and provenance. A canonical write triggers derived-view invalidation/update; stale indexes must be detectable.

This means **one shared body of authoritative data, multiple specialized memory mechanisms**. It does not require forcing BSC, FHRR, transformer attention and KAN parameters into one vector or file format.

## 5. Artifacts for independent audit

Current ChatGPT Library paths:

- Corrected adapter: `/Zog Zoo/hdc_backend/torchhd.py`
- Pre-fix original: `/Zog Zoo/Backups/2026-10-24_pre_TorchHD_adapter/torchhd.py`
- TorchHD source: `/torchHD-main/torchhd/` (source release reported version 5.8.4)
- TorchHD adapter regression tests: `/Zog Zoo/benchmark/test_torchhd_adapter.py`
- TorchHD integration review: `/Zog Zoo/benchmark/TorchHD_Integration_Review_2026-10-24.md`
- Original C1–C6 raw files: `/Zog Zoo/benchmark/Results/`
- Revised C5/C6 notes: `/Zog Zoo/benchmark/REVIEW_CHANGES_2026-10-24.md`
- C2 high-D: `/Zog Zoo/benchmark/C2_HighD_Results_2026-10-24.md`
- C2 conventional: `/Zog Zoo/benchmark/C2_Baselines_New_Seeds_Report.md`
- C2 equal-budget: `/Zog Zoo/benchmark/C2_Equal_Memory_Architecture_Report.md`
- Source, tests and JSONL stored alongside reports in `/Zog Zoo/benchmark/` and `Results/`; dated source and Git bundles in `/Zog Zoo/Backups/`.

**For Claude:** Please review the original and corrected TorchHD adapter side by side, then the test protocol/data files. The most important questions are whether paired-input C1 is now mathematically valid, which C2 comparison contracts are fair, how much operational memory costs after counters/codebooks and whether the remaining C6/C7 work should block specific production claims. We are seeking **scoped conclusions and practical integration decisions**, not a universal yes/no verdict for HDC.