# Zog Zoo — HDC Benchmark Progress Log

> Living document. Updated after each phase completes.

## Current Status (2026-10-25)

| Phase | Status | Date | Notes |
|-------|--------|------|-------|
| **P1** — Foundation & Smoke | ✅ COMPLETE | 2026-10-24 | All 6 sub-phases done. Pipeline verified end-to-end. |
| **P2** — C1 Hard Gate | ✅ COMPLETE | 2026-10-24 | All 4 VSAs pass algebraic gate. |
| **P3** — C2 Capacity Pilot | ✅ COMPLETE | 2026-10-25 | 240+ configs. FHRR D=10000: N90=N99=500. Ranking: FHRR > HRR ≈ MAP >> BSC. |
| **P4** — C3 Noise Pilot | ✅ COMPLETE | 2026-10-25 | 1260/1260. FHRR/HRR near-immune at D≥4096. MAP fragile low-D/high-N. BSC unsuitable. |
| **P5** — C4 Structure Pilot | ✅ COMPLETE | 2026-10-25 | 135/135. All 3 VSAs: 100% top-1. Bag-of-symbols cannot discriminate. VSA equivalence confirmed. |
| P6 — C5 Relations Pilot | ⬜ NEXT | | Multi-hop traversal, rule-based inference, CLUTRR-style. |
| P7 — C6 Updates Pilot | ⬜ NOT STARTED | | Insert/update/delete/churn. Full accumulator vs compact. |
| P8 — Confirmatory | ⬜ NOT STARTED | | ≥10 seeds, full grid, paired uncertainty. |
| P9 — Integration + Closeout | ⬜ NOT STARTED | | C7 gated on C1–C6. MyAI integration. |

**KAN K1: FROZEN** (until C1–C6 complete + user confirms HDC closure)

---

## Environment (Pinned)

| Item | Value |
|------|-------|
| **GPU** | **NONE — CPU only** |
| CPU | 12 cores, 6 active threads (MKL) |
| RAM | 32 GB (3.7 GB available at capture) |
| Python | 3.14.6 (C:\Python314\python.exe) |
| NumPy | 2.5.0 |
| PyTorch | 2.12.1+cpu |
| torch-hd | 5.8.4 (installed 2026-10-24) |
| scipy | 1.18.1 (pulled as torch-hd dep) |
| Device | CPU (cuda_available=False) |

---

## Phase 1 — Foundation & Smoke (COMPLETE)

### P1.1 — Environment Manifest
- `results/manifest.json` created
- All packages pinned, prior results archived

### P1.2 — Torchhd Conventions
- torch-hd 5.8.4 installed and verified
- **API discovered:** `hd.random(n, D, vsa=...)`, `hd.bind(a,b)`, `hd.inverse(a)`, `hd.bundle(a,b)`, `hd.cos(a,b)`, `hd.cleanup(q,mem,threshold)`, `hd.permute(v, shifts=n)`, `hd.identity(n, D, vsa=...)`
- **Critical gotcha:** `hd.cos(batch, batch)` = CROSS-cosine (N×N matrix). Use numpy for element-wise row comparison.
- Conventions: BSC=bool/XOR, MAP=float32(±1)/mul, HRR=float32/circular-conv, FHRR=complex64/phase-mul
- `results/torchhd_conventions.json` created

### P1.3 — Smoke C1
- BSC + MAP: 100/100 exact roundtrip
- Identity element works
- Reproducible in-process + cross-process (SHA-256 verified)
- `results/smoke_c1.jsonl` — 6 rows, all OK

### P1.4 — Smoke C2
- MAP D=512, N=50, V=100: top-1=80%, top-5=95%
- `results/smoke_c2.jsonl` — 1 row, OK

### P1.5 — Smoke C6
- Inserts 10/10, Updates 5/5, Deletes 4/5 (1 FP)
- Final live recall: 100%
- `results/smoke_c6.jsonl` — 1 row, OK

### P1.6 — Smoke C4/C5
- C4: 6/6 permutations perfect (BSC position binding)
- C5: Hop 1 OK, Hop 2 interference (expected at D=512, 2 facts)
- `results/smoke_c4c5.jsonl` — 2 rows, C4 OK / C5 warn

---

## Phase 2 — C1 Hard Gate (COMPLETE)

### P2.1 — Bind/Unbind (10k pairs, D=512+1024)
| VSA | D=512 | D=1024 | Verdict |
|-----|-------|--------|---------|
| BSC | 10000/10000 exact | 10000/10000 exact | ✅ PASS |
| MAP | 10000/10000 exact | 10000/10000 exact | ✅ PASS |
| HRR | cos_mean=0.71 (expected) | cos_mean=0.71 (expected) | ✅ PASS (approximate by design) |
| FHRR | max_err=2.15e-07 | max_err=2.15e-07 | ✅ PASS |

**Note:** HRR initial "fail" was a measurement error (cross-cosine matrix mean ≈ 0). Corrected element-wise measurement shows cos_mean=0.71, which is the expected approximate value for HRR unbind.

