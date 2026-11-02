# Cognitum P22b — Linux research handoff

**This is research, NOT a physical safety or drone controller.** Two trained RBF KAN variants predict stopping distance in a custom 1D ODE simulator with wind, drag, braking delay and actuator lag. Both fail at least one physical monotonicity/calibration gate and lose to the numerical solver. No changes to Lu, production Cognitum algorithms, Windows, or P15.

Reproduce from the bundled `work/` root with NumPy, SciPy, scikit-learn, PyTorch (CPU), pytest and protobuf installed:

```bash
OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=. python train_kan_dynamics_p22b.py --output evidence/p22b_replay
OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=. python audit_kan_dynamics_p22b.py --evidence evidence/p22b
OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=. python -m pytest -q tests/test_kan_dynamics_p22b.py tests/test_kan_dynamics_p22.py tests/test_kan_decoder_p18.py tests/test_training_artifacts_p19.py tests/test_component_quality_p17.py
```

New files:

- `work/cognitum/research/kan_dynamics_p22b.py`: bounded 6-variable simulator, inference policy and live-parameter guard.
- `work/train_kan_dynamics_p22b.py`: offline two-model training, validation, calibration, regression baselines and test metrics.
- `work/audit_kan_dynamics_p22b.py`: **no retraining** fresh-seed post-freeze audit with paired bootstrap CIs.
- `work/tests/test_kan_dynamics_p22b.py`: independent ODE reference and security/negative tests.
- `work/evidence/p22b/kan_wind_drag_lag_p22b*.npz` and `*receipt.json`: *actual trained* bounded portable weights and non-production receipts.
- `work/evidence/p22b/results.json`, `postfreeze_audit.json`, `uniform_test_predictions.csv`: detailed results and case-level output.
- `work/development_wheel/`: rebuilt independently smoke-tested development wheel.
- `work/build_p22b_wheel.py`: deterministic `RECORD`-validating wheel reassembly.

Important: `P22b` is a local source snapshot/overlay built from the P22 artifact. GitHub is the repository and milestone record, not the development environment. The research branch carries the report, not yet merged source. Prior Linux kernel acceptance, live supervisor deployment and causal inference production requirements remain open.
