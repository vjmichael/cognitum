# CH40-L.4 — coupled likelihood–information bounds and deeper continuation

Date 2026-11-03. **Partial engineering gate; scientific release NO_GO.**

Implemented the Fenchel/log-det dual upper-bound construction against original frozen CH23 Firth objective. For each model row, a native libmpfr 256-bit producer supplies a concave tangent in probability space. Exact-rational derivative-sign bisection selects near-stationary tangent supports. A separate rational/libmpdec interval implementation with conservative termwise upward rounding independently checks the child upper cap. The selected bound is min(verified direct, verified coupled) with mandatory inherited-parent min. The auditor separately reconstructs original frozen frontier, exact child partitions, digest chain and bounds; it never imports the native producer. Recovered journals continue to rely on CH40-L.3 fsync/reconciliation.

**Observed results are from four complete 3-split paired original-dataset comparisons, not all 15:** 
- one_event_n160_i00: selective upper reduction 0.02996096382544744; breadth-first direct 0.
- one_event_n80_i00: selective reduction 0; breadth-first direct 0.
- quasi_separated_n160_i00: selective reduction 0.10787709657364597; breadth-first direct 0.
- quasi_separated_n80_i00: selective reduction 0.05786853546329429; breadth-first direct 0.
- rare_1pct_n160_i00: selective 3-split journal independently audited, 0 frontier reduction; its direct-control three-split run remains incomplete. One child on the rare-event case used a verified coupled bound.

Five focused tests PASS: original three-split read-only audit, altered-bound tampering refusal, pending-intent refusal, resume idempotence, parent-bound conservatism.

**Caveats:** The selective arm evaluates both direct/coupled while breadth-first evaluates direct only, so this experiment confounds strategy and bound method; CPU time was not normalized. In the four completed paired cases, selected bounds were direct, so measured frontier gains are primarily from selective tree traversal, not yet evidence that coupled bounds reduce the global ceiling. The full 15-case 3-split comparison did not complete due to computational execution limits. Original CH40-J signatures remain unmodified, finite-root 0.05 closure remains unresolved, and scientific release stays NO_GO.

Conversation artifact: Cognitum_CH40L4_Coupled_Deep_Continuation_Partial_2026-11-03.zip (SHA-256 118fc82d688b015c3ecf24c3376a64afde61e96ce27a5e97beae9d28fcb2feb9). This GitHub commit is documentation only; all executable source and journals are in the artifact.

Next: complete the remaining 11 three-split paired cases from the existing replay journals; compare direct-only and coupled-only on **the same selected leaves** to isolate coupling benefit; then run CPU-matched deeper allocations, tune dual matrices for tighter caps with separately certified dual SPD proofs, and independently verify full per-operation MPFR transcript witnesses.
