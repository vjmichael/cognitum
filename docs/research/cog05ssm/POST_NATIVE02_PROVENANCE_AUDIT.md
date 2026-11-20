# NIST observed-data provenance and rights reconciliation — November 20, 2026

## Identity and independent numeric cross-check
Using the NIST/ITL publicly published plain-text StRD tables, compare every displayed response/predictor pair with the version-locked project transcription under `research_tests/ssm_postnative02/data/`. This comparison is **row-by-row numerical agreement**, **not** a downloaded-origin binary provenance attestation.

| External reference | Observations checked | Value discrepancies | SHA256 of the **project CSV**, not upstream .dat |
|---|---:|---:|---|
| [Norris.dat](https://www.itl.nist.gov/div898/strd/lls/data/LINKS/DATA/Norris.dat) | 36 | 0 | `75973a50205dadcc2876336eb7a9645128602b1463d18b8d928ed5cbf5bd59b0` |
| [Misra1a.dat](https://www.itl.nist.gov/div898/strd/nls/data/LINKS/DATA/Misra1a.dat) | 14 | 0 | `ae55d8e2a3f3d5bdc169a08cb46ef2669fd872c46657c859b3edd65f48875217` |

Norris source describes 36 ozone-monitor calibration observations, two-parameter linear regression and certified regression values. Misra1a source describes 14 dental adsorption pressure/volume observations, nonlinear saturation and certified values. Independent coefficients and SSE are verified in the existing POST-NATIVE-02 test suite. **Neither dataset is an observed dynamical state trajectory; neither validates the KAN mathematical vector-field fixture as a physical law.**

## What is NOT proven
- A SHA-256 digest of the original NIST **.dat bytes** was not downloaded and independently authenticated. Content checking here is limited to the 50 publicly displayed numeric pairs and their ordering. The checked CSV digests do not authenticate the origin, publication time or integrity of NIST's upstream files.
- NIST explicitly identifies the Statistical Reference Datasets collection as **NIST Standard Reference Database 140** (https://www.itl.nist.gov/div898/strd/ and https://www.nist.gov/srd/srd-catalog). NIST's [licensing policy](https://www.nist.gov/open/copyright-fair-use-and-licensing-statements-srd-data-software-and-technical-series-publications) distinguishes protected SRD from ordinary government-employee works. The public availability of the individual Norris/Misra1a pages does **not** itself establish their applicable redistribution license, any terms/permission, or whether these individual tables have distinct third-party rights. Dataset-specific reproduction/distribution rights determination and any required attribution/permission remain **OPEN**; do not assert public domain, free commercial redistribution or an unconditional license.
- The 14/36 small scientific measurement datasets give no independent time order or state derivatives, so do not assert discovered physical dynamics or real-world uncertainty calibration.
- Split-conformal marginal coverage is conditional on exchangeability; IID synthetic experiments and negative distribution-shift tests do not imply universal or conditional coverage. Misra1a calibration/test partitions are particularly small; no general out-of-domain guarantee.
- Mathematical checkpoint fixtures test represented functions and numerical integration only. They do not establish scientific truth, general KAN training/identification, uncertainty propagation under model mismatch, or actuation authority.

## Scientific qualification disposition
Classify claims separately as (a) NIST table numeric reproduction, (b) independently certified numerical regression agreement, (c) causal/protocol/data custody, (d) synthetic KAN/HDC/SSM functional tests, and (e) genuine physical-law validation (NOT TESTED). Keep the capability register marked PARTIAL where broad acceptance remains. No user-facing display precision changes affect internal evidence.

Cross-platform POST-NATIVE-02 native acceptance is tracked in the separate, source-locked qualification branch `cognitum/ssm-postnative02-native-20261120` at `4a33cbec2d1103eabd13d704c8f7d3eb9de68eef`; source code and tests must not be changed on that branch merely to record provenance.
