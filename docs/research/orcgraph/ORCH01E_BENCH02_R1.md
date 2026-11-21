# COG-ORCH-01E-BENCH-02-R1 — external source, receipt-time admission

**Status: STAGED / LOCAL SOURCE-GATE TESTS ONLY. No new scientific benchmark or native acceptance.** Original BENCH-01 remains accepted at SHA 8d0b1d2d, 436/436 on four platforms, with 2/5/2 default and 3/4/2 opt-in wins/losses/ties. No consistent ridge superiority.

## Candidate source (not yet acquired or independently attested)
Use the official NOAA/NWS Aviation Weather Center (AWC) [METAR Data API](https://aviationweather.gov/data/api/), from the HTTPS \`/api/data/metar\` JSON endpoint. It supplies original report text, station identity, \`obsTime\` (Unix seconds), \`receiptTime\` (AWC received the report) and temperature in Celsius. This differs materially from previously used UCI/USGS historical excerpts and supports independent station selection. Public API documents access of up to 30 days, maximum responses and rate limits.

**Do not conflate AWC receipt with historic public data availability.** The source's \`receiptTime\` does not prove a user could read the observation then. An old report downloaded later cannot be used in a historical 'as-of' forecast before its first independently witnessed acquisition. The first-capture clock must come from a protected, independently verified host journal/attestor. A user-declared clock, URL, SHA or capture-reference string alone is not authenticated transport or time custody. Original sensors are not signed by these fields. Only original acquisition and independent corroboration can establish the bounded causal use.

## R1 implementation boundary
\`tools/orcbench02/availability_gate.py\` validates original raw UTF-8 JSON byte SHA-256, exact HTTPS source/query/ICAO, original report identity, observation/receipt/capture order, nonduplicate monotonically ordered observations and finite Celsius→Kelvin conversion. Missing temperatures stay missing and are counted. Revisions/duplicates, source conflicts and impossible clocks **refuse**, not silently intersect or rewrite the evaluation cohort. Candidate \`provisional_asof\` excludes any reading observed/received/first-captured after the proposed forecast origin; it is **research-only** and does not attest historic access. All outputs retain explicit \`NOT_QUALIFIED_UNTIL_INDEPENDENT_CAPTURE_ATTESTATION\`, with production admission false.

R1 tests use synthetic JSON only. No real external data was fetched; no forecasts, benchmark scores, source rights/instrument signatures, installed host auth, OS-enforced budgets or measured user–AI synergy are established. Local Python tests are not four-platform native acceptance.

## Remaining gates
1. **BENCH-02-R2:** independently acquire original AWC bytes, pin digest/URL/rights/source and protect verified first-fetch clock and revisions in a trusted append-only receipt. Do not treat reconstructed historical retrieval as past public availability.
2. **BENCH-02-R3:** pre-register previously unseen physical stations, unit/horizon and eligibility rules BEFORE measuring heldout outcomes. Handle irregular station observations, missingness/late/corrected reports, 60/20/20 train/cal/test chronological splits, strict as-of features and identical heldout origins without imputation.
3. **BENCH-02-R4:** independently calculate matched direct ridge, AR24, time-aware SSM, persistence, conservative and research-opt-in Orc. Report MAE/RMSE, dimensionless per-series gain, wins **and losses**, abstention and dependence-aware uncertainty limitations; no model choice based on test scores.
4. **BENCH-02-R5:** native Windows/Linux Python 3.11/3.13 unchanged-SHA qualification, independently verified JUnit/ZIP/CRC/Git object/actual prediction and trusted capture evidence.
5. **COG-ORCH-FIN-01:** separate source convergence, installed MEL host authorization, physical resource enforcement and user interaction. CH⊕aT user benefit remains independently unmeasured.

**Release state:** BENCH-02 OPEN; BENCH-01 scientific result unchanged; no new GitHub Actions run should stack on another run.
