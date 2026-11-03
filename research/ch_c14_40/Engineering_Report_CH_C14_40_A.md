# Cognitum CH40-A — Independent Math Checker Engineering Report

Date: 2026-11-03. Research only; Windows bench continues independently.

## Verified Linux-hosted new-implementation acceptance

- Frozen original CH39 archive SHA256: `9e713b102982ea09fecbcfbd27bccf55d56808188bfc3e5be1ba76922000ae6b`.
- Code fingerprint: `9eb0d61fef28647e264bd03bcd4b95b11406cb456f3be369cf5df15de8cac70f`.
- Original CH23 case count: **15 of 15 PASS independent replay, all unresolved**.
- Exact rational partition verification: **1905** nodes, **960** leaf enclosures.
- Independent gap upper bounds from 4.6895 to 21.9307. The original proof tolerance 0.05 is *not* reached by this separate checker.
- Independent computation engine: `decimal`-only directed 85-digit interval arithmetic, monotone binomial likelihood, Hadamard upper Fisher determinant, positive reference-minor and direct 3x3 lower bound, exact `fractions.Fraction` geometry and SPD.
- Adversarial correctness tests: 19 PASS.

## Honest CH40-A certification boundary

These are new independently **conservative** mathematical bounds, not byte-for-byte reproduction of the inherited optimized CH29/39 local bounds. Original false `CERTIFIED_BOUNDED_GAP` status is rejected. Source certificate upper *display* numbers are ignored as mathematical authorities; specialized coupled/curvature bounds and validated Newton domain reductions need subsequent independent implementation before this can be promoted to a production/CH39 signer acceptance gate.

**Scientific: 0/15 global optima, NO_GO.** Finite-box unresolved is not a global theorem on R^3. No Cognitum production algorithm, CH39 witness, Windows test kit, or Lu source changed.
