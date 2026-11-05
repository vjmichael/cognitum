# Cognitum CH-C14-27 — Coupled likelihood–information bounds and selective interval Newton

**Date:** November 2, 2026 (America/Phoenix)  
**Disposition:** Research implementation and scoped numerical replay **PASS**; finite-box 0.05-gap closure **0/15**; scientific and production release **NO-GO**.  
**Isolation:** No changes to Cognitum production C14, pinned G25, Lu, DLC, or Windows. GitHub serves as source/history only.

## Problem and exact original-case provenance

All experiments use the **same** original CH23 12 index-zero bounding datasets plus the same three original zero-event ambiguity cases, with no generated substitutes. The 15 frozen CH25 inputs are SHA-256 verified against CH27's protocol and retain original CH23 data digests. Original coefficient root is `[-10,1] × [-5,5] × [-5,5]`. Source CH26 and CH24 primitives are pinned by SHA-256.

- CH27 frozen protocol SHA-256: `4875c449f1b6b12b1f1377983da6b94e9a094a549ee47f81c9e68a58af4ed928`.
- Frozen SPD dual matrices SHA-256: `a6584584ebcb34ead943d2991be6cabf75c1bb5d6f115731350cfe6cf640d49a`.
- Original CH26 frozen protocol SHA-256: `48d7c5193b806da152a9cc3ec173529333a5af752c278f20238af9a3215d07bc`.
- Frozen original-seed Newton probe SHA-256: `18a7d1f0863e8f7210e771b377d899ecf13dbf5e449b08257aecb181fb562d8c`.
- All 15 cases used 160-bit MPFR solving, 224-bit replay and absolute objective gap threshold `0.05`.

## New rigorously coupled bound

Let `F(β)=Σ_i n_i p_i(1-p_i) x_i x_iᵀ`, `p_i=σ(x_iᵀβ)` and `J(β)=ℓ(β)+½ log det F(β)`. For any **exactly positive-definite** symmetric matrix `Q`, log-det concavity gives

`log det F(β) ≤ tr(Q F(β)) − log det Q − d`.

Thus, for each row/group, a single univariate function in `p` jointly bounds the likelihood and the weight contribution:

`g_i(p)=s_i log(p)+(n_i−s_i)log(1−p) + ½ n_i (x_iᵀ Q x_i) p(1−p)`.

The second derivative is `−s_i/p²−(n_i−s_i)/(1−p)²−n_i(x_iᵀ Q x_i)`, which is nonpositive for exact SPD `Q`. Every supporting line to `g_i` is therefore a global **upper** bound. A heuristic binary64 root selects the tangent location only; its gradient, function, and resulting upper endpoint are evaluated with directed MPFR arithmetic. CH27 verifies **exact rational** Sylvester principal minors for each decimal `Q` and refuses a non-SPD or numerically uncertifiable matrix. A frozen set of up to two Q matrices per original dataset is used. The minimum of this upper envelope and CH26's independent Loewner/tangent upper envelope is valid and never looser at the same box.

**15 root-box tests:** the new dual bound was strictly tighter on **12**, and retained CH26's bound on **3**. This is a pointwise mathematical enclosure, not a global search success claim.

## Interval Newton / Krawczyk contractor

For `g=∇J`, `H(B)` an outward-rounded interval Hessian, midpoint `m`, and an exact decimal preconditioner `C`, all stationary roots in a convex box B lie inside

`K(B) = m − C g(m) + [I − C H(B)](B − m)`.

Proof validity does **not** depend on `C` being invertible, only the enclosure. A box is contractible or excludable in the global-max search **only if strictly interior to the original root domain**, since original-domain boundary maxima can have nonzero gradient. The verifier replays each permitted contraction or exclusion with 224-bit MPFR and checks that every saved narrowed box contains the replayed Krawczyk intersection. The outer search still forms a complete binary partition of the original domain, except for rigorously justified interior stationary-root exclusions. Contraction is a global-maximum *candidate-domain* reduction, not a claim that all objective values outside the retained subbox were bounded.