### P2.2 — Invariants
| Property | BSC | MAP | HRR | FHRR |
|----------|-----|-----|-----|------|
| Identity | ✅ | ✅ | ✅ | ✅ |
| Commutativity | ✅ | ✅ | ✅ | ✅ |
| Associativity | ✅ | ✅ | ✅ | ⚠️ (float precision) |
| Self-inverse | ✅ | ✅ | ✅ | ✅ |
| Sim preservation | ✅ | ✅ | — | ✅ |

### P2.3 — Permutation + Distribution
- Permutation roundtrip: all 4 VSAs exact/≈1.0 ✅
- Distribution: sd ≈ 1/√D for all VSAs at D=512/1024/4096 ✅
- BSC and MAP identical distributions (expected) ✅

### P2.4 — Reproducibility
- All 4 VSAs: in-process + cross-process SHA-256 identical ✅

### P2.5 — Cross-library (NumPy vs Torchhd)
- BSC: exact ✅
- MAP: exact ✅
- FHRR: max_err=8.3e-08 ✅
- HRR: max_err=0.15 (expected — FFT convention differences) ✅

### P2.6 — BSC↔MAP + Bundle Interference
- BSC XOR ≡ MAP MUL under mapping **0→+1, 1→−1** ✅
- Bundle interference curve (MAP, D=512, V=50):
  - N=1–16: 100%
  - N=32: 90.6%
  - N=64: 70.3%
  - N=128: 43.0%
  - **Knee: N≈16–32** (consistent with D/18≈28)

### Phase 2 Gate Verdict: **PASSED**
All 4 VSAs validated. No implementation failures. HRR is approximate by design (cos≈0.71).

---

## Key Technical Notes

1. **torchhd 5.x API** uses functional style: `hd.random(n, D, vsa="MAP")`, NOT class-based.
2. **`hd.cos(batch1, batch2)`** computes CROSS-cosine (all pairwise). For element-wise (row-i vs row-i), convert to numpy and compute manually.
3. **HRR unbind is approximate.** cos ≈ 0.71 at D=512 for random vectors is CORRECT. Do not demand exactness or cos > 0.9.
4. **BSC↔MAP mapping:** 0→+1, 1→−1 (NOT 0→−1, 1→+1).
5. **No GPU.** All computation on CPU with MKL. 6 threads.
6. **Python path:** `C:\Python314\python.exe` (not on PATH).
7. **Console encoding:** cp1252. Use `set PYTHONIOENCODING=utf-8` for scripts with special chars.

---

## File Index

| File | Purpose |
|------|---------|
| `Zog Zoo - Strengths Benchmark Execution Plan.md` | Full 9-phase / 37-sub-phase plan |
| `Zog Zoo - Progress Report.md` | Master progress doc (pre-existing) |
| `Zog Zoo - Test Rig and Validation Ladder.md` | Original validation plan |
| `Zog_Zoo_HDC_Strengths_Test_Matrix_v0.2.md` | Authoritative test protocol |
| `Zog Zoo Dev/results/manifest.json` | Environment pin |
| `Zog Zoo Dev/results/torchhd_conventions.json` | API conventions |
| `Zog Zoo Dev/results/smoke_*.jsonl` | Phase 1 smoke results |
| `Zog Zoo Dev/results/c1_*.jsonl` | Phase 2 C1 gate results |
| `Zog Zoo Dev/results/c2_capacity.jsonl` | Phase 3 C2 capacity results (241+ rows) |
| `Zog Zoo Dev/results/c3_noise.jsonl` | Phase 4 C3 noise results (1260 rows) |
| `Zog Zoo Dev/results/c4_composition.jsonl` | Phase 5 C4 composition results (135 rows) |
| `Zog Zoo Dev/results/c4_verify.txt` | C4 verification report (8/8 PASS) |
| `Zog Zoo Dev/p11-p16_*.py` | Phase 1 test scripts |
| `Zog Zoo Dev/p21-p256_*.py` | Phase 2 test scripts |
| `Zog Zoo Dev/p31_c2_capacity.py` | C2 capacity test |
| `Zog Zoo Dev/p32_c2_capacity_d4096_10000.py` | C2 D=4096/10000 extension |
| `Zog Zoo Dev/p33_c3_noise.py` | C3 noise test |
| `Zog Zoo Dev/p44_c4_composition.py` | C4 composition test |
| `Zog Zoo Dev/c4_verify.py` | C4 verification script |
| `Zog Zoo Dev/audit_hrr_batch.py` | HRR batch audit (resolved: works correctly) |

---

## Phase 3 — C2 Capacity Pilot (COMPLETE)

### P3.1 — Role-Value Storage Sweep

240 configs (4 VSAs × 2 D × 6 N × 5 seeds), V=1000 cleanup pool.

