# Cognitum P23 — trained temporal SSM checkpoint

P22b (wind/drag KAN) was already finished. This archive contains the next planned milestone, **P23**: actual Linux-only offline training and benchmarking of the existing bounded diagonal SSM on **synthetic 1D occluded velocity tracking**.

The source is inside `source/`, the trained parameters and fresh audit are inside `results/`, and the full engineering report is at the archive root. `source/development_wheel/` contains the development wheel updated with the P23 research-only module. No Cognitum production API was changed; Windows work stays deferred. This is not a live safety controller, camera perception system, or trained NVP Acting Coach.

Reproduce from `source/` with Python 3.13, NumPy, PyTorch and pytest:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=. python train_ssm_temporal_p23.py --output ../retraining --steps 700
OPENBLAS_NUM_THREADS=1 PYTHONPATH=. python audit_ssm_temporal_p23.py --output ../retraining
P23_RESULT_DIR=../retraining OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=. pytest -q tests/test_ssm_temporal_p23.py tests/test_training_artifacts_p19.py
```

SHA-256 verified member manifest `SHA256SUMS_P23.json` is included. Original P19 JSON artifact remains `trained:false` by strict schema; separate research receipt asserts it arose from training and remains explicitly `production_approved:false`.

Read `Engineering_Report_P23.md` for the numerical results, assumptions, and caveats.
