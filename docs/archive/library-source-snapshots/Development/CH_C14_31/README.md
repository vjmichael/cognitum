# Cognitum CH-C14-31 — progressive verification + cold-restart reattestation

**Status:** isolated numerical research. No production C14/G25/Lu changes; scientific NO-GO.

## Original inputs, not synthetic substitutes

Uses precisely the original 15 CH23 datasets, CH29 fixed/63 and fixed/127
certificates, CH27 frozen dual matrices and the original CH29 frozen protocol.
Checks SHA256 of every source-bound input, protocol, and archived certificate.
The intermediate budget stages **7, 15, 31, 95** are *derived, closed-prefix
certificate projections*, **not actual newly executed CH29 solver runs**.

## Procedure

After extracting the complete CH31 reproduction package on Linux with
`libmpfr.so.6`, Python, and project dependencies installed:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -q CH_C14_31/tests/test_progressive.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python CH_C14_31/benchmark31.py --workers 4
python CH_C14_31/audit31.py
# Verify restart with an original CH23 case in a clean Python process:
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python CH_C14_31/restart31.py --case zero_balanced_n80_i00
```

The benchmark visits six node budgets (7/15/31/63/95/127) in one trusted
process per dataset; each restarted process must replay the full original
63-node certificate from scratch before it can verify 95/127 incrementally.

The state has **no serialization/import API** and any `benchmark_results.json`
receipts remain *diagnostic*, not source authority. Inputs and saved certificates
must be revalidated after restart. This does not defend against arbitrary
malicious Python executing **inside** the trusted verifier process.

## Proof boundaries

- MPFR solver 160 bits; mathematical replay 224 bits, directed rounding.
- Existing CH29 root domain `[-10,1] × [-5,5] × [-5,5]`.
- Every certificate recomputes new upper bounds and ancestor inheritance;
  old bounds may be reused only after verification in the *same process*.
- Original CH23 ambiguities remain refused; no global \(\mathbb{R}^3\), uniqueness,
  causality, calibration, or scientific production claims.
- No changes to frozen CH23–CH30 source or to pinned G25.

See `Engineering_Report_CH_C14_31.md`, `frozen_protocol.json`,
`benchmark_results.json`, `audit31.py` and `tests/test_progressive.py`.