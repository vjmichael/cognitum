# Cognitum CH40-L — Mathematical gap reduction (2026-11-03)

Engineering result: **PASS_FROZEN_FRONTIER_AND_ONE_VERIFIED_INCUMBENT_IMPROVEMENT**. C14 scientific release: **NO_GO**.

This phase reused the CH40-J signed original research result and CH40-K frozen, pinned raw mathematical traces. For all fifteen cases, exact rational dyadic reconstruction of 127 inherited MPFR upper bounds and the 64 terminal caps established the original frozen frontier ceilings. The earlier independent CH40-E checks justify the selected cap mathematical provenance; CH40-L did not freshly re-run the full local MPFR formulas for every node.

For twelve cases, lower bounds were freshly reevaluated from the original feasible incumbent with rational interval arithmetic; for three cases, prior CH40-E independently checked, outward-floor-rounded lower bounds were reused with explicit provenance. Every case remains above the 0.05 tolerance, with 39–57 of 64 terminal boxes per case above its certified feasible lower + 0.05.

**Actual mathematical improvement:** on frozen original quasi_separated_n160_i00, a bounded L-BFGS-B heuristic proposed a new feasible incumbent. An independent rational/interval point-objective check certified the feasible lower increased by at least 0.8198555124381615394 and the finite-root upper-minus-lower gap decreased from 7.9823269813687096349 to **7.1624714689305480955**. The original 127-node upper caps were not modified. The comparison control zero_imbalanced_n80_i00 yielded no improvement.

Focused regression tests: 5/5 pass, including tampered-trace refusal and exact dyadic decoding. Source and results package (not committed to this repository): Cognitum_CH40L_Frozen_Frontier_Verified_Incumbent_2026-11-03.zip, SHA-256 7ea9819c5eecf1c31c28941494fd23d630f9d0ea14f9aebd527c23aedd603842.

**CH40-L.2 next:** source-trace and independently verify *new* child MPFR caps for selected highest-terminal-upper boxes, with certified parent inheritance, journaled tree append, equal-CPU control, and no alteration of the original signed evidence. No new child caps have yet been certified. Unrestricted global optimality, the 0.05 tolerance, and the scientific C14 release remain **NO_GO**.
