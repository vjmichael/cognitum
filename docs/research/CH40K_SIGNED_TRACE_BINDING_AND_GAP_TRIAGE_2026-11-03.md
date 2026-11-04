# CH40-K — signed trace binding and numerical gap triage (2026-11-03)

**Acceptance: PASS_SIGNED_TRACE_BINDING_ONLY (15/15). Scientific release: NO_GO.**

Reused the actual CH40-J 15-record signed public evidence and unchanged original 15 raw CH23 MPFR producer traces. CH40-K independent read-only auditor rechecked the pinned five-UID public chain and signed research receipts, then compared each receipt's raw producer trace SHA-256 and canonical certificate SHA-256 with frozen code pins and original case identity. All 15 agreed.

3/3 tests passed: original evidence acceptance; single trailing byte in an original raw trace refused; mutated signed record refused.

This is **not independent recomputation of interval arithmetic**; it verifies cryptographic binding between signed receipts and original mathematical artifacts. Observed key fingerprints/terminal tip remain CH40-J self-observed trust anchors, not independently authenticated off-host.

The original **producer-displayed** gap (not an independently recomputed outward-certified gap) ranges **1.0670999335484361–7.982326981368711** across the 15 cases against the frozen **0.05** tolerance. All 15 original certificates remain UNRESOLVED_REFUSE_CERTIFICATION. Worst displayed gap: quasi_separated_n160_i00 (7.982326981368711). Smallest: zero_imbalanced_n80_i00 (1.0670999335484361). No unrestricted global-optimality conclusion is licensed.

The source and adversarial tests are available as a separate conversation artifact: Cognitum_CH40K_Source_Gap_Triage_2026-11-03.zip (SHA-256 377cdf1b703ac29d031ddf31ee1162effb3b8c27e6811ffb6f8e1279aa010bd1). The ZIP reuses prior CH40-J frozen trace/evidence artifacts rather than duplicating approximately 800 MB of expanded traces; this GitHub commit records the result, not executable sources.

Next CH40-L: independently recompute the outward-certified finite-root upper-minus-lower gap from the 15 original proof trees, profile dominating leaves, and test proof-tree continuation, new incumbents and tighter local bounds without changing historical signatures. Production promotion is forbidden until the stronger mathematics is established.
