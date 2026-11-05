# Cognitum CH-C14-29 — Verified inherited upper bounds and paired fixed-node/equal-CPU benchmarks

**Date:** November 2, 2026 (America/Phoenix). **Scope:** Original CH23 research cases only. **Scientific release: NO-GO.**

## Mathematical safety

For nested coefficient boxes \(B_c\subseteq B_p\), the true objective maximum over the child cannot exceed the maximum over its parent. CH29 therefore computes \(U_c=\min(U_p,U_{c,local})\) with 160-bit directed-rounding MPFR. The bound may be inherited repeatedly through arbitrary ancestor depth.

Independent verification at 224 bits rebuilds the exact partition and any interior interval-Newton contractions, recomputes *every* local node bound and recursively reconstructs the ancestor minimum, and rejects any false finite-box certification. Neither displayed floats nor cached endpoints carry proof authority.

The finite coefficient domain is `[-10,1] × [-5,5] × [-5,5]`; `epsilon=0.05`. The method does **not** establish unrestricted global maximization, uniqueness, causal identification, or interval calibration.

## Frozen cohort and measurement protocols

All 15 original CH23 inputs are hash-bound in the preregistered `frozen_protocol.json` (12 original bounding cases and three original zero-event ambiguities). The paired tests used 63 and 127 nodes per case. Equal-CPU controls used the independently recorded CH28 *solve process CPU* per case as a hard target checked between node expansions; a final expansion can overshoot. They allowed up to 127/255 nodes to avoid conflating node and CPU budgets. Verification CPU was measured independently, not added to the solve cap.

Results from different search policies cannot be compared as if their nodes followed the same partitions. CPU comparisons use historical CH28 single-process measurements from the same environment; machine load and finite node-step granularity remain limitations.

## Aggregate results

| Mode | Reference CH28 nodes | CH28 mean gap | CH29 mean gap | Better / tied / worse | CH29 solve CPU (s) | CH28 solve CPU (s) | 224-bit replay CPU (s) | Within ±10% CPU target |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| fixed | 63 | 4.8259 | **4.2642** | 10/4/1 | 887.1660 | 825.4570 | 325.0200 | 13/15 |
| fixed | 127 | 3.9428 | **3.4087** | 8/5/2 | 1277.7810 | 1193.8690 | 612.8530 | 8/15 |
| equal_cpu | 63 | 4.8259 | **4.3556** | 11/0/4 | 833.0580 | 825.4570 | 273.4500 | 15/15 |
| equal_cpu | 127 | 3.9428 | **3.2767** | 12/2/1 | 1200.1410 | 1193.8690 | 560.0860 | 15/15 |

## Original-case paired comparisons

| CH23 input | CH28/63 | CH29/63 | CH28/127 | CH29/127 | CH29 CPU/63 | CH29 CPU/127 |
|---|---:|---:|---:|---:|---:|---:|
| `one_event_n160_i00` | 5.0997 | **3.7825** | 3.9635 | **3.3044** | 3.7841 | 3.1398 |
| `one_event_n80_i00` | 3.8353 | **4.0461** | 3.0612 | **3.1630** | 4.0645 | 3.0612 |
| `quasi_separated_n160_i00` | 11.7434 | **10.0484** | 7.9894 | **7.9823** | 11.2397 | 7.4992 |
| `quasi_separated_n80_i00` | 7.5333 | **7.5333** | 5.3476 | **5.3476** | 7.4894 | 4.5586 |
| `rare_1pct_n160_i00` | 6.5957 | **4.9671** | 4.0285 | **4.0808** | 4.9671 | 3.9619 |
| `rare_1pct_n160_i13` | 3.5078 | **2.5417** | 4.9708 | **2.2759** | 2.5417 | 2.1614 |
| `rare_1pct_n80_i00` | 4.8235 | **4.4352** | 3.6592 | **3.4411** | 4.2977 | 3.3247 |
| `rare_5pct_n160_i00` | 5.6550 | **5.6550** | 4.1920 | **4.1920** | 5.7389 | 4.1920 |
| `rare_5pct_n80_i00` | 5.1174 | **5.1174** | 4.0781 | **4.0781** | 4.9665 | 4.0996 |
| `zero_balanced_n160_i00` | 3.6486 | **2.7793** | 4.7361 | **2.5830** | 2.8003 | 2.5830 |
| `zero_balanced_n80_i00` | 2.1301 | **1.9106** | 2.0232 | **1.7595** | 1.8301 | 1.7595 |
| `zero_imbalanced_n160_i00` | 4.1540 | **3.8605** | 2.8250 | **2.8250** | 3.9556 | 2.7792 |
| `zero_imbalanced_n160_i05` | 2.4683 | **2.4114** | 2.0525 | **2.0333** | 2.5407 | 2.0333 |
| `zero_imbalanced_n160_i07` | 3.7807 | **3.7807** | 2.9972 | **2.9972** | 4.0249 | 2.9302 |
| `zero_imbalanced_n80_i00` | 2.2954 | **1.0931** | 3.2175 | **1.0671** | 1.0931 | 1.0671 |

## Monotonicity and unproven claims

- CH29 127-node gaps no greater than its own 63-node gaps: **15/15**. This comparison tests search-budget monotonicity; it is distinct from CH29-versus-CH28 improvement.
- `fixed/63`: 239 inherited caps strictly tighter; 0/15 finite-box gap certificates; 0 Newton contractions.
- `fixed/127`: 412 inherited caps strictly tighter; 0/15 finite-box gap certificates; 0 Newton contractions.
- `equal_cpu/63`: 194 inherited caps strictly tighter; 0/15 finite-box gap certificates; 0 Newton contractions.
- `equal_cpu/127`: 434 inherited caps strictly tighter; 0/15 finite-box gap certificates; 0 Newton contractions.

All three original CH23 ambiguous zero-event cases retain **REFUSED** scientific status. Every numerical bound-gap claim is confined to the *finite root box*. A held-out detection rate or near-optimal objective bound alone cannot validate a causal estimator.

## CPU caveats

The equal-CPU controls match **solving process CPU only**. Independent replay CPU is not constrained; it is deliberately measured and included separately in the engineering-cost comparison. CH29 replay recomputes upper bounds at every internal ancestor, whereas CH28 primarily replayed terminal leaves. This additional cost must not be disguised as an end-to-end equal-CPU win.

## Verification and reproducibility

The original CH23 per-case inputs, CH27 dual matrices, CH28 baseline controls, solver sources, and 160-bit/224-bit directed MPFR primitives have SHA-256 entries in the frozen protocol and package manifest. All case receipts contain a full split tree, parent references, upper-bound modes, feasible incumbents, and verifier outcomes. Adversarial tests reject forged parent references, false certification, bogus partitions, unknown ancestor methods, and infeasible incumbents; display-only cap tampering does not affect replay.

Independent replay uses the same mathematical bounding algorithms at higher MPFR precision, not an external formally verified proof assistant. The wider precision and recomputation reduce rounding and cache risk but are not a proof of zero software defects.

## Next engineering gate

Profile the cost of recomputing internal ancestor bounds during independent replay, retain a cryptographically bound partition-replay cache only for efficiency, and add a priority-neutral controlled search comparison. Do not relax the fail-closed scientific gates or promote C14/G25 to production.