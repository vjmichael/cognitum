# Cognitum CH-C14-26 — Verified MPFR determinant/Hessian improvement on original CH23 data

Research-only Linux implementation. No changes to CH23/CH24/CH25, production C14/G25 or Lu.

The **same 15 CH23 datasets** are sourced from the immutable CH25 inputs and tied to their original CH23 SHA-256s by `frozen_protocol.json`. No synthetic replacement fixtures were used in the benchmark. The full release ZIP contains sibling `CH_C14_23/`, `CH_C14_24/`, `CH_C14_25/`, and `CH_C14_26/` directories. Extract the archive and run the commands below from `CH_C14_26/`. The GitHub research branch uses lowercase directory names; if running directly from a checkout, extract the CH25 evidence ZIP to provide the original inputs and add the CH24 folder to `PYTHONPATH`.

## Commands

```bash
cd CH_C14_26
OPENBLAS_NUM_THREADS=1 python -m unittest discover -s tests -v
OPENBLAS_NUM_THREADS=1 python run_case.py zero_imbalanced_n160_i05
python compile_results.py
```

Requirements: Python 3.13, `libmpfr.so.6`, NumPy/SciPy needed only to rerun the historical CH23 generator audit. `solver26.py` and `verifier26.py` import the exact CH24 MPFR interval primitives; the original CH25 dataset files are taken from the CH25 archive. The run is bounded to `[-10,1]×[-5,5]×[-5,5]`; certificate replay at 224 bits never promotes an unresolved gap.

- `improved_bounds.py`: Loewner Gram determinant + logistic concave tangent + analytic interval Hessian.
- `solver26.py`, `verifier26.py`: interval branch-and-bound and exact partition/high-precision replay.
- `frozen_protocol.json`: SHA-256 frozen 15 cases, source hashes, precise budget/claim parameters.
- `certificates/`, `verifications/`, `logs/`: saved proof trees and CPU/wall timing receipts (in evidence ZIP).
- `Engineering_Report_CH_C14_26.md`, `study_summary.json`: full held-out baseline comparison and remaining limitations.

**All scientific and unrestricted-global certification remains NO-GO.**
