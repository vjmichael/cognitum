# COG-ORCH-01B — Shared scientific data pipeline and source-lock acceptance

**Status: BOUNDED ENGINEERING CANDIDATE; terminal four-platform native acceptance PENDING.** This is a first-party, CPU-only, data-preparation and compatibility layer: it is NOT a learned router, a second host executor, an empirical accuracy-improvement claim, a sensor attestation authority, a license adjudicator, or a production Lu tool.

## Supported data contract

- Inputs are original immutable UTF-8 CSV bytes, provided by the host, with exactly `timestamp_ms,available_ms,value,observed,observation_id` fields. A declared original SHA-256 must match actual bytes; source publisher/reference, rights status and unit-evidence status are attached without falsely certifying the original physical sensor.
- Every observation has a UTC Unix-millisecond event timestamp AND earliest recorded availability timestamp. Both are explicit; available time must not precede measurement time. A value is either an explicitly observed finite float or truly missing (`observed=0`, blank value); no silent imputation, interpolation, inferred sensor signature or future data.
- Strict physical quantity/unit pair (`discharge:m3/s`, `water_level:m`, `temperature:K`, `dimensionless:1`). Other quantities and conversions fail closed until independently reviewed, typed conversion contracts exist.
- Irregular observations preserve exact event times; a declared regular sampling interval requires every expected timestamp, including an explicit missing row. Unmarked gaps, duplicates, unsorted timestamps, duplicate observation IDs, invalid rows and noncanonical timestamps refuse.
- Bounded read: 2 MiB and 50,000 rows; full derived series retains immutable source identity and rights evidence as *reported*, not authenticated.
- Chronological first 60% train / next 20% calibration / final 20% untouched test by ordered observation rows. Train statistics use only train observations with `available_ms <= end_of_train`; transformation source, cutoff and training fingerprint are reverified before feature preparation.
- Exact-time lagged numeric forecasting examples include two numeric features: current origin observation and prior measured lag. Both must be published by the forecast origin; target must match the precise future horizon within the same declared fold and is stored separately as a label. Missing/unavailable/invalid target examples are counted as skipped, never silently filled.
- Host-provided candidate contracts can independently assess exact quantity/unit, UTC clock, regular/irregular policy, explicit missingness, and declared/publisher-reported unit provenance. Compatible does NOT mean authorized, scientifically appropriate, or accurately predictive. Source-backed HDC/KAN/SSM/ridge are not yet worker-executable through Orc Graph.
- `assert_matched_cohorts` refuses mismatched source/fold/horizon/origin sets rather than silently intersecting candidate samples and inflating a benchmark. This is **infrastructure** for future independent comparison, not the comparison itself.

## Limitations and negative conditions

Science-specific causal drivers and domain validity are NOT inferred. This ingestion contract has not yet adapted or re-qualified original R4 NOAA/USGS dataset CSV layouts. CSV `available_ms` is required and should come from independently credible publication/revision records; synthetic or user-reported availability times are not automatically authenticated. This module cannot establish upstream sensor credentials, raw gauge units, provenance rights, as-of corrections or truly independent physical publishers. It does not certify conditional coverage, forecast quality, HDC/KAN/SSM integration, or numerical reproducibility.

## Native acceptance gate

Run all ORCH-01B dedicated cases plus the prior unmodified ORCH-01A and existing two COG-06 cooperative test suites, each on Ubuntu and Windows with Python 3.11 and 3.13. Archive JUnit with full exact testcase identities, source and test SHA256 and canonical Git blob IDs, resolved dependency versions, and exact workflow SHA. Reconcile all four independently downloaded ZIP artifacts before source-locked PASS. Do not stack CI, weaken tests, turn on research by default, or alter the accepted ORCH-01A SHA 5345c998ddd84b22063a7a5b865ff586644b424a or R4 physics SHA cf78900c4fcec3981b93c842144c53b15cc0d411.

**Next:** ORCH-01C existing-runtime input handoff and bounded execution; ORCH-01D matched candidate scientific comparison; ORCH-01E model selection/decision and operator review. Independent R4-R1 source and KAN checkpoint holds remain open.
