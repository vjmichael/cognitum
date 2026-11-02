# CH-C14-01A — Fresh Local C14 Diagnostic Smoke

Date: 2026-11-02. Linux CPU, local workspace; no Lu changes and no production estimator changes.

## Reproduction

The locally available extracted P18 source snapshot was tested:

```bash
cd /mnt/data/cognitum_full_nvp_preflight/p18
python -m pytest -q tests/test_causal_bootstrap_p18.py tests/test_causal_variance_p17.py
```

Result:

```
................ [100%]
16 passed in 0.30s
```

## What this demonstrates / does not demonstrate

This checks the *existing P17/P18 diagnostic and bootstrap unit tests* in a local source snapshot. It is a **fresh smoke pass**, not a rerun of G25N's 14,000 synthetic datasets, not its width/calibration preregistration, not external statistical review, and not production causal inference. The tests' pass cannot reverse G25N's documented 12/12 precision failure.

## Next action

Review the C14 G25 nonproduction guard and contract, rerun provenance/refusal/cancellation checks with precise fixture hashes and then run new preregistered calibration data. All proposed estimator modifications remain research-only. Maintain explicit **NO-GO** for production causal-confidence promotion.
