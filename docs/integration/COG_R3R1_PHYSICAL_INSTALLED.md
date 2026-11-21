# Cognitum R3-R1 — Physical Installed Windows Admission

**OPEN: physical production installation and authenticated Core integration are unverified.**

## What already passed

The CI-only fixed numerical service on exact SHA f2258406f387282edec493ea1bb788957e51502e passed native Windows AppContainer/SCM Job execution, independent NumPy/SciPy numerical recomputation, separately provisioned CI-only CNG signed receipts, terminal/replay checks and original account/key cleanup:
- https://github.com/vjmichael/cognitum/actions/runs/44956081778
- https://github.com/vjmichael/cognitum/actions/runs/44956081760

The tested binary has test-only embedded HMAC intent and is **not** a genuine signed production supervisor. Passing hosted CI does not establish physical installed acceptance.

## Read-only physical preflight

The following scripts require **independently approved** release pins and do not mutate system state:
1. scripts/cog-r5-physical02-r2-signed-host-preflight.ps1 — existing Authenticode-pinned installed service, restricted service SID, process image and SYSTEM/session custody observation.
2. scripts/cog-r5-physical02-r3-r1-runtime-audit.ps1 — externally pinned production manifest and separately pinned provenance, every closed Python/NumPy/SciPy import hash, exact full file inventory, protected owner/NTFS ACL, no reparse, bounded file count and byte size. Empty legitimate Python modules are hash-checked.
3. scripts/cog-r5-physical02-r3-r1-installed-preflight.ps1 — requires both gates and emits **only** signed host plus runtime integrity observation, not full installed acceptance.

The production provenance schema is cognitum.ssm.r3r1.production_installer_runtime.v1, different from the CI fixture schema; **the CI runtime cannot be promoted by renaming its service**. All image, signer-certificate, manifest and provenance SHA-256 pins must come from an independent release authority, not from files that the installer self-declares.

The new hosted Windows preflight workflow uses only a **synthetic protected runtime** and verifies wrong pins, modified dependency bytes, unlisted files and unsigned/uninstalled host refusal. Even a passing result is not real production signing, installation or enrollment.

## Actual R3-R1 closeout requires

- Real production supervisor built without CI-only HMAC key and securely packaged by an independently approved Windows installer/publisher, pinned exact signed executable and provenance.
- An actual installed nonadministrator AppContainer numerical worker, no network capabilities, correct TokenUser/TokenIsAppContainer/TokenElevation and verified SCM-owned Job attachment **before** worker resume.
- Installed, separately provisioned nonexportable production CNG signer with independently verified terminal, cancellation and uncertain restart receipts; prove rollback/replay/tamper resistance.
- Authenticated Lu Core Health and per-operation PURE_COMPUTE authorization, original-operation reconciliation and revocation.
- Physical installed Windows restart/uninstall/reinstall/cancellation/cleanup/tamper evidence on one pinned release build and independent evidence audit.

**Never** claim PASS_INSTALLED, approve a release, or deliver/ACK original output based on this preflight alone. LocalSystem fallback, user-writable imports and test-only symmetric key authority remain prohibited.
