# Cognitum CH-C14-39 — Independent MPFR proof checking before attestation

**Date:** 2026-11-02 (America/Phoenix). **Disposition:** scoped Linux research engineering PASS; scientific/production NO-GO.

## Security boundary

CH38 allowed the math worker UID 1002 to fabricate a JSON success report that attestor UID 1003 would sign after checking metadata. CH39 makes attestation contingent on a *second* MPFR replay under checker UID 1004 with its own owner-only original proof material.

| Principal | UID | Authority |
|---|---:|---|
|Writer|1000|Case-ID-only request|
|Math worker|1002|Original CH23 224-bit MPFR replay; no signing keys or checker source|
|Independent checker|1004|Separate frozen-source copy, full 127-node certificate and six historical-frame replay; no signing keys|
|Attestor|1003|Requires checker UID + independent success; owns attestation key but no proof files|
|Final witness signer|65534|Owns final signing key, frozen policy and durable history|

The worker success message alone is never sufficient: checker response must bind case, random nonce, frozen policy, exact SHA-256 of worker attestation and newly independently computed attestation. Attestor signs only on equality; the signed ticket embeds the checker receipt and the final signer validates its schema and signature. CH39 signing domains differ from CH38.

## Frozen original CH23 regression

- **Original cases:** 15 / 15. No substitutions or new optimizers.
- **Independent checker+worker replays:** 30 mathematical verifier invocations.
- **Checkpoint nodes rechecked:** 3,810 (127 per case per independent invocation).
- **Historical frames rechecked:** 180 (six per case per invocation).
- **Source pins:** 15/15 original CH32 heads and CH33 compacted checkpoints matched.
- **Executed service source digests:** 6/6 matched the current CH39 source files byte-for-byte.
- **Signatures:** 15 attestor and 15 signer signatures independently audited.
- **Wall clock:** 1357.46 seconds at worker limit 4 and checker limit 4 (both expensive, independent MPFR runs).
- **Frozen original witness chain tip:** `112980038c992461c0eaf43c2d3f066191e4c7404b058ba434c1ba1352af68c5`.

## Live adversarial checks

- **24/24** CH39 protocol tests passed (source: `ch39_tests.log`), including forged archive/binding hash, altered bounds, replay, forged checker receipt, absent checker, invalid scope, independently signed legacy ticket refusal and old-domain signature rejection.
- **Forged real math UID 1002:** result **PASS**, fabricated original-case MPFR claim was refused; witness created = **False**; elapsed 182.68 seconds. This is a real UID-separated running service, not a mocked payload.
- **Offline checker UID 1004:** result **PASS**, worker claimed success but signed witness = **False**; elapsed 7.158 seconds.
- **Historical forged certificate with recomputed hashes:** CH33 original-data `test_forged_valid_hashes_cannot_replace_mathematical_proof` was rerun and passed (original case, not synthetic).

## Assurance limitations

1. **Independent execution, shared algorithms:** UID 1002 and UID 1004 use separately protected copies of the *same* historical MPFR verifier implementation; systematic mathematical code errors are still common-mode risks. Independent algorithm / implementation is not claimed.
2. **Attestor trusts checker UID:** checker receipt is protected by SO_PEERCRED and a signed attestor envelope, not a third public-key signature. Compromising checker/attestor or OS root remains outside this security boundary.
3. **No off-host trusted anchor:** public keys and latest tip must be independently pinned. A writable local ledger and all local pins can be rolled back if an attacker controls them.
4. **Not a scientific certificate:** original 0.05 global objective-gap requirement still unmet: **0/15** global-optimality claims. Results are verified-but-unresolved original CH23, not unrestricted-global proof.
5. **Not a power-loss/Windows/EDQUOT result:** earlier CH36 genuine ENOSPC and fsync injections are inherited evidence, not rerun here. Windows testing remains deferred.

## Next research gate

Develop or adapt an independently implemented proof verifier, preferably in a different language and arithmetic stack, and independently reproduce CH23 interval enclosures and branch-bound descent to reduce common-mode correctness risk. Defer promotion into production Cognitum C14/G25 and Lu.