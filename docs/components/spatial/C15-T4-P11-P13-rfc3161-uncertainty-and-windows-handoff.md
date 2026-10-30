# Cognitum C15 — T4 P11/P12/P13 engineering handoff

**Research checkpoint:** October 29, 2026 (America/Phoenix).  
**Source:** `Cognitum_C15_T4_P8_P10_Host_Policy_Notary_Data_Readiness_2026-10-29.zip`.  
**Boundary:** Offline experimental Python/Protobuf only; **no Lu modifications or granted authority**.

## P11 — Host-pinned RFC 3161 timestamp receipt verifier (PORTABLE MECHANISM PASS)

- New typed `T4P11Rfc3161Request/Result` contains the validated P6 signed plan-lock request and an original DER timestamp query and response. Separate host arguments supply the pinned TSA certificate SHA-256, trusted CA PEM, allowed policy OIDs, and *host-selected* OpenSSL executable path. These are not model-enrolled roots.
- Replays P6 source/lock signature checks under the same externally supplied P8 policy snapshot, then SHA-256 hashes the **deterministically serialized signed P6 plan-lock record**. DER parsing checks request hash, nonzero nonce, `certReq`, successful response, matching nonce, message imprint and policy OID. It compares CMS signer issuer/serial and embedded certificate DER with the host-pinned signing certificate and requires a critical `id-kp-timeStamping`-only EKU. `openssl ts -verify` performs signature and trust-chain checking without network.
- Returns the token's signed generation time and an independent *claimed chronology* boolean comparing that generation time against signer-asserted observation times. The boolean does NOT establish that any observation occurred when claimed. A locally signed, host-trusted synthetic TSA with artificially future-dated observations exercises the positive chronology branch, while a genuinely late local receipt fails the chronology branch.
- **Still OPEN:** genuine independent TSA identity and root enrollment, CRL/OCSP revocation checks, host custody/freshness of the nonce challenge, external preregistration certificate and records, unmanipulated independent physical observations. Pinning a locally generated certificate is not independent TSA authentication. See [RFC 3161](https://www.rfc-editor.org/rfc/rfc3161.html), sections 2.1–2.4, for the nonce, imprint, TSA signing identity and verification requirements.

## P12 — Measurement uncertainty and holdout-label consistency (PORTABLE MECHANISM PASS)

- New typed `T4P12UncertaintyRequest/Result` accepts the P10 validated CSV and one uncertainty record per specimen. Each record binds an instrument ID, asserted calibration/observation timestamps, a bounded standard uncertainty in metres and a coverage factor in `[1,3]`.
- For this deliberately narrow research reference, **zero-metres clearance** is the prespecified decision boundary: lower bound strictly above zero means `satisfies`, upper bound strictly below zero means `violates`, and an interval crossing/touching zero means `undetermined`. All caller-provided labels must match. Decimal arithmetic prevents floating-point boundary surprises. At least one calibration and one holdout specimen must exist; P10's source/partition/hash/license-ID checks are re-executed.
- **Still OPEN:** actual reference specimens, calibrated real instrument uncertainty, externally authenticated calibration records, verified data reuse permission, nonlinear material-model calibration, holdout lock provenance, independent reviewer qualification and physical safety.

## P13 — Windows x86-64 reproducible smoke runner (PREPARED, NATIVE TEST OPEN)

- A disposable-VM operator may double-click `Run-Cognitum-T4-P13-Windows.cmd` in the extracted ZIP. It requires a preinstalled Python interpreter, OpenSSL executable and the pinned direct Python packages. It performs no installation, registry changes, VM reboot, host witness mutation, network calls or Lu operations.
- `tools/run_c15_t4_p13_windows_gate.py` verifies platform is Windows x86-64; tests and direct package versions are present; and the output directory is new/empty. It executes the P11–P12, P8–P10, P5–P7 and P4 suites in separate bounded child processes; writes stdout/stderr, SHA-256 hashes, environment fingerprint and `gate-result.json`. Existing evidence is never overwritten.
- **Still OPEN:** a *real Windows VM run* with actual `gate-result.json` and independent host-side review, genuine OS-level process confinement (Job Objects/AppContainer), native Lu worker/Protobuf integration, and a reviewed transitive Windows dependency wheel/hash lock. Running unit suites in subprocesses does **not** establish an isolated worker sandbox.

### Windows operator prerequisites (manual, not performed by this checkpoint)

- Windows 11 x86-64 disposable VM; Python 3.11 or 3.13 (the historical CI-supported versions); installed `protobuf==6.33.6`, `cryptography==46.0.4`, `asn1crypto==1.5.1`, `pytest==9.0.2`; OpenSSL 3.x on `PATH`; **verified separately** by the operator. The dependency list includes only direct requirements; obtain matching Windows wheels and transitive dependencies through an approved offline wheelhouse if the VM cannot install from a package index.
- Extract the entire ZIP without stripping directory structure, then run `Run-Cognitum-T4-P13-Windows.cmd` as a normal user. No VM power-off or rollback simulation is needed. Upload the generated `Cognitum_T4_P13_Windows_Evidence/gate-result.json` and suite logs for review. If it reports `P13_NOT_VERIFIED`, no Windows gate can be claimed.
- Keep the previous T3 `highwater.sqlite` and `powercut-highwater.sqlite` entirely separate and untouched.

## Reproduction and claims ledger

- `python -m pytest -q tests/test_c15_t4_p11_p12_boundary.py tests/test_c15_t4_p13_windows_runner_contract.py`: **24 passed** in available Linux environment (ephemeral private-key fixtures only).
- `python -m pytest -q tests/test_c15_t4* tests/test_c14_p4e_g8_uncertainty.py tests/test_c14_p4e_g9_protobuf.py tests/test_c13_p4_conjugate.py tests/test_c07_p7_longform.py tests/test_c15_t3_p2z_host_recovery_readiness.py`: **353 passed, 1 skipped, 17 subtests passed**. This is a selected subset, not the whole repository.
- Independently compiled with `protoc 3.13.0 --experimental_allow_proto3_optional`: **82/82 source/binding descriptors matched** after adding one `.proto` file.
- A larger all-C15/C14/C13/C07 selected regression attempt exceeded the execution limit after 75% progress, with no final verdict. It has not been counted as a pass; the smaller completed selection is reported above.
- **No actual external timestamp issued, external calibration verified, Windows-native execution, production host root custody, trusted expert review or physical safety attested.**
