# Cognitum CH40-C — Engineering Acceptance Report

Date: 2026-11-03

## Engineering question

Can the original CH29 coupled/direct branch-and-bound certificate's bound values and rule choices be independently certified by CH40's separate Decimal implementation and admitted safely into CH39 attestation?

## Answer

**Partial.** The exact partition geometry, all original parent-bound inheritance display identities and independently recomputed direct/coupled conservative upper bounds can be validated. The original format omits full optimized local proof witnesses and has no accepted Newton actions; it does **not** support automatic independent mathematical certification of all producer cap numbers or their incorporation as global proof statements.

A fail-closed, domain-separated, challenge-bound Ed25519 research-only receipt protocol has been implemented and adversarially tested. No live Linux signer or attestor has been modified or exercised with this adapter.

## Source and proof scope

- Original frozen CH39 ZIP SHA256: `9e713b102982ea09fecbcfbd27bccf55d56808188bfc3e5be1ba76922000ae6b`.
- 15 original CH23 data cases, each 127 CH29 nodes, 64 leaves and 224-bit historical MPFR certificates.
- CH40-C independent recomputation: CPython Decimal/Fraction implementation already tested in CH40-A/B. The 127 producer nodes may use `direct`, `coupled_logdet_dual`, or a `coupled` selection falling back to `direct`.
- Source display cap numerical checks are **independent sufficient conditions**. A refusal means that this checker does not have sufficient evidence, not that original math has been disproven.

## Attestation design and exclusions

- Research ticket is signed with a trusted-key Ed25519 identity, binds the exact externally pinned source archive and per-case certificate hash, nonce, independent checker result, scientific `NO_GO` and 127-node scope.
- Fake keys, altered source IDs, nonce replay, unauthorized promotion, forged Newton and tailored field mutations must be rejected.
- Prototype verifies checker-signed digest and policy; it deliberately does not give the attestor the sealed math source. This remains a **mock policy demonstration**, not five-UID CH39 live service integration or independently operated witness.
- No unbounded global optimum proof or new finite-box 0.05 proof is claimed; release status `NO_GO`.

## Required follow-up

CH40-D should enrich the producer proof format to include independently checkable local bound witnesses. Only after independent rule-level validation and live cross-account acceptance tests should the new receipt type be admitted to a CH39-like signer. Scientific success remains a separate mathematical gate.