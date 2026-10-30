# Cognitum C15 T4 P3 — held-out falsification and claimed-uncertainty evidence audit

**2026-10-29.** Research-only reference. A portable P3 *evaluation method* is implemented and tested; **the real externally measured held-out engineering validation gate is OPEN**. C15 T3 VirtualBox reboot/hard-off/snapshot rollback tests are deferred, not passed. Lu and physical/robotics action authority are untouched.

## Purpose and existing methods

The P1/P2 model evaluates **conditional compatibility of caller-supplied engineering assertions**. It cannot authenticate either those assertions or physical safety. P3 tests whether its decisions disagree with independently supplied reference labels and whether an observed fit clearance falls inside its claimed numerical bounds. Standard reference methods used: 95% Wilson binomial score intervals for observational error-rate/coverage diagnostics, the dimensioned SI conventions of NIST and the GUM caution that a measurement interval needs a justified probabilistic interpretation. No confidence probability is automatically assigned to P2's worst-case engineering intervals.

References: [NIST measurement uncertainty](https://www.nist.gov/itl/sed/topic-areas/measurement-uncertainty), [NIST TN1297 uncertainty reporting](https://www.nist.gov/pml/nist-technical-note-1297/nist-tn-1297-7-reporting-uncertainty), [JCGM GUM 100:2008](https://www.bipm.org/documents/20126/2071204/JCGM_100_2008_E.pdf). These standards inform reporting; this implementation is **not** an ISO/JCGM-certified metrology instrument.

## Protobuf contract and evaluator

- `proto/cognitum/spatial/v1/functional_material_p3.proto`: additive, versioned P3 request/case/result and rate schema; compiled binding `cognitum/proto/spatial_functional_material_p3_pb2.py` generated using the existing pinned protoc 3.13.0 binary. P1/P2 schemas unmodified.
- `cognitum/spatial_functional_material_p3.py`: bounded request-level evaluator (at most 160 cases, 1.8 MB serialized), strict canonical source/binding check, conversation scope and source identity checks, rejection of reused source references, duplicate specimen groups, and identical P2 scenarios crossing calibration vs holdout partitions. Validates and executes the P2 kernel for each case. It returns ONLY content-free finding IDs, error indicators and aggregated counts; no secret journal material or read/write actions.
- Observation status is **caller-declared**; reference SHA-256 identifies an asserted record but does not sign it, authenticate provenance, prove true statistical independence or establish physical truth. A valid `T4_MEASUREMENT_ASSERTED` P2 input is not cryptographically verified measurement evidence.
- P3 explicitly computes `false_positive` as **P2 CONSISTENT** when observed reference says **VIOLATES**, and `false_negative` as **P2 CONTRADICTS** when reference says **SATISFIES**. Reference-unknown observations are not silently treated as true negatives. Abstentions are included in decision coverage but not the selective-error denominator. FPR and FNR denominators are all labelled violating/satisfying examples, respectively, including abstentions. All undefined rates use `defined=false`, not invented zeros.
- 95% Wilson interval endpoints are provided only as sample-level exploratory uncertainty under assumptions (independent Bernoulli trials and representative labels). Group IDs are checked for uniqueness but independent acquisition is NOT authenticated. Minimum case counts gate exploratory interpretation; no production error threshold is inferred.
- For fit findings only, an optional SI **observed clearance** audits whether the observed number is inside P2's caller-asserted [min,max] range. Because these are NOT calibrated predictive intervals, nominal coverage defaults to **NO_PROBABILITY_COVERAGE_CLAIM**. When a user separately asserts a nominal target, a Wilson diagnostic reports whether the target is excluded, supported or inconclusive; it does not transform P2 intervals into calibrated probabilities. Mixed load-ratio and clearance units are explicitly rejected. No P2 learning or update is performed from the calibration partition, and a sample is never transferred into the holdout set by this code.
- Reports retain `research_only=true`, `grants_authority=false`, `independent_evidence_authenticated=false`, `physical_validity_verified=false`. Source hashes, labels and P2 results never grant execution, deployment, sensing or physical actuation permission.

## Synthetic out-of-sample falsification exercise

`evals/c15_t4_p3_synthetic_heldout.py` constructs **40 synthetic calibration + 40 synthetic holdout** fit specimens. An independent Decimal arithmetic oracle derives reference clearance and binary fit labels from a separately declared *simulated* specimen; the P2 scenario uses independently asserted nominal geometry. The held-out partition deliberately has more corrupted nominal-vs-actual shaft claims. This exposes the limitation of algebra that trusts inputs. The fixture/partitions are **in-repository, fixed and reproducible**, not externally sequestered, domain-reviewed real hardware data or a preregistered clinical/scientific trial. This evaluator is NOT trained on the calibration partition.

| Metric | Synthetic calibration | Synthetic holdout |
|---|---:|---:|
| Cases | 40 | 40 |
| Decisions / abstentions | 35 / 5 | 35 / 5 |
| Conditional decision disagreement | 5/35 (14.3%) | 15/35 (42.9%) |
| False-positive among labelled violations | 5/20 (25.0%) | 10/20 (50.0%) |
| False-negative among labelled satisfactions | 0/20 (0.0%) | 5/20 (25.0%) |
| Claimed fit-interval empirical coverage | 35/40 (87.5%) | 25/40 (62.5%) |
| Separate asserted nominal target | 90% (inconclusive) | 90% (below target by Wilson upper bound) |

The falsification is **deliberately injected** and therefore is not an unbiased estimate of Cognitum's deployment quality. It illustrates that apparently robust P2 predictions can be wrong when inputs omit calibration bias or the actual specimen differs from the claimed input. The 95% binomial intervals in JSON do not make the synthetic design representative of any target distribution.

`docs/components/spatial/C15-T4-P3-synthetic-falsification-evidence-2026-10-29.json` contains all summary metrics, flagged specimen IDs and reproducible plan/study SHA-256. Local Python-only 80-case warm-run p50/p95 timings are included for transparency but are NOT real-time model, native CE, engineering simulation or end-to-end Lu latency; no power/energy data was measured.

## Portable verification

- New T4 P3 reference suites: **40/40 tests pass** (source/non-synthetic provenance restrictions, synthetic falsifications, nominal claim failure, wrong unit/dimension, unseen/duplicate IDs, partition leakage, source reuse, missing/unknown truth, p2/P3 evidence alignment, Wilson endpoints, protobuf roundtrip and loads-not-fit support).
- Combined P1 + P2 + P3: **110 passed**, 7 subtests; separate C15 T3/C07/C13/C14 regression sample: **241 passed, 1 Windows-only skipped**, 20 subtests. These are selected suites, **not** a full repository sweep.
- **78/78 Protobuf source/binding descriptor parity**, independently compiled by protoc, including P3 and 77 unchanged predecessor schemas. No new runtime third-party dependency; SciPy required only when P2 joint feasibility cases use it.
- ZIP preservation and archive integrity in separately generated archive verification JSON.

## Incomplete acceptance gates / no promotion

1. **Real externally held-out engineering measurements:** datasets with licenses, consent, instrument/calibration metadata, independent specimen IDs and protocols; P2 model source must not see holdout labels or measurement source. OPEN; no physical dataset bundled.
2. **Domain expert and independent numerical/physical reference:** compare analytic reference, CAD/FEA and measured specimens, including geometric stress concentrations, nonlinearity, cyclic fatigue, real temperature correlations, installation tolerance and multiple materials. OPEN.
3. **Calibration and statistical transport:** separate preregistered train/calibration/test custody, correlation/grouping/shift analysis, binomial assumptions and multiclass stratification. P2 intervals are worst-case claims, not predictive probability intervals; genuine predictive coverage calibration remains OPEN.
4. **Latency/resource/energy:** actual Lu host, representative Windows target and energy measurement, with model/Cognitum on/off and conventional solver baseline. OPEN; local audit timing is not a substitute.
5. **Runtime authority/Windows resilience:** C02 native supervised process, real host provenance, C15 T3 VM hard-off/rollback, user consent and physical controls remain OPEN/DEFERRED. Lu is unchanged.

The correct gate result is **PORTABLE_EVALUATION_INFRASTRUCTURE_PASS; EXTERNAL_PHYSICAL_P3_ACCEPTANCE_OPEN**.
