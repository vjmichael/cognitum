# Cognitum P21 — first HDC training handoff

Linux-only, synthetic-only, non-production. Includes the P20 source baseline plus new P21 code, actual trained HDC centroid checkpoint, independent-seed audit, development wheel and tests.

## Reproduce

```bash
cd cognitum_p21_training
PYTHONPATH=. python train_p21.py
PYTHONPATH=. python audit_p21.py
PYTHONPATH=. pytest -q tests/test_grounded_hdc_p21.py tests/test_training_artifacts_p19.py tests/test_world_grounding_p20.py
```

`train_p21.py` uses 2,400 training examples and 600 validation examples to select among six HDC configurations. The 900-case development test was examined during the experiment and is **not** an untouched final test. `audit_p21.py` runs the frozen choice on 5,400 newly seeded synthetic examples. Exact synthetic evidence matching is performed before HDC, so this is evidence policy training rather than open-world physical understanding.

The trained weights are in `artifacts/p21/hdc_evidence_classifier_p21.npz`. Verify its SHA256 using `artifacts/p21/checkpoint.sha256`. `training_report.json` and `independent_audit.json` preserve metrics, per-scenario checks and dataset fingerprints. `development_wheel/` is a rebuilt local wheel with the P21 research module and a verified RECORD. No trained model has been promoted.

NVP remains an application, not the restriction of Cognitum. All Windows-related Cognitum work and P15 stay deferred; no Lu changes.
