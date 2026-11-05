# Cognitum C14 CH28 — cached selective MPFR bound evaluation

Research-only. Builds on the frozen CH23 15-case ambiguity cohort, the CH24 directed-MPFR core, CH26 Loewner Fisher bound, and CH27 coupled information–likelihood/interval-Newton code. **No production, G25, or Lu changes.**

## Deterministic evaluation policy

- Each node gets a directed 160-bit CH26 independent upper bound. If the result already proves the current incumbent within 0.05, skip the CH27 dual.
- Otherwise evaluate the CH27 coupled dual for root/depth≤2 and for each subsequent new node whose zero-based ID is divisible by 3. If the dual is tighter, take its minimum with the CH26 bound; if not, retain CH26.
- Keep the MPFR upper endpoint from the evaluated node in a process-local cache for search priority and terminal leaf accounting. Do not recompute it for final solver gap, which previously wasted work.
- **Verifier independent of cache:** Reconstructs the entire split tree and any interior Newton contractions at 224 bits, then recomputes terminal upper bounds by recorded proof method. Source-mode selection may affect speed and sharpness but cannot justify an excluded region without proof.

The efficiency policy is heuristic, not a statement about certified global optimum. In particular, with too few nodes, even an excellent local maximum remains **UNRESOLVED_REFUSE_CERTIFICATION**. The verifier rejects a forged certified status.

The frozen cohort is 15 original CH23 datasets with separately recorded digests. Coefficient domain remains [-10,1] × [-5,5] × [-5,5]. Solve 160-bit; replay 224-bit; 0.05 objective-gap threshold. CH28 preregistered both 63- and 127-node budgets.

## Run

From the parent of CH_C14_28, with Python 3.13, NumPy, SciPy, MPFR:

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
python -m pytest -q CH_C14_28/tests
python CH_C14_28/run_case28.py zero_balanced_n80_i00 --budget 63
python CH_C14_28/run_case28.py zero_balanced_n80_i00 --budget 127
python CH_C14_28/audit28.py
# For full, slower independent re-evaluation of all terminal proof bounds:
python CH_C14_28/audit28.py --replay
```

All 15 cases, not just the sample shown here, are listed in frozen_protocol.json. The run creates per-case proof trees, replay receipts, and CPU/wall logs in `runs/{63,127}/`.

Scientific release and unbounded global optimality remain **NO-GO**.