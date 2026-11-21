# Cognitum R3-R1 — Signed production carrier source

Status: source-only candidate; not an approved signed release.

The separate no-worker production service must be built at an exact source SHA.
The Windows NSIS carrier copies that executable and a frozen Python/NumPy/SciPy
runtime into the fixed x64 Program Files Cognitum SSM directory, and refuses
existing or interrupted installation trees. It never registers SCM, launches
a worker, mints a signer, creates a Core grant or releases output.

The release builder requires an existing externally provisioned code-signing
certificate with its private key, Windows SignTool and NSIS. It signs the
production PE and then the outer NSIS installer, checking both certificates
and original runtime pins. The build receipt explicitly is NOT independent
release approval and NOT physical installed acceptance. A separate release
authority must approve the completed hashes before physical SCM enrollment.

No signing certificate, approved publisher, genuine signed installer, original
production CNG credential or physical Windows acceptance is presently proven.
No transactional updater or uninstaller is claimed; those remain open.
The legacy native Windows SCM fixture must never be renamed/signed as production.

## Protected installer source qualification

The NSIS carrier pins its install directory under 64-bit Program Files, rejects an existing directory, and seals all installed file ownership/ACLs before reporting success. A separate unsigned CI test now builds and actually installs the NSIS carrier with CI-only synthetic runtime provenance, verifies the sealed installed bytes and runs the real hosted Windows SCM service from that installed image. Reinstallation must refuse without changing existing bytes, and teardown is limited to the synthetic CI tree. This is NOT a production publisher-signature test, NOT an independently signed package, and NOT physical Windows installed acceptance.
