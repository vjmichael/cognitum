# Zog Zoo — Independent validation report for Claude and Qwen

**Date:** October 24, 2026. **Status:** completed C1/C2/C5 checks and 100,000-operation C6 controlled stress test; **not production certification**.

## Scope and provenance

- Ran from the user-uploaded ZogZoo source and the user-uploaded TorchHD 5.8.4 source on CPU, without changing either core implementation.
- Used ZogZoo’s revised TorchHD adapter, retaining BSC Boolean/XOR and HRR circular-convolution types.
- C1 and C2 used **identical input hypervectors and value assignments** for both backends, not independently generated random inputs.
- C5 and C6 were separate additional tests; their case generation and goals are stated below.
- All scripts and raw result data are provided. Original historical JSONL files and repository files remain untouched.

## C1 — paired-input operation parity

**40/40 passed:** 4 VSA architectures × D=512/4,096 × 5 independent seeds.
Verified the same input vectors for binding, unbinding, seven-item bundles after documented output normalization, and cleanup top-1 ranking.
For BSC, mapped bipolar signs to TorchHD Boolean bits; for MAP, compared to sign of TorchHD additive bundle; for FHRR, compared to phase-normalized sum; for HRR, compared to norm-normalized sum.
HRR inverses are approximate in both libraries; parity of the computed unbinding operation does not mean exact restoration of the original vector.
The tests do **not** establish equality of all TorchHD native bundle outputs with ZogZoo finalized bundles absent normalization.

## C2 — matched-input association retrieval

**120 configurations completed:** 4 VSAs × D=1,024/4,096 × N=50/150/350 × 5 fresh seeds; V=256; up to 96 queries per cell.
The following mean top-1 accuracies use the *same* keys, value vectors, assigned labels and query indices in both backends; their native bundling policies still differ.

| D | N | VSA | ZogZoo | TorchHD | Prediction agreement |
|---:|---:|---|---:|---:|---:|
| 1,024 | 50 | BSC | 78.4% | 78.0% | 77.6% |
| 1,024 | 50 | MAP | 74.4% | 95.2% | 76.4% |
| 1,024 | 50 | HRR | 94.0% | 94.0% | 100.0% |
| 1,024 | 50 | FHRR | 99.6% | 100.0% | 99.6% |
| 1,024 | 150 | BSC | 24.4% | 24.4% | 62.5% |
| 1,024 | 150 | MAP | 24.0% | 43.5% | 34.6% |
| 1,024 | 150 | HRR | 40.2% | 40.2% | 100.0% |
| 1,024 | 150 | FHRR | 67.5% | 78.3% | 74.2% |
| 1,024 | 350 | BSC | 7.7% | 8.1% | 61.5% |
| 1,024 | 350 | MAP | 7.7% | 14.4% | 25.8% |
| 1,024 | 350 | HRR | 17.9% | 17.9% | 100.0% |
| 1,024 | 350 | FHRR | 30.8% | 38.3% | 48.3% |
| 4,096 | 50 | BSC | 100.0% | 100.0% | 100.0% |
| 4,096 | 50 | MAP | 100.0% | 100.0% | 100.0% |
| 4,096 | 50 | HRR | 100.0% | 100.0% | 100.0% |
| 4,096 | 50 | FHRR | 100.0% | 100.0% | 100.0% |
| 4,096 | 150 | BSC | 89.6% | 90.2% | 91.7% |
| 4,096 | 150 | MAP | 88.5% | 98.5% | 88.5% |
| 4,096 | 150 | HRR | 98.8% | 98.8% | 100.0% |
| 4,096 | 150 | FHRR | 99.8% | 100.0% | 99.8% |
| 4,096 | 350 | BSC | 47.7% | 47.5% | 71.9% |
| 4,096 | 350 | MAP | 46.9% | 74.0% | 50.8% |
| 4,096 | 350 | HRR | 71.2% | 71.2% | 100.0% |
| 4,096 | 350 | FHRR | 92.7% | 97.5% | 92.5% |

**Important:** MAP’s TorchHD sum-vs-ZogZoo sign-of-sum explains much of the observed recall gap. Prediction agreement is not always 100% because these are different retrieval representations, not because C1 algebra failed. No statistical superiority test or equal-RAM comparison was made in this new C2 round.

## C5 — shared graphs and directed inference

**48 configurations:** 4 VSAs × 2 backends × D=2,048/4,096 × 3 seeds. 120 entities, three-hop disjoint chains with 90 edges in one shared associative memory; symbolic graph oracle on same graph. Rule test uses 30 three-person family chains and an explicit one-position source permutation.

| D | VSA | Backend | 3-hop retrieval | 2-step directed rule |
|---:|---|---|---:|---:|
| 2,048 | BSC | zogzoo | 67.8% | 95.6% |
| 2,048 | BSC | torchhd | 61.1% | 93.3% |
| 2,048 | MAP | zogzoo | 68.9% | 98.9% |
| 2,048 | MAP | torchhd | 94.4% | 100.0% |
| 2,048 | HRR | zogzoo | 66.7% | 38.9% |
| 2,048 | HRR | torchhd | 62.2% | 46.7% |
| 2,048 | FHRR | zogzoo | 100.0% | 100.0% |
| 2,048 | FHRR | torchhd | 100.0% | 100.0% |
| 4,096 | BSC | zogzoo | 95.6% | 100.0% |
| 4,096 | BSC | torchhd | 98.9% | 100.0% |
| 4,096 | MAP | zogzoo | 96.7% | 100.0% |
| 4,096 | MAP | torchhd | 100.0% | 100.0% |
| 4,096 | HRR | zogzoo | 98.9% | 55.6% |
| 4,096 | HRR | torchhd | 94.4% | 40.0% |
| 4,096 | FHRR | zogzoo | 100.0% | 100.0% |
| 4,096 | FHRR | torchhd | 100.0% | 100.0% |

