# Cognitum CH-C14-30 — Incremental MPFR proof verification

**Date:** 2026-11-02 · **Scope:** Original CH23 finite-box interval proof engineering. **C14/G25 scientific promotion: NO-GO.**

## Work completed

Replaced repeated full 224-bit MPFR verification of unchanged CH29 ancestor bounds with a safe **in-process incremental certificate session**. The initial 63-node proof is fully replayed independently; a 127-node extension may reuse the same 63 exact MPFR cap objects only if the verified nodes are unchanged and every new split is geometrically validated. All 64 new node bounds are recomputed at 224-bit MPFR, the complete partition is traversed, incumbent feasibility and objective floor are checked again, and the 0.05 objective-gap decision is independently reconstructed.

There is **no external checkpoint restore**: restarting the verifier requires cold full replay. The cache cannot be deserialized or treated as standalone proof. A modified tree, unknown bound mode, changed input, proof parameter or failed claim is rejected without updating the trusted session.

## Frozen original-data results

- Original CH23 cases: **15/15**, including three historical zero-event ambiguity refusals.
- Proof-decision and gap agreement with original CH29 full verifier: **15/15**.
- 224-bit MPFR caps reused in second-stage replay: **945**; newly computed: **960**.
- All original 0.05-gap global certificates: **0**; all remain unresolved.
- Frozen CH30 protocol SHA256: `b86793a9da30a1b5f6fa4dc9a91470b764d591ec1984214343f0466d62626d73`.

### Per-case verification CPU (seconds; original archived fixtures, no substitutes)

| Original CH23 case | Cold 63 | Incremental 127 | CH29 cold 127 | Incremental speedup |
|---|---:|---:|---:|---:|
| `one_event_n160_i00` | 23.93 | 23.71 | 43.57 | 1.84× |
| `one_event_n80_i00` | 11.33 | 11.27 | 24.07 | 2.14× |
| `quasi_separated_n160_i00` | 20.96 | 20.96 | 38.47 | 1.84× |
| `quasi_separated_n80_i00` | 11.04 | 9.49 | 18.54 | 1.95× |
| `rare_1pct_n160_i00` | 22.46 | 22.11 | 43.73 | 1.98× |
| `rare_1pct_n160_i13` | 21.81 | 20.66 | 42.19 | 2.04× |
| `rare_1pct_n80_i00` | 10.84 | 11.21 | 21.02 | 1.87× |
| `rare_5pct_n160_i00` | 21.88 | 21.51 | 41.82 | 1.94× |
| `rare_5pct_n80_i00` | 11.87 | 10.42 | 21.39 | 2.05× |
| `zero_balanced_n160_i00` | 22.42 | 20.58 | 42.81 | 2.08× |
| `zero_balanced_n80_i00` | 10.75 | 11.16 | 21.69 | 1.94× |
| `zero_imbalanced_n160_i00` | 22.82 | 21.54 | 43.61 | 2.02× |
| `zero_imbalanced_n160_i05` | 22.38 | 22.16 | 43.45 | 1.96× |
| `zero_imbalanced_n160_i07` | 22.37 | 22.64 | 43.56 | 1.92× |
| `zero_imbalanced_n80_i00` | 11.59 | 11.22 | 20.97 | 1.87× |

| Aggregate | **268.44** | **260.65** | **510.89** | **1.96×** |

**Measured aggregate saving on the incremental step:** 49.0%. **Measured saving for verifying both certificates together:** 32.1%. The latter includes the required full verification of the 63-node checkpoint; no cold-start speedup is claimed.

## Security and numerical soundness

- `verifier30.py` accepts CH29 certificates as-is. First verification reconstructs every ancestor cap from the proven mathematical bound methods at 224-bit MPFR. Subsequent certificates are bound by SHA-256 to all unchanged proof-relevant inputs and protocol fields; the old proof-relevant node data are compared exactly.
- A previous leaf may become an internal node only with a validated binary split. New leaves require fresh outward-rounded bound evaluation. A fresh feasible incumbent is checked for every new certificate, and all leaf caps are used in a fresh gap decision.
- 15/15 targeted adversarial and functional tests passed (including forged global certification, changed partitions, changed duals and precision, and mutation after prior successful verification).
- A failed incremental replay cannot replace the previously verified state. No disk cache, signature delegation or untrusted checkpoint import path exists.
- The original CH29 verifier is retained for cold differential replay; the CH30 verifier still shares underlying MPFR logistic/Fisher interval code and is not an external formally certified proof assistant.

## Evidence and scientific limits

- Original CH23 source/deterministic data hashes and all CH29 reference certificates remain in `research/ch_c14_23/` through `research/ch_c14_29/` in Cognitum GitHub and the original CH29 reproduction archive.
- No adjusted statistical estimator, global-search output, scientific causal identification, or production C14/G25 algorithm was changed.
- Numerical decisions concern only the fixed coefficient domain `[-10,1] × [-5,5] × [-5,5]`. Global optimality over all real coefficients, uniqueness, and valid confidence interval calibration remain **unproven**.
- CPU timings are process CPU on this Linux environment. They measure verification cost, not solver throughput, not cross-machine absolute speed and not wall-clock improvement under different parallel schedules.

## Next engineering gate

Profile shared-memory verification across more than two successive checkpoint budgets. For process-restart recovery, treat any persistent proof cache as untrusted until independently reconstructed or attested by a separately validated trust mechanism; never silently replace a mathematically verified bound with an unauthenticated display value.