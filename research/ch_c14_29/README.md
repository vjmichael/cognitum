# CH-C14-29: Monotone MPFR parent-cap inheritance, same-data benchmarks

**Status:** Research-only; production C14/G25 and Lu remain unchanged. A finite coefficient-domain upper-gap certificate is not an unrestricted global-optimality or causal-identification claim.

## Mathematical invariant

If a branch-and-bound node's coefficient box \(B_c\) is a subset of its parent's effective box \(B_p\), and the verifier proves \(\sup_{\beta\in B_p}J(\beta)\le U_p\), then \(\sup_{\beta\in B_c}J(\beta)\le U_p\) independently of the new local upper bound \(U_c^{local}\). CH29 retains the stronger cap

\[U_c^{verified}=\min(U_p^{verified},\,U_c^{local}).\]

The solver computes each `min` with directed 160-bit MPFR endpoints. The proof tree includes `parent_id`, the box partition, and the local method (`direct`/`coupled`). The independent verifier **ignores stored cap display values** and reconstructs the full ancestor minimum at 224-bit MPFR precision. It checks the full coefficient-box partition and any interval-Newton contraction. A new parent cap never authorizes excluding a region without a valid enclosing ancestor proof.

## Frozen inputs and budgets

- All 15 original CH23 datasets: 12 initially selected global-bound boxes and three historical ambiguous zero-event datasets. Each frozen input JSON and CH23 data digest must match CH28's pinned originals.
- Coefficient box: `[-10,1] × [-5,5] × [-5,5]`; solve 160-bit; independent replay 224-bit; gap requirement `0.05`.
- **Equal-node:** 63 and 127 nodes on all 15 original cases, independently replayed. Report whether the CH29 127-node search improves each case relative to its own CH29 63-node search. Search order may change compared with CH28.
- **Equal-CPU:** for each case, cap CH29 solving process CPU at the original saved CH28 63- or 127-node solve CPU. The maximum permitted nodes are 127/255 respectively. The CPU stop condition is checked between complete node expansions, so a single expansion may overshoot. Record actual CPU and flag cases more than 10% away from target; do not claim exact matching. Verification CPU is measured separately.
- Source and original-baseline SHA-256 digests are frozen in `frozen_protocol.json` (`frozen_protocol.sha256`). No alternative data or updated seed schedules are permitted.

## Reproducing

From the parent directory containing `CH_C14_23` through `CH_C14_29`, with MPFR available:

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
python -m pytest -q CH_C14_29/tests
python CH_C14_29/run_case29.py zero_balanced_n80_i00 --budget 63 --mode fixed
python CH_C14_29/run_case29.py zero_balanced_n80_i00 --budget 63 --mode equal_cpu
python CH_C14_29/launch29.py --mode fixed --workers 4
python CH_C14_29/launch29.py --mode equal_cpu --workers 1
python CH_C14_29/audit29.py
python CH_C14_29/summarize29.py
```

Full replay from certificates is available with `audit29.py --replay`, which recomputes all ancestor bounds at 224-bit precision rather than trusting the evidence receipts.

## Limitations

Full MPFR replay shares the original bound implementation and is not a machine-checked proof assistant. Equal-CPU comparisons use archived CH28 process-CPU records from the same environment, not an exact CPU instruction-cycle budget. Results are a numerical engineering benchmark, not authorization to promote a statistical estimator.

## Recorded CH29 results (not a production release)

All 15 original CH23 cases were run and independently replayed under four budgets, **60/60 verified**. Mean gap results:

| Comparison | CH28 mean gap | CH29 mean gap | Improved / tied / worsened |
|---|---:|---:|---:|
| 63 nodes | 4.8259 | 4.2642 | 10 / 4 / 1 |
| 127 nodes | 3.9428 | 3.4087 | 8 / 5 / 2 |
| CH28 63-node solve CPU matched | 4.8259 | 4.3556 | 11 / 0 / 4 |
| CH28 127-node solve CPU matched | 3.9428 | 3.2767 | 12 / 2 / 1 |

**15/15** fixed 127-node runs retained the exact 63-node proof-tree prefix and a non-increasing objective gap. **30/30** CPU-capped runs finished within ±10% of the archived CH28 solve-CPU targets. All original ambiguous cases remain refused and there are **0/60 finite-box certificates at epsilon 0.05**. Independent replay CPU increased substantially due to rechecking every ancestor. Refer to `Engineering_Report_CH_C14_29.md` and `study_summary.json` for the original-case breakdown and limitations.
