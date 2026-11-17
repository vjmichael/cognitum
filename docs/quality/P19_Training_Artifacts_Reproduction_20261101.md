# Cognitum P19 — Training artifact readiness

Linux-only, offline, non-production overlay for P18. **No Lu changes. Windows and P15 deferred.**

Quick check:

```bash
PYTHONPATH=. python -m pytest -q tests/test_component_quality_p17.py tests/test_specialist_scale_p18.py tests/test_kan_decoder_p18.py tests/test_training_artifacts_p19.py
PYTHONPATH=. python evidence/run_hdc_synthetic.py
```

* HDC new research trainer: `cognitum/research/hdc_training_p19.py` — `fit_centroid(...)`, `.to_bytes()`, `HDCClassifier.from_bytes(bytes, external_sha256)`. Store the NPZ bytes explicitly to a host-owned path; no default disk writes or memory integration.
* KAN existing inference: `cognitum/research/kan_portable.py` — `PortableKAN.save(path)` stores numeric model parameters in `.npz`; `kan_optional.predict` requires SHA pin. P19 record: `cognitum/research/kan_training_record_p19.py`, paired canonical JSON. No optimizer-state resumption or new trainer.
* SSM existing recurrence: `cognitum/specialists/ssm.py` — request parameters are transient. P19 `ssm_artifact_p19.py` exports/imports a pinned JSON coefficient set. No training yet, no runtime state persisted.
* `examples/` contains intentionally synthetic fixtures, **not trained production Cognitum models**. P19 HDC checkpoint shows how persistence works. KAN fixture is hand-constructed, SSM coefficients are hand-selected.
* Wheel in `development_wheel/` contains updated research module code and a verified wheel RECORD, but is neither cryptographically signed nor production-certified; hash pinning is integrity, not a cryptographic signature.

Use `SHA256SUMS_P19.txt` to verify the full package. See `Engineering_Report_P19.md` for details and cautions.
