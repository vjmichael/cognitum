# Cognitum CH-C14-28 — selective coupled-bound evaluation and cache-aware MPFR search

**Date:** November 2, 2026 (America/Phoenix)  
**Scope:** Standalone Cognitum C14 research; no production, G25, Lu, Windows or DLC modification.  
**Disposition:** Engineering verification complete; 0/30 finite-domain 0.05-gap proofs. Scientific and production NO-GO.

## Immutable provenance and new protocol

The 15 input JSONs are the original CH23 SHA-bound dataset reproductions used in CH25–CH27: 12 frozen original bounding cases and three previously ambiguous zero-event cases. No regenerated or substituted datasets were used for the present benchmark. The pinned CH27 coefficient root box is `[-10,1] × [-5,5] × [-5,5]`, 160-bit directed-rounded MPFR solve, 224-bit replay, absolute objective gap 0.05. Each case was rerun at **63** and **127** nodes. The protocol was frozen before the first run:

`e19c2c2d237892e48cd9688e73ade19dc3a9220dc459925ce6dedc0a09cac906`

CH28 does **not** rewrite CH23–CH27 certificates, and does not assert a globally unique solution over all real coefficients.

## Algorithms

Every node receives the sound CH26 Loewner/log-likelihood MPFR upper bound. A node whose direct bound is already within the incumbent threshold skips coupled evaluation. Otherwise, CH27’s exactly-SPD coupled Fisher–likelihood dual bound is evaluated on nodes through depth 2 and each subsequent third node by insertion ID, and the tighter bound is used. This selection rule is a heuristic for *speed and search ordering*, not for certification. Other nodes retain the conservative direct upper bound.

The solver caches each complete node’s 160-bit MPFR upper endpoint and reuses it to calculate the maximum retained leaf bound, avoiding CH27’s extra pass over the entire leaf set. The **224-bit verifier does not trust cached endpoints or binary64 display values**; it rebuilds the complete partition and any interior Newton contract proof, then recomputes each leaf’s upper bound under the recorded valid method. Unresolved proofs remain explicit refusals.

## Full original-data benchmark

| Metric | 63-node cohort | 127-node cohort |
|---|---:|---:|
| Original cases / independent replays | 15/15 | 15/15 |
| Mean upper objective gap | 4.825871 | 3.942796 |
| Median upper objective gap | 4.153979 | 3.963545 |
| Maximum upper objective gap | 11.743448 | 7.989437 |
| Coupled bound calls | 366 | 667 |
| Direct bound calls | 945 | 1905 |
| Cached terminal leaf values reused | 480 | 960 |
| Newton contractions in global search | 0 | 0 |
| Solver CPU seconds (sum) | 825.457 | 1193.869 |
| 224-bit replay CPU seconds (sum) | 160.270 | 285.715 |
| Finite-box global certificates | 0 | 0 |

### Per-case upper objective gaps (independently replayed)

| Original CH23 case | 63 nodes | 127 nodes |
|---|---:|---:|
| `one_event_n160_i00` | 5.099691 | 3.963545 |
| `one_event_n80_i00` | 3.835292 | 3.061232 |
| `quasi_separated_n160_i00` | 11.743448 | 7.989437 |
| `quasi_separated_n80_i00` | 7.533302 | 5.347579 |
| `rare_1pct_n160_i00` | 6.595701 | 4.028498 |
| `rare_1pct_n160_i13` | 3.507829 | 4.970787 |
| `rare_1pct_n80_i00` | 4.823468 | 3.659225 |
| `rare_5pct_n160_i00` | 5.654974 | 4.192020 |
| `rare_5pct_n80_i00` | 5.117430 | 4.078120 |
| `zero_balanced_n160_i00` | 3.648561 | 4.736053 |
| `zero_balanced_n80_i00` | 2.130058 | 2.023196 |
| `zero_imbalanced_n160_i00` | 4.153979 | 2.825003 |
| `zero_imbalanced_n160_i05` | 2.468284 | 2.052512 |
| `zero_imbalanced_n160_i07` | 3.780668 | 2.997229 |
| `zero_imbalanced_n80_i00` | 2.295384 | 3.217505 |

## Equal-node CH27 comparison (one original case, not general population inference)

The unchanged CH27 full coupled-evaluation solver was additionally run on the **same original** `zero_balanced_n80_i00` data at both budgets. These control runs modify only the node budget in memory. They are new exploratory controls, not modifications of CH27’s frozen 15-node results.

| Budget | CH27 full coupled gap | CH28 selective gap | CH27 solve+replay CPU s | CH28 solve+replay CPU s | CH28 CPU saved |
|---|---:|---:|---:|---:|---:|
| 63 | 1.574618 | 2.130058 | 64.605 | 41.387 | 35.9% |
| 127 | 1.386876 | 2.023196 | 107.876 | 63.342 | 41.3% |

The selective solver saves CPU on this case but returns a **looser** upper gap. Do not interpret the CPU benefit as a mathematical proof-quality improvement.

## Assurance and limitations

- The independent high-precision verifier accepts only a complete binary partition of the original root, valid interior-root contractions/exclusions, and sound direct or coupled MPFR bounds on all live leaves. Tampered partitions, incorrect global claims, altered root boxes and unsupported bound methods are rejected by tests.
- The three original zero-event ambiguous datasets retain their historical refusal status. Finding a better local maximum, or a smaller finite-domain upper gap, cannot override causal-identification or global-uniqueness gates.
- The cache is only a performance feature. Every terminal upper bound in each proof record was recomputed by the verifier at 224 bits. CH28 shares the underlying MPFR interval mathematics with CH24–CH27; this is not a separately formalized theorem-prover implementation.
- Cumulative CPU time is the sum of per-process CPU measurements. Benchmarks ran concurrently, so wall times and aggregate CPU are not interchangeable, and original CH26/127 or CH27/15 figures are not equal-node comparisons.
- Broader coefficient domains, unrestricted global optimization, optimality/uniqueness of the Jeffreys estimator, causal coverage/calibration and external R equivalence remain unproven. **C14 scientific and production release NO-GO.**

## Next measured engineering steps

1. Preserve the CH28 63/127 baseline and compare alternate *safe* selective gates on the exact same 15 cases using preregistered CPU/time budgets; consider dual benefit measured at parent nodes and best-first bound uncertainty.
2. Improve coupled scalar surrogate evaluation without heuristic precision loss; explore verified relative determinant bounds and interval-Hessian bounds that actually prune live search nodes.
3. Before any promotion, test larger and unseen nonzero-event cohorts, prove parameter domain tail bounds (or refuse unbounded claims), and complete the separate scientific release gates.