# Cognitum CH40-M.7 — Same-Formula FLINT versus MPFR Branch-and-Bound

**Date:** 2026-11-03 America/Phoenix (2026-11-04 UTC)  
**Engineering:** 15/15 original datasets and 30/30 native search arms independently audited.  
**Science:** **NO_GO** — no 0.05 finite-root/global optimization closure, and no causal identification claim.

## Purpose

CH40-M.6 compared *different* certified bound formulas (FLINT/Arb positive-semidefinite Fisher-Gram vs native MPFR direct/Hadamard), obscuring arithmetic-engine effects. CH40-M.7 implements the **same proven three-parameter PSD-Gram upper bound** with directed 256-bit native MPFR, alongside CH40-M.5F's existing 256-bit FLINT/Arb implementation. Both start from the same hash-pinned original CH40-K 64-terminal frontiers, select the highest inherited cap, bisect the same widest parameter axis, and retain parent-min caps. Both call the **same independent rational/Decimal** acceptance rule on each new child **within** the search worker. Separate read-only rational replay verifies each published journal afterward.

No new numerical theory or production backend is introduced. The native MPFR code is a *research comparison adapter*, not another engine proposed for shipping.

## Frozen original-case results

| Metric | FLINT/Arb Gram | MPFR Gram |
| --- | ---: | ---: |
| Completed splits | **65** | 56 |
| New child bounds independently replayed | 130 | 112 |
| Worker timing (post-standard-library import; CPU s) | 16.953 | 16.149 |
| Full subprocess CPU incl. interpreter startup (s) | 28.398 | 27.581 |
| External, second independent audit CPU (s) | 26.716 | 24.237 |
| Combined full-child + second-audit CPU (s) | **55.114** | 51.818 |
| Cases with materially better upper frontier reduction | **5** | 0 |
| Ties at 1e-10 absolute | 10 | 10 |
| Max worker peak RSS | 425876 KiB | 426084 KiB |

Fifteen original input trace hashes verified. Both engines' first child boxes are identical for every case, and all **30 first-child caps** differ by <1e-60 (maximum observed difference ≈3.41e-75). Every one of the 242 new child caps was produced with an online independent rational check and rechecked by a **separate** read-only rational replay: **30/30** audits accepted. The original CH40-J signed proof history was **not** modified or resigned. Ten targeted M.7 regression tests passed; three basic MPFR/Arb tests also passed (**13/13**).

These are **not perfectly equal full-process CPU** runs. Each arm receives the same 1.0-second requested *post-stdlib-import* process-time cutoff, can overshoot by one atomic split, and has separately measured interpreter/startup and post-run audit costs. CPU costs and memory for actual independently executed operations are disclosed above. All experiments were isolated with 1.5-GiB virtual-address limits, 15-second wall limits, OS CPU ceilings, one OpenBLAS thread, and a 256-split safety cap that did not bind. Experiment order alternates across cases; single-trial scheduling effects remain. A formal cost-matched multi-seed replication and more efficient witness acceptance are required for production performance claims.

**Interpretation:** the previous roughly 7.3x split-count difference was **principally confounded by different mathematical bounds**. With identical Gram mathematics the FLINT implementation completes ~16% more splits at ~6% more fully accounted CPU, including independent second audits. That is a **modest** throughput benefit, not a 41x or 7.3x whole-solver speedup. FLINT is a promising optional producer, but the original certified Gram mathematics is more valuable than an arithmetic-library brand choice.

## Source, results, and reproduction

- `mpfr_gram.py` — new 256-bit directed native MPFR implementation of the original certified PSD-Gram rule; exact rational predictor bounds and Gram matrix, outward transcendental functions.
- `worker_m7.py` — one original-case search per backend, source-hash pinning and independent rational online child checks; no historical trace writes.
- `audit_m7.py` — read-only rational replay; rejects chain, partition, source-hash, underbound, status, inheritance or metadata tampering; does **not import** either native producer.
- `launch_m7.py` — isolated whole-child CPU, RAM, wall and external-audit accounting; alternate arm order.
- `finalize_m7.py` — no synthetic substitution or duplicate-case acceptance, 15/15 original cases, 30 original-run receipts and first-child equal-formula checks.
- `test_basic.py`, `test_m7.py`, `test_m7.log` — 3 basic and 10 research acceptance tests; no CI-only synthetic substitutes.
- `accepted/CH40M7_ALL15_MATCHED_GRAM.json` — summary including per-case splits, frontier reduction, CPU and memory.
- `accepted/*_arb_gram.json`, `*_mpfr_gram.json`, plus paired `*.audit.json` — 30 source-hash-pinned journals and 30 independent auditor receipts.

From an **isolated Linux research environment**, place the original read-only CH40K frozen case traces and CH40J rational reference plus CH40L/L2/L3/M5/M6 sources in one workspace, and install a compatible python-flint wheel **only in the research environment**. The original lab used `/mnt/data`. Set:

```bash
export CH40M7_WORKSPACE=/path/to/frozen/research/workspace
export PYTHONPATH="$CH40M7_WORKSPACE/CH40M3/site"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python launch_m7.py --cpu-budget 1.0 --max-splits 256 \
  --output /tmp/ch40m7-repro --cases quasi_separated_n80_i00 quasi_separated_n160_i00
python audit_m7.py /tmp/ch40m7-repro/quasi_separated_n80_i00_arb_gram.json
python test_m7.py
```

The ZIP includes this research source, summary, 30 child journals, independent receipts and SHA-256 file manifest, **not the historical large original dataset** or its signed chain. The code relies on those externally immutable original inputs. Missing original fixtures must **skip/refuse**, never silently substitute synthetic inputs or declare a scientific PASS.

## Adoption disposition

**ACCEPT AS A RESEARCH COMPARATOR; DO NOT ACTIVATE IN LU OR COGNITUM PRODUCTION.** Next gate: replace the producer only behind the existing independent witness/journal interface, profile whether verification dominates whole task latency, replicate the same-formula benchmark with tighter matched *full-process* CPU/RAM controls and held-out seeds, and independently test certified gap reductions. The finite-root 0.05 scientific certification remains unresolved.