The conventional graph traversal baseline was 100% across these cells. **HRR 2-step rule accuracy remains substantially lower** than its plain multihop result; this specific task needs a dedicated encoding/algorithm investigation. These tests are structured synthetic examples, not CLUTRR natural-language interpretation, analogy generalization or MyAI reasoning.

## C6 — operational updates and real restart

**100,000 operations PER VSA (400,000 across four).** Deterministic common event log: 50,176 insert, 25,071 update and 24,753 delete requests. Active capacity capped at 64; 25,360 implicit evictions accompany inserts when full. The final active count was 63.

- Every operation changed a FULL reversible HDC accumulator using add/remove/update of the actual bound association; no end-of-test-only bundle reconstruction.
- Every 10,000 operations rebuilt a reference accumulator from active authoritative records; maximum observed reconstruction error was exactly zero for all four VSAs in this workload.
- After operation 50,000 a disk NPZ checkpoint was created. A **new Python process** loaded it, completed the other 50,000 operations and matched a separate uninterrupted 100,000-operation run (identical final state digest).
- Resume checked event-log checksum, architecture, dimension, and snapshot-state checksum. An intentionally altered snapshot was rejected with `snapshot checksum mismatch`.
- **Do not conflate exact accumulator maintenance with successful recall.** The following sample recall measures the HDC cleanup accuracy while active-key memory experiences interference.

| VSA | Operations | Mean checkpoint recall | Final checkpoint recall | Accumulator bytes | Saved/reloaded identical |
|---|---:|---:|---:|---:|---|
| BSC | 100,000 | 56.7% | 41.7% | 4,096 | Yes |
| MAP | 100,000 | 57.1% | 41.7% | 4,096 | Yes |
| HRR | 100,000 | 84.2% | 83.3% | 8,192 | Yes |
| FHRR | 100,000 | 97.1% | 100.0% | 16,384 | Yes |

### What the C6 stress test does and does not validate
- **Proves in this controlled workload:** deterministic live delta-update arithmetic, snapshot/reload continuity, correspondence with an exact active-key dictionary, and basic snapshot tampering rejection.
- **Does not prove:** compact one-bit writable memory by itself; thresholded abstention on missing/deleted keys; safe crash-consistent production writes; transaction isolation; schema migrations; file-system power-loss durability; distributed replication; larger active worksets or 100,000 updates at D=100,000.
- The system kept a key bank, value bank, authoritative dictionary and an uncompressed accumulator. For example at D=1,024, FHRR kept a 16 KiB accumulator, a 2 MiB key bank, and a 4 MiB candidate-value bank (excluding Python metadata).
- The operation log uses an eviction policy to maintain 64 live records. Inserts at capacity cause an additional removal; do not describe actual state changes as exactly 50% inserts, 25% updates, 25% deletes.

## Program disposition

**Completed now:** C1 shared-input algebraic comparisons; limited C2 matched-input recall; C5 shared-graph and directed-rule audits; bounded C6 100k live updates plus process restart/replay consistency.

**Open / not claimed completed:**
1. Production C6 engineering: durable transactional event log, atomic snapshot writes, crash injection, negative-key abstention, rollback/replay tests and memory under larger live sets.
2. C5.4/5.5: CLUTRR-style structured kinship and held-out analogy; especially diagnose HRR role composition.
3. Confirmatory C2 large-D with more independent seeds and queries if statistical N90/N99 thresholds are required; newer paired-input tests cover only D≤4,096.
4. Matched **total working-set** RAM/compute comparisons at production update rates; the previous read-mostly equal-index-byte comparison is useful but not sufficient.
5. C7 transformer integration and KAN baselines are untested. Do not claim hybrid AI improvement without ablations.
6. Real workstation, PCIe transfer, FPGA and measured energy benchmarks remain out of scope of this CPU-only run.

**Recommendation:** Treat core mathematical operations and a bounded update/restart prototype as validated; do not declare MyAI memory production-ready. Proceed to KAN and MyAI integration while addressing HRR directed relational encoding and durable persistence in parallel. Preserve source-of-truth records independently of HDC indexes.

## Reproduction

Use Python with NumPy, PyTorch and the user-supplied TorchHD 5.8.4 source, setting `PYTHONPATH` to the parent of both source packages. The supplied scripts run CPU only.

```bash
PYTHONPATH=<torchHD-main-parent>:<ZogZoo-root> python validate_c1_c2_paired.py
PYTHONPATH=<torchHD-main-parent>:<ZogZoo-root> python validate_c5_shared.py
PYTHONPATH=<ZogZoo-root> python validate_c6_restart.py --mode make-events --ops 100000 --output-dir c6_100k
PYTHONPATH=<ZogZoo-root> python validate_c6_restart.py --mode first --vsa BSC --output-dir c6_100k
PYTHONPATH=<ZogZoo-root> python validate_c6_restart.py --mode resume --vsa BSC --output-dir c6_100k
PYTHONPATH=<ZogZoo-root> python validate_c6_restart.py --mode reference --vsa BSC --output-dir c6_100k
PYTHONPATH=<ZogZoo-root> python validate_c6_restart.py --mode compare --output-dir c6_100k
```

Repeat the C6 first/resume/reference stages for MAP, HRR and FHRR before `compare`. The stored results cover all four.

## Source/data preservation

No original Library source, existing benchmark result, or user TorchHD source was changed by this validation. New scripts and outputs have distinct names. This audit documents the tested source as it existed at time of execution.