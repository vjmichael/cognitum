# Cognitum C14 G25H — independent parametric stacked variance research

**Research-only:** no Cognitum production module, Lu code, or release pipeline was modified.

This package contains the G25H two-cohort heldout study (8,000 fixtures; four nuisance specifications, two score/sandwich uncertainty estimates plus a nondeployable synthetic oracle), a separate 1,200-case observed-data sentinel study, a 256-case global Jacobian numerical cross-check, and SHA-256-audited receipts.

## Primary result

Doubly misspecified nuisance working models can produce dramatically biased AIPW point estimates even when reported SE approximately tracks the empirical estimator SD. A variance correction alone cannot repair lack of consistent causal estimation. A numerical interval returned on hidden-confounder data is not proof of identification.

## Reproduction

Use Python 3.13, NumPy, SciPy, pytest; choose single-thread linear algebra. From this package's root:

```sh
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH=tools
python tools/run_g25h.py A
python tools/run_g25h.py B
python tools/audit_g25h.py A
python tools/audit_g25h.py B
python tools/g25h_combine.py
python tools/g25h_observed_sentinels.py
python tools/audit_g25h_sentinels.py
python tools/verify_g25h_independent.py
pytest -q tests
```

Check `G25H_Freeze_Record.md` and both `G25H_Frozen_*.json` protocols before executing. The observed sentinel was frozen separately after the primary study; its documented pre-results harness correction is preserved in `G25H_Observed_Sentinel_Deviation.md` with both original and corrected protocols. No code changes to the primary research core after its freeze. `SHA256SUMS.json` lists the files in the packaged archive, excluding itself.

## Scientific status

G25H research complete; **G25 overall scientific acceptance NOT MET**. R Firth external package verification remains unperformed. The two Python Firth optimizers share the same mathematical objective and are not claimed to independently establish implementation validity in external software.