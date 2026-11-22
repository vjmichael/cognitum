# Zog Zoo — Phase B Sub-Phase Execution Plan

| Field | Value |
|---|---|
| **Date** | 2026-10-23 |
| **Status** | B1 RUNNING · B2–B4 queued |
| **Companion docs** | `Zog Zoo - Progress Report.md` §13.2, `Zog Zoo - HDC Boundary Push + KAN Transition Plan.md` §1.1 |
| **Results file** | `Zog Zoo Dev\results\rows_run.jsonl` (shared, resumable) |

---

## Why sub-phases

The full Phase B (5 datasets × 14 pipelines × 6 D × 3 seeds × 3 noise models + diagnostics)
estimates 1.5–3 days. Running it as a single background task risks:
- Timeout or silent failure with no intermediate visibility
- No ability to catch issues early on the smallest/fastest data
- No checkpoint between the largest (fiqa, 57k docs) and the rest

**Decision:** split by dataset size. Run smallest first for a quick harness audit, then
scale up. Each sub-phase is a few hours. All write to the same JSONL file (resumable).

---

## Sub-phase definitions

| Phase | Datasets | Docs | Config | Batch | Est. time |
|---|---|---|---|---|---|
| **B1** | nfcorpus + scifact + SQuAD/dev | 3.6k + 5.2k + 1.2k | `configs/b1_small.json` | `run_b1.bat` | ~1–2 hrs |
| **B2** | cqadupstack-android | 23k | `configs/b2_medium.json` | `run_b2.bat` | ~2–3 hrs |
| **B3** | fiqa | 57.6k | `configs/b3_large.json` | `run_b3.bat` | ~3–5 hrs |
| **B4** | D=10k sentence diagnostic + equal-memory | nfcorpus + scifact | `configs/b4_diag.json` | `run_b4.bat` | ~1–2 hrs |

### Scope per sub-phase

**B1–B3 (main grid):**
- 14 pipelines: dense_cohere, emb_cohere, emb_rescore, bm25, bag_idf, bow_flat,
  hybrid, ngram, ri, xor_position, fhrr_bag, fhrr_hybrid, map_bag, hrr_bag
- D: 1024, 512, 256, 128, 64, 32
- Noise: clean, 20% bitflip, 20% mixture
- Seeds: 20261020, 20261021, 20261022
- Positive control per group

**B4 (diagnostics):**
- D=10,000 sentence-unit capacity diagnostic (bag_idf + hybrid × 3 seeds)
- Equal-memory comparison: 1-bit@10240 vs 2-bit@5120 vs 4-bit@2560
- Clean noise only (capacity test, not noise robustness)

---

## Execution order and gates

```
B1 → check results → B2 → check results → B3 → check results → B4 → Phase C
```

### Between each sub-phase:
1. Check task status (completed? errors?)
2. Verify rows in `rows_run.jsonl` (count, spot-check scores)
3. Harness audit: dense_cohere nDCG@10 vs published scores
   - scifact: 71.81
   - nfcorpus: 38.63
   - fiqa: 42.14
   - android: 50.01
4. If audit passes → proceed to next sub-phase
5. If audit fails → diagnose before continuing

### After all four complete:
- Phase C (Progress Report §13.3): aggregate, full audit, answer gate question,
  re-scope verdict, reconstruct h2_original_lastrow_wins.py, fresh backup

---

## Commands

```bat
:: B1 (smallest — run first)
C:\Users\UserMN4312\Documents\Zog Zoo\Zog Zoo Dev\run_b1.bat

:: B2 (medium)
C:\Users\UserMN4312\Documents\Zog Zoo\Zog Zoo Dev\run_b2.bat

:: B3 (largest)
C:\Users\UserMN4312\Documents\Zog Zoo\Zog Zoo Dev\run_b3.bat

:: B4 (diagnostics)
C:\Users\UserMN4312\Documents\Zog Zoo\Zog Zoo Dev\run_b4.bat
```

Or via the quote-safe launcher:
```
cd /d C:\Users\UserMN4312\Documents\Zog Zoo\Zog Zoo Dev
set PYTHONIOENCODING=utf-8
C:\Python314\python.exe -c "import sys; sys.path.insert(0,'.'); from zogzoo_hdc.cli import main; main(['run','--config','configs/b1_small.json'])"
```

---

## Monitoring

- Rows appear incrementally in `Zog Zoo Dev\results\rows_run.jsonl`
- Last line of process output: `[done] ...s, ... groups, ... datasets`
- Each row: `{"dataset": "...", "pipeline": "...", "D": ..., "noise": "...", "seed": ..., "status": "ok", "top1": ..., "ndcg10": ...}`

---

## Rules

1. **Do NOT edit package code while any sub-phase is running** (config_fp fingerprint).
2. **Do NOT skip the harness audit between sub-phases** — a broken harness on B1
   wastes hours on B2/B3.
3. **Resumable:** if a sub-phase crashes mid-run, just re-run the same batch file.
   It reads `rows_run.jsonl` and skips completed cells.
4. **Power-loss safe:** rows are flushed after each cell. A restart picks up
   where it left off.