# Cognitum C15 T4 P5–P7 — signed evidence intake, claimed time order and dual review

**Date:** 2026-10-29 (America/Phoenix)  
**Scope:** additive, Protobuf-native, offline/research-only capability reference.  
**Status:** **P5, P6 and P7 portable synthetic gates PASSED**. Real-source authentication, independent preregistration, authentic expert review, licensed measurements, and physical safety all **OPEN**. Lu unchanged.

## P5 — content-bound publisher signature verification

Source: `cognitum/spatial_functional_material_p5_p7.py`, `evaluate_p5()`. New typed messages in `proto/cognitum/spatial/v1/functional_material_p5_p7.proto` and generated binding. Requires P4 evidence gate to succeed, then one signed evidence receipt per distinct case. Ed25519 signatures cover exact canonical JSON bytes prefixed by domain `C15-T4-P5-SOURCE-V1\0`. Required fields: schema version, case, study, frozen plan SHA-256, observation payload SHA-256, exact source ID, declared license, declared calibration receipt, and publisher-asserted observation timestamp. The valid signer must have a `publisher` role in an injected host policy. Enforces limits, rejects duplicate or missing signatures, mismatched study, source, hashes, license, calibration, noncanonical/ambiguous JSON, unknown fields, role confusion, signatures from revoked/untrusted/out-of-validity keys, and direct authority claims.

The reported `trusted_policy_signatures_verified` proves signatures under the **supplied policy**, NOT that the policy's real-world identity assertions or source licenses are independently valid. This reference implementation does not provision publisher keys, validate PKI/certificates, fetch data, or store revocation/rotation history.

## P6 — signed prespecified plan and timestamp ordering

`evaluate_p6()` requires all P5 checks and a second, valid Ed25519 plan-lock statement (`C15-T4-P6-LOCK-V1\0`), signed by an attestor role distinct by both key ID **and public-key bytes** from any publisher. It binds the same study and frozen plan hash and requires its claimed `locked_at_ms` to precede each source's signed `observed_at_ms`. Revoked/unknown/out-of-validity keys, same-key role aliases, different plan, missing signature, equal-time and late-lock conditions are rejected.

**Time caveat:** these are *signer-asserted dates in offline signed statements*. Cryptographic validity does not prove a statement was signed at the claimed date; a signer may backdate it. `signed_timeline_consistent=true` is deliberately **not** `independent_preregistration_verified=true`. Real preregistration needs externally anchored, independent, verifiable issuance-time evidence and a controlled key life cycle.

## P7 — duplicate-aware dual reviewer adjudication

`evaluate_p7()` requires valid P5 and P6 evidence, **two distinct** trusted reviewer signing keys for each reference case, no duplicate public-key aliases, roles isolated from the source and attestor, declared blinded-review protocol, a reported review timestamp no earlier than the observation or lock, signed binding to the same reference bytes, agreement between the two reviewer labels, and agreement with the observation class used in P4/P3 evaluation. A conflict fails closed with `REVIEWER_DISAGREEMENT_REQUIRES_ADJUDICATION`; either duplicate reviewer or shared key aliases also fail.

**Expert caveat:** signed claims of blinding are not observed blinding; publisher identity is not verified; no real professional accreditation or domain adjudication occurred; multiple fake keys do not establish separate human experts. `actual_blinding_verified=false` and `qualified_expert_status_verified=false` even on a full portable pass. Similarly, reviewer consensus is not material or physical safety truth.

## Synthetic 80-case replay

One freshly generated, memory-only test-key policy signed all 80 P4 synthetic observations, an illustrative plan lock, and 160 reviewer statements. No private keys are archived. The P3 test retained its 35 decided calibration and 35 decided holdout cases, with 5 and 15 deliberate disagreement cases, respectively. Negative controls returned `INVALID_ED25519_SIGNATURE` for signature forgery and `REVIEWER_DISAGREEMENT_REQUIRES_ADJUDICATION` for contradictory signed review. These are internally generated laboratory-**free** fixtures, not a substitute for a real engineering study.

## Verification summary

- **42/42** focused P5–P7 tests passed (including public-key aliases and domain-separated signature misuse).
- **183 selected T4 tests passed**, 7 subtests.
- **914 selected T4/T3/C07/C13/C14 tests passed**, 10 skipped, 87 subtests; 2 dependency-related warnings. Not the entire repository test suite. Skips are not claimed as passes.
- **80/80** checked-in Protobuf bindings matched descriptors freshly compiled from their `.proto` sources with protoc 3.13.0; the 4 `proto3 optional` schemas needed `--experimental_allow_proto3_optional`.
- Signing verifier uses `cryptography` Ed25519. A compatible package must be available on the target environment; Windows-native testing for P5–P7 has **not** been run.

## Trust boundary & acceptance rubric

| Gate | Portable result | Independent external acceptance |
|---|---|---|
| P5 signed source/data identity | PASS, test keys and supplied trust policy | OPEN: validated publisher identity, licensing, instrument, custody and durable revocation |
| P6 signed pre-observation plan | PASS, synthetic claimed timestamp order | OPEN: external timestamp evidence, time authority, immutable preregistration |
| P7 dual signed reviewer consensus | PASS, test signatures and asserted blind protocol | OPEN: actual independent reviewers, qualification, blinding, real disagreement adjudication |
| P4 actual reference data bytes | PASS, test inputs | OPEN: licensed real data and engineering-grade reference truth |
| T3 experimental Windows VM recovery | PASS per separate VM evidence archive | NOT production power-loss/TPM certification |
| Lu native E2E, physical controls, Cognitum-on/off LLM benchmarks | UNTOUCHED | DEFERRED |

No Lu source, tool permissions, user assets, network resources or hardware were modified. Signatures are validated under **host-supplied** trust policy; passing this gate cannot grant Cognitum any tool execution authority. The fixture keys must never be promoted to trusted production identities.

## Next gates

1. Collect a **licensed real engineering dataset** with raw source files, specimen grouping, instrument calibration and data dictionary; obtain permission to process and publish reproducibility digests.
2. Establish **external key trust and revocation** (publisher, registrar/time notary, reviewers) and independent timestamp proof; no model may register its own trust roots.
3. Run actual independent **domain-expert reviews**, split lock before observation, and stratified error analysis against real data; investigate persistent disagreements before any claim of model correctness.
4. Run Windows-native P5–P7 verification in isolated worker and do the deferred matched Lu+Cognitum comparisons only after the authorization boundary is ready.