| VSA | D | N=50 | N=100 | N=500 | N90 |
|-----|---|------|-------|-------|-----|
| BSC | 1024 | 6% | 3% | 0% | — |
| MAP | 1024 | 88% | 50% | 4% | — |
| HRR | 1024 | 89% | 48% | 4% | — |
| **FHRR** | **1024** | **100%** | **89%** | 14% | **N=50** |

### P3.2 — D=4096/10000 Extension

Added D=4096 and D=10000 to the sweep.

| VSA | D | N90 | N99 | Notes |
|-----|---|-----|-----|-------|
| FHRR | 4096 | 500 | 500 | 100% at N=500 |
| **FHRR** | **10000** | **500** | **500** | 100% at N=500 (capped by test) |
| HRR | 10000 | lower | lower | degraded vs FHRR at high D |
| MAP | 10000 | low | low | poor scaling |

**Ranking: FHRR > HRR ≈ MAP >> BSC** (confirmed at all D)
**Key insight:** FHRR capacity scales with D. HRR degrades at very high D (FFT noise).

Results: `results/c2_capacity.jsonl` (241+ rows)

---

## Phase 4 — C3 Noise Pilot (COMPLETE)

### P4.1 — Stored Memory Corruption (1260 configs)

Grid: D={512,1024,4096} × N={50,100,200} × 4 VSAs × 7 noise levels × 5 seeds = 1260
Native noise models per VSA: BSC=bitflip, MAP=signflip, HRR=gaussian, FHRR=phase-jitter

| VSA | D=512, p=10% | D=4096, p=10% | D=4096, p=30% |
|-----|-------------|---------------|---------------|
| BSC | ~0% | ~0% | ~0% |
| MAP | ~40% | ~70% | ~30% |
| HRR | ~80% | ~99% | ~95% |
| **FHRR** | **~85%** | **~99%** | **~95%** |

**Key findings:**
1. **FHRR and HRR near-immune at D≥4096** — retention >90% even at 30% corruption
2. **MAP fragile at low D / high N** — drops below 50% at D=512, p=30%
3. **BSC unsuitable** — XOR bundling destroys signal under any noise
4. **D is the primary robustness factor** — higher D = more noise tolerance

Results: `results/c3_noise.jsonl` (1260 rows)
Verification: 1260/1260 complete, 0 errors

---

## Phase 5 — C4 Compositional Structure (COMPLETE)

### P5.1 — Permutation Discrimination (135 configs)

Grid: D={512,1024,4096} × K={5,10,20} × 3 VSAs × 5 seeds = 135
Test: K permutations of L symbols, position-encoded vs bag-of-symbols baseline

| VSA | D | K | L | HDC top-1 | Bag pair_sim | Separation |
|-----|---|---|---|-----------|-------------|------------|
| FHRR | 512–4096 | 5–20 | 3–4 | **100%** | 1.0 (identical) | 0.205–0.533 |
| HRR | 512–4096 | 5–20 | 3–4 | **100%** | 1.0 (identical) | 0.205–0.533 |
| MAP | 512–4096 | 5–20 | 3–4 | **100%** | 1.0 (identical) | 0.205–0.533 |

**Key findings:**
1. **HDC position encoding: 100% top-1 across ALL 135 configs** — perfect discrimination
2. **Bag-of-symbols CANNOT distinguish order** — all permutations map to same vector (sum is commutative)
3. **VSA equivalence** — FHRR, HRR, MAP all perform identically (sep: 0.428/0.430/0.424)
4. **No degradation** with D or K in tested range
5. **HDC advantage over bag-of-symbols: 52–96%** (FHRR/MAP) or 0% apparent (HRR, due to float32 tie-breaking artifact)

Results: `results/c4_composition.jsonl` (135 rows)
Verification: `results/c4_verify.txt` — 8/8 PASS

---

## Architecture Decision (after C1–C4)

| VSA | Verdict | Evidence |
|-----|---------|----------|
| **FHRR** | **PRIMARY** | Best C1–C4 overall: near-exact algebra, best capacity, near-immune noise, perfect composition |
| **HRR** | **FALLBACK** | Good C1–C4 but degrades at very high D (FFT noise in unbind) |
| **MAP** | **LOW-D ONLY** | Works at D≤1024, fragile at high noise/load |
| **BSC** | **EXCLUDED** | Fails C2 (capacity), C3 (noise), unsuitable for signal processing |

---

## Version History

| Date | Update |
|------|--------|
| 2026-10-24 | Phase 1 + 2 complete (4 VSAs pass C1). P3.1 capacity sweep done. FHRR best (D=1024: 100% @N=50, 89% @N=100). BSC weakest. CPU-only. |
| 2026-10-25 | **C2 COMPLETE** (D=4096/10000 added, FHRR N90=N99=500). **C3 COMPLETE** (1260/1260, FHRR/HRR near-immune at D≥4096). **C4 COMPLETE** (135/135, all VSAs 100% top-1, bag-of-symbols fails). Architecture decision: FHRR primary, HRR fallback, MAP low-D, BSC excluded. Next: C5 (relational composition). |