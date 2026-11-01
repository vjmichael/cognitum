# Cognitum C14 G25D — isolated research package (2026-11-01)

**No Cognitum production estimator changes. No Lu edits. No permission to promote a CI method.**

## Contents

- `G25D_Predeclaration.json`: primary A scientific protocol; SHA-256 frozen before A holdout.
- `G25D_Replication_Predeclaration.json`: independent positive-dataset seeds for B, frozen after viewing A but before B run.
- `G25D_Support_Probe_Addendum.json`: separate observed-support safety probe, preregistered before its own seeds, after A/B.
- `tools/g25d_research.py`: isolated simulation and two fitted cross-fit AIPW research estimators plus privileged oracle.
- `tools/run_g25d.py`: deterministic primary and replication runners.
- `tools/audit_g25d.py`: separate structural auditor, source hash verification and same-code exact replay.
- `tools/g25d_support_probe.py`: observed deterministic non-overlap and stochastic comparison diagnostic.
- `tests/`: 20 verified local scientific/integrity tests.
- `results/`: lossless compressed receipts, model summaries, independent audit, and the additional support probe.
- `G25D_Engineering_Report_2026-11-01.md`: findings, caveats, acceptance gates and next engineering steps.
- `SHA256SUMS.json`: file-level integrity manifest.

All scripts run offline with Python 3.13, NumPy and SciPy. No Docker, third-party model downloads, Lu GUI, elevation, or network is required.

## Run

From the archive directory:

```sh
python -m unittest discover -s tests -v
python tools/audit_g25d.py
python tools/g25d_support_probe.py
```

The complete primary and replication receipts are included. To reproduce them, use:

```sh
python tools/run_g25d.py
python tools/run_g25d.py --config G25D_Replication_Predeclaration.json --output results/G25D_replication_receipts.json.gz --summary results/G25D_replication_summary.json
```

Re-running a primary result intentionally overwrites that receipt; the SHA256 manifest will then need regeneration, since gzip timestamps make byte hashes differ even when decoded JSON is identical. The audit verifies the archived original-byte hashes; move/copy the entire package first if rerunning.

## Interpretation

- **12,000 unique positive/stress synthetic datasets; 36,000 method receipts.** Two cohorts with disjoint positive-case seeds. There are 300 metadata-only controls repeated across cohorts, not 600 independent controls.
- **G25 acceptance remains failed:** the >=99% positive-case completion gate does not hold in every n=900 primary and replication cell, and uncertainty-proof/external causal-library checks are unfinished.
- `weak_overlap` is quantitatively near-zero but not structural zero. The oracle values are nondeployable. Only the separate `g25d_support_probe` covers actual deterministic support contradictions.
- Continuous-X overlap, ignorability and resistance to hidden common causes cannot be established by a coarse observed support test or a band around fitted propensity.