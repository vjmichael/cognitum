# Cognitum C15 T4 P8–P10 — host trust policy, time-anchor contract, data intake

**Date:** 2026-10-29 (America/Phoenix)  
**Scope:** additive, Protobuf-native, offline-only reference; no Lu modification.  
**Result:** portable **synthetic protocol gates pass**; real issuer, time authority, human review, real licensed data and scientific validity **remain OPEN**.

## P8 — signed host policy and rollback-resistant updates (limited)

Source: `cognitum/spatial_functional_material_p8_p10.py` (`policy_snapshot`, `advance_policy_highwater`), typed envelope/result in `proto/cognitum/spatial/v1/functional_material_p8_p10.proto`.

- Host pins the **root Ed25519 public key** by an out-of-band, non-model mechanism. The model never enrolls/rotates a root or grants permissions.
- A domain-separated root signature covers the exact canonical policy JSON (`C15-T4-P8-HOST-POLICY-V1\0`). Strictly parses a bounded policy ID, generation, previous-policy SHA-256 link and keys with roles (`publisher`, `plan_attestor`, `reviewer`, `time_notary`), valid intervals, and revoked flags.
- Denies root forgery, key-ID aliases, public-key reuse across roles and unpinned root IDs. Monotonic per-policy sequence is enforced in a **host-operated SQLite transaction** (`BEGIN IMMEDIATE`), with equal-generation equivocation rejection, linked next-generation acceptance, and rollback/jump rejection. Previous signers must remain in the chain; revoked signers cannot be silently reactivated and signing identity/role cannot be rewritten. A rotated key needs a **new ID**; retain the old key as a signed tombstone.
- `HostHighwater(generation, policy_sha256)` is an optional **separately supplied host checkpoint**; comparing it to the current DB detects divergence. The SQLite DB itself is **not a protected monotonic counter**. If the attacker can restore the database **and** host checkpoint, this mechanism cannot establish anti-rollback. Production needs hardware/remote protected state and root-key governance.
- `persistent_highwater_verified=true` only reports that the externally supplied host checkpoint matched the DB at update time; it does **not** certify hardware security or signer identity. `independent_identity_verified=false` always.

## P9 — separated signed notary receipt (protocol-readiness only)

`evaluate_p9` re-evaluates P4–P7 under the **same P8 snapshot**. A dedicated `time_notary` role signs the deterministic serialized P6 request digest (including the study, plan lock and P5 signed sources), an asserted issuance time and a claimed notary sequence using `C15-T4-P9-NOTARY-V1\0`. It requires a separate public key (not publisher, plan-attestor or reviewer), claimed issuance no earlier than lock and strictly before all claimed observations, and rejects corrupted signature/binding and late receipt.

**This does not verify RFC 3161, qualified TSA, a public transparency log, a timestamp counter independently held by the notary, or genuine preregistration.** A notary can backdate its own signed time and claim any `notary_sequence`. Therefore `externally_issued_timestamp_verified=false` and `independent_preregistration_verified=false` even on passing synthetic tests. Independent time acceptance remains a separate real-world task.

## P10 — bounded, structurally validated external CSV staging

`evaluate_p10` accepts raw CSV bytes, canonical JSON manifest and raw calibration-document blobs through a typed Protobuf request. It verifies SHA-256 equality of **actual** CSV and calibration bytes, bounds count and size, strictly constrains columns and units, rejects duplicate specimen IDs and group partition leakage, rejects nonfinite measurements, and requires an **injected host allowlist** for the declared license ID. It performs **no filesystem read or network access**.

**Required CSV columns in order**: `specimen_id,group_id,partition,observed_class,measured_clearance_m,calibration_id`. Partition values are `calibration` or `holdout`; labels are `satisfies`, `violates`, `undetermined`; numeric measurements are finite metres (`m`). Host-supplied license IDs only attest an operational allowlist, not legal rights. Calibration document hashes only attest file bytes, not that the equipment was ever calibrated. `licensed_real_world_data_verified=false`, `calibration_independently_verified=false` and `physical_safety_verified=false` are always retained. This adapter stages a future dataset; it does not yet map a true engineering dataset to P4 reference specimens or validate material physics.

### External dataset handoff requirements (not satisfied)

1. A permissibly acquired, named reference dataset with explicit reuse terms and permission to redistribute hashes/results; preferably an instrumented engineering fit or material test covering independent specimens and repeat runs.
2. Raw files, original documentation, units, instrument serial and calibration certificates, specimen grouping, measurement uncertainty, acquisition method and dataset version/digest.
3. Study plan locked **before** testing or chosen holdout release, with an independently verifiable issued timestamp, split isolation and conflict/disagreement reporting. No model-selected holdout after scores are known.
4. Two genuinely separate, qualified human expert reviewers (where warranted) with review blinding evidenced by process logs, not merely two generated signing keys.
5. Written sign-off of the source license, calibration and limitations by responsible humans. None is automated by this reference code.

## Tests and gates

- 38 focused P8–P10 tests include root/signature mutation, generation rollback, same-generation equivocation, host DB deletion, key-tombstone removal, revocation resurrection, notary timing/binding forgery, invalid JSON/CSV, license rejection, calibration-file tampering and partition leakage.
- Selected cross-family regression: 1,193 passed, 39 skipped, 117 subtests passed; 5 warnings. Not the entire repository suite.
- 81/81 checked-in Protobuf descriptors match independent `protoc 3.13.0` compiled sources.
- 80-case P8→P9 synthetic replay preserves P3 `5/35` calibration and `15/35` holdout disagreement counts, verifies 80 source signatures and 160 reviewer signatures. Separate P10 CSV fixture has **2 synthetic rows only**.
- Original P5–P7 logic and P4 source behavior remain unchanged. No real publisher identity, real measurement, license verification, actual reviewer independence, protected root custody, genuine timestamp authority, Windows-native execution, Lu integration, or safety certification is claimed.

## Host security warning

The witness SQLite file is **for a trusted host to operate**, not a Lu/Cognitum model tool. Host root keys and external checkpoint must be provisioned and stored through mechanisms **outside** Cognitum's request envelope. No root enrollment, external key rotation, real TSA, TPM or hardware-monotonic storage is included. Model-generated policy requests never authorize an update. User must approve the exact context before any future integration with a real host.

## Developer commands

```bash
python -m pytest -q tests/test_c15_t4_p8_p10_external_readiness.py
python -m evals.c15_t4_p8_p10_synthetic_readiness
```

A disposable host-witness test can be run with an ephemeral SQLite location; never reuse T3 VM rollback databases for this work.