At the 15-node broad-root search budget, **zero contractor calls occurred** because no visited box met the original-domain interior plus width conditions. An independent frozen, original-seed ±0.001-per-coefficient diagnostic gave **6 verified contractions, 7 no-gain, 2 skips with no CH23 seed**; no synthetic substitute was introduced. Six narrow-box contractions were replayed at 224 bits. They are not counted as global pruning or global optimum certificates.

## Paired measured benchmark: same 15 nodes per original case

CH27's initially considered 63-node exploratory run exceeded its execution cap without a certificate; it is **not** included in the benchmark. A 15-node engineering budget was then frozen and used for all 15 original cases. The CH26 15-node comparator was executed subsequently, making this a **post-selection exploratory engineering comparison**, not a fresh blinded prospective study. Both solvers were replayed independently at higher precision. These results should not be compared as if they used CH26's published 127-node budget.

| Original CH23 case | CH26 @15 | CH27 @15 | Δ (CH26 − CH27) |
|---|---:|---:|---:|
| `one_event_n160_i00` | 7.8961 | 5.2758 | +2.6203 |
| `one_event_n80_i00` | 7.5763 | 4.7364 | +2.8399 |
| `quasi_separated_n160_i00` | 50.2642 | 47.1334 | +3.1308 |
| `quasi_separated_n80_i00` | 23.9689 | 23.9689 | +0.0000 |
| `rare_1pct_n160_i00` | 8.7523 | 5.6669 | +3.0853 |
| `rare_1pct_n160_i13` | 5.8453 | 2.5245 | +3.3208 |
| `rare_1pct_n80_i00` | 7.8086 | 4.8877 | +2.9209 |
| `rare_5pct_n160_i00` | 8.9827 | 8.9827 | +0.0000 |
| `rare_5pct_n80_i00` | 8.7324 | 7.1475 | +1.5849 |
| `zero_balanced_n160_i00` | 5.8521 | 2.6759 | +3.1762 |
| `zero_balanced_n80_i00` | 5.0762 | 1.9522 | +3.1241 |
| `zero_imbalanced_n160_i00` | 5.2511 | 3.9703 | +1.2808 |
| `zero_imbalanced_n160_i05` | 4.9799 | 2.5442 | +2.4357 |
| `zero_imbalanced_n160_i07` | 5.1075 | 5.1075 | +0.0000 |
| `zero_imbalanced_n80_i00` | 4.5910 | 1.0931 | +3.4979 |

- Mean remaining gap CH26/15 = **10.712300**, CH27/15 = **8.511130** (**20.55% lower**).
- Equal-node cases improved/tied/worsened: **12 / 3 / 0**. 15/15 verified unresolved; 0/15 0.05-gap closures.
- Aggregated solve+replay **CPU** seconds (sum across parallel jobs): CH26 **134.714**, CH27 **251.115** (**1.86×**). Not wall-clock latency or a matched-time benchmark.
- Tests: **10/10 passed**, including original input binding, exact SPD refusal, verified local contraction, boundary preservation, forged contraction and dual rejection, tampered tree refusal, and forged certification refusal.
- Full original data/source/output audit: see `audit27.py --replay`, which reruns every saved proof at 224 bits and independently checks the original input hashes, source pins, certificate hashes and local probe receipts.

## Release and mathematical limitations

1. This is an epsilon-gap research solver only on the **finite specified coefficient domain**. Neither exact uniqueness, an unbounded-real global optimum, nor causal effect identification, interval coverage or clinical/economic production performance is established.
2. The same original CH23 cases were reused for method development and evaluation. The post-hoc CH26/15 comparator is an engineering ablation, not independent blind validation.
3. MPFR outward rounding and higher-precision replay constitute strong numerical evidence, but the replay shares interval identities with the generator and is **not** a third-party independent theorem prover or formally verified arithmetic kernel.
4. CH27 consumed approximately 1.86× the CPU of CH26 at matched 15 nodes; the primary opportunity is caching identical logistic predictions and avoiding redundant dual/Loewner evaluations, then benchmarking at 63/127 nodes under a bounded CPU policy.
5. The three historically ambiguous CH23 zero-event datasets remain **REFUSED**; improved bounds do not erase their original distinct local maxima. No change to scientific or production C14 acceptance.

**Decision: CH27 engineering PASS (scope above); global optimum gate UNRESOLVED; production/scientific NO-GO.**