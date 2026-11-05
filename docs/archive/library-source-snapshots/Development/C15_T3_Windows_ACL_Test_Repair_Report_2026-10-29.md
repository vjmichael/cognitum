# C15 T3 — Windows native ACL negative-test assertion repair

## Actual first native run (2026-10-29)

- Windows AMD64 / NTFS / CPython 3.14.6 confirmed by uploaded evidence.
- Broken LM Studio registration bypassed; installation of pinned pytest and protobuf completed.
- Windows test suite: **2 passed, 1 failed, 3 skipped**. The runner stopped before full restart/DPAPI process acceptance.
- Test injected a BUILTIN\Users read/execute ACE with no `(OI)(CI)` inheritance flags.
- Auditor correctly rejected the modified ACL with `UNEXPECTED_OR_INHERITED_ACE`.
- Test incorrectly required `UNAUTHORIZED_OR_DUPLICATE_ACE`, which applies when a syntactically valid ACE contains an unauthorized SID.

## Repair

1. Keep **all production ACL enforcement code byte-for-byte identical** to the prior package.
2. Update the existing no-inheritance negative test to require a failure and accept only the two specific security-rejection reasons.
3. Add an independently exercised native-only negative test injecting BUILTIN\Users `(OI)(CI)(RX)` so its flags match the expected directory format. Require the `UNAUTHORIZED_OR_DUPLICATE_ACE` rejection.
4. Retain original checkpoint, portable evidence, and all existing tests. Regenerate source integrity manifest and update launcher SHA-256 pin.

## Validation boundaries

- Source/packaging and portable tests can run on Linux. Windows-specific ACL tests **must run on Windows** and are expected to skip on Linux.
- Previous native evidence verifies rejection of an unauthorized ACL; it does **not** close the full native gate.
- No changes to Lu, GitHub, original Cognitum datasets, R1 baseline, Windows AppData, or preceding checkpoints.
- Power-loss, independently held anti-rollback authority, and Lu host integration remain deferred.

## Manifest

Old embedded SHA-256: `d87cfe953332303333f0d396a7cb201cd7f7cf96717b9f78a7d35bf2470caf7e`

New embedded SHA-256: `8cf1d11d6e0a6d305da62d6e195eac6eeaca6336a070708e2dce211c94196275`

## Clean package verification (Linux environment)

- 19 tests passed; 5 Windows-only tests skipped (including new SID-policy test).
- 75/75 independent Protobuf schema-parity checks passed.
- All 840 tracked source-file SHA-256 hashes verified within the new embedded ZIP.
- Only `tests/test_c15_t3_windows_acl_gate.py` differs among tracked source files. The production Windows ACL implementation and other source remain unmodified.
- Outer kit ZIP passed CRC verification, embedded ZIP passed CRC verification, and launcher SHA-256 pin equals `KIT_MANIFEST.json` and the new embedded ZIP hash.
- Native Windows acceptance **not rerun yet** for this fixed test.

**Next step:** Extract the newly named ACL-fix ZIP in a fresh Windows directory, run `Run-Cognitum-Windows-Gate.cmd`, and upload its generated evidence ZIP.