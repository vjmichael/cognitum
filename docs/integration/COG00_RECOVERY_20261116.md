# COG-00 — historical source recovery and reconciliation

Baseline: unified candidate PR #81 at `3211fa1223c978039a3202b224539745eef912b5`. This is a source-only research recovery candidate, not release or scientific acceptance. Main and existing PR branches remain unchanged.

## Source reconciliation

- Restore the 15 original recovered HDC modules, canonical candidate verification, admission, revision lifecycle, tests and benchmarks from PR #79. The canonical verifier still requires a separately trusted, scoped Lu ANSF snapshot. HDC is not canonical memory.
- Restore the P3 signed KAN approval schema, generated descriptor, signed/revocation tests and local integrity ledger. The ledger is a research reference with caller-provided epochs/digests, not a protected host authority or rollback-proof store. Its legacy deliver_hdc method returns candidate bytes, never trusted facts; COG-02 must require independently authenticated current canonical verification before any host publication. Keep this API out of production routing.
- Restore the later P25 portable spline endpoint fix and its original regression. Retain the newer, bounded SSM kernel (including constructor, overflow and restart-state fixes); the historical ssm_recovered name is an explicit re-export rather than a second implementation. Preserve the original recovery tests and new alias identity/restart test.
- Preserve original reports and reproduction guides, including the HDC/KAN guide from PR #82. A report or checksum does not restore a missing checkpoint. No third-party source, live data, private keys or large archives imported. The exact selected source blobs and prior replacement hash are recorded in COG00_SOURCE_PROVENANCE.json.
- Deliberately leave the historical specialists.py plugin off this branch: it permits an environment-variable KAN pin rather than the signed/revocable approval boundary, and uses a separate JSON/base64 dispatch. Reconcile the route at COG-02 rather than restoring a bypass. C08/C09 research stays default-off; no CLI/registry/worker/host activation changes.
- Do not wholesale merge the divergent P25 or PR #79 branches; do not replace C05 or other unified Protobuf schemas. PR #82 continues to preserve the broader historical C14/C15 archive independently.

## Library inspection (2026-11-16)

The historical paths /Zog Zoo, /torchHD-main and /pykan-master no longer resolve; no matching standalone connected GitHub repository was found. The Cognitum root still contains Checkpoints, Datasets, Development, Packages and Reference Docs. All 772 entries in the paginated Development listing were inspected by name; none matched HDC/KAN/SSM/P21-P25. Checkpoints, Packages, Reference Docs and Datasets were also inspected by name. The HDC/KAN training guide survives; TrackEval archives survive. No trained checkpoints or training overlays were identified in these locations. This is not proof that all other Library locations, local PCs, or expired workflow artifacts lack copies.

## Remaining blockers

Original trainable K4 KAN source, K4 performance overlay, trained P21-P25 HDC/KAN/SSM overlays and models, original data/split manifests and independently authenticated archives remain missing/unverified. Reconstruct only from verified source, documented seeds and licensed data; mark newly trained models as new artifacts. The old C14 research and broad acceptance remain separate. No COG-00 production promotion.

## Grouped acceptance required (not performed here)

Install on clean Windows/Linux Python 3.11 and 3.13: python -m pip install -e '.[research-hdc-kan,security]' 'scipy>=1.14,<2' 'threadpoolctl>=3,<4' 'pytest>=8,<10' 'grpcio-tools>=1.70,<2'. Then run the unchanged original focused tests plus COG-00 alias tests:

```sh
python -m pytest -q tests/test_research_optional.py tests/test_c08_admission.py tests/test_c08_canonical.py tests/test_c08_lifecycle_recovery.py tests/test_c08_index_lifecycle.py tests/test_c09_signed_approval.py tests/test_research_durable.py tests/test_hdc_kan_ssm_recovery.py tests/test_hdc_recovered_extended.py tests/test_kan_spline_endpoint_p1.py tests/test_ssm_state_resume_p1.py tests/test_cog00_ssm_alias.py
python -m cognitum.research.hdc_recovered.selftest
python -m tools.run_hdc_kan_ssm_recovery_benchmark
python -m tools.run_c08_candidate_benchmark
python -m tools.run_c08_conventional_baselines
python -m compileall -q cognitum tests
```

Also compare compiled kan_approval protobuf descriptor to the checked-in generated descriptor, run the combined regression with all appropriate optional dependencies, and retain exact-SHA results before merging. Historical green results do not establish acceptance here. Source recovery is not training or efficacy verification.
