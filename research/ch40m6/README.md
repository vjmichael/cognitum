# Cognitum CH40-M.6 — frozen C14 search-level FLINT/Arb Gram vs native MPFR direct

**2026-11-03 America/Phoenix — research engineering result, not a scientific release**

## Question and experimental design

Does the existing certified Gram-matrix bound, when produced through 256-bit FLINT/Arb with exact rational linear-predictor endpoints, let the existing highest-cap-first branch-and-bound search advance farther than its native 256-bit MPFR **direct/Hadamard** producer?

We ran the **15 original CH23/CH40-J datasets**, each verified against its CH40-K source trace SHA-256 pin and original 127-node/64-terminal proof tree. Every arm starts from the identical frozen frontier and uses the same deterministic highest-effective-upper terminal selection, widest-axis midpoint split and parent-min upper-bound inheritance. Two child bounds are generated atomically per split.

Requested search CPU ceiling: **0.25 seconds per arm per case**. Full-split atomicity allows the final split to overshoot the budget. Maximum **12 splits** per arm: FLINT hit this cap early in some cases. Loading and read-only auditing are excluded from the search CPU stopwatch. Each case is validated in its own independent result file; the first single-process multi-case run timed out, so missing cases were run in bounded separate batches with the **same** settings. The combined result is a synthesis of **15 unique originally pinned runs**, not a claimed uninterrupted 15-case process.

## Measured results (all 15 frozen cases)

| Metric | Native FLINT/Arb Gram | Native MPFR direct/Hadamard |
| --- | ---: | ---: |
| Search splits completed | **153** | **21** |
| Search child bounds produced and independently recomputed | **306** | **42** |
| Aggregate search CPU across case arms | **3.320 s** | **4.376 s** |
| Better certified frozen-frontier reduction | **12 cases** | 0 cases |
| Ties (at 1e-10 display threshold) | 3 cases | 3 cases |
| Worst-case finite-root 0.05 gap closed | 0 cases | 0 cases |

FLINT completed **7.29x as many splits** as the MPFR baseline. These are distinct valid bound *formulas*—PSD Gram versus direct/Hadamard—and the FLINT arm was sometimes stopped at the 12-split cap. Consequently, **these numbers are NOT a controlled pure native-library speed ratio, NOT a matched whole-process CPU comparison, and NOT proof of a new globally optimal solution**. The verified 15-case remaining frozen frontier gaps are still > 0.05 (minimum approximately 1.06710, maximum approximately 7.52303 when using CH40-L's conservative stored incumbent lower bounds).

### Strongest example

On the original `quasi_separated_n160_i00` dataset, the fixed 0.25s search CPU budget produced:
- FLINT Gram: 10 splits, ceiling lowered by **0.4592928866**.
- MPFR direct/Hadamard: 1 split, ceiling lowered by **0.0686001199**.

A separate 0.45s / max12 one-case smoke test yielded 12 FLINT vs 2 MPFR splits, ceiling reductions 0.48312934 vs 0.10787710. Do not combine its CPU or results with the frozen all15 acceptance above.

## Audit and integrity rules

- Original trace hashes checked before execution. Historical signed CH40-J materials remain read-only.
- Producer result creates new local hash-linked event chain (not an externally anchored signed chain). Each child records its exact rational producer ceiling, box identity, inherited upper, 256-bit producer identifier and a witness metadata hash.
- Producer search includes per-child **independent rational/libmpdec bound re-evaluation**. A standalone **read-only** `audit_m6.py`, which does not import any native producer, successfully recomputed **348/348 new child bounds**, in 15 isolated independent invocations. It also verified parent selection, exact binary partitions, parent-cap monotonicity, terminal count, SHA-256 hash chain, and final frontier upper.
- **9/9** focused tests passed: original SHA, 15-case totals, real independent audit, hash-chain tampering refusal, rehashed child under-bound refusal, parent-selection mutation, scientific-status forgery, source-pin forgery and auditor import isolation.
- The original CH40-J signed proof history was not modified or re-signed. This supplement independently checks only the *new child bounds* and inherits the existing published historical acceptance; it does not redo all historical leaf mathematics.
- No IBEX superiority claim, no ability to invoke Lu, no production-ready C14, no causal identification proof, and no unrestricted-global-optimum certificate.

## Reproduction

Prepare an external, immutable research workspace containing neighboring folders `CH40K` (pinned original full traces), `CH40J/source` (rational checker), `CH40L`, `CH40L2`, `CH40L3`, `CH40M5`, and `CH40M3/site` (optional FLINT wheel). In the original experiment this folder is `/mnt/data`; in a repository clone, set `CH40M6_WORKSPACE` to point to that external workspace. The scripts **do not substitute synthetic data** if missing.

```bash
export CH40M6_WORKSPACE=/path/to/original-frozen-workspace
export PYTHONPATH="$CH40M6_WORKSPACE/CH40M3/site"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python compare_m6.py --cpu-budget 0.25 --max-splits 12 --output /tmp/ch40m6-experiment --cases quasi_separated_n160_i00
python audit_m6.py /tmp/ch40m6-experiment/quasi_separated_n160_i00.json
python -m unittest test_m6 -v
```

For a complete 15-case run, process the 15 canonical case identifiers in **separate worker processes** with the same CPU budget, exact frozen pins, and independent audits. `finalize_m6.py` combines the recorded evidence from the original lab run using its original sibling output paths and is not a generic data processor. New production integration requires a host-supervised worker, a durable atomic journal and independent witness protocol; the research runner is not that integration.

## Adoption decision

**CONTINUE RESEARCH / NOT PRODUCTION-ENABLED**: the FLINT Gram kernel has now demonstrated meaningful frontier progress, not just arithmetic microbenchmark advantage. Next: compare *the same Gram formula* using FLINT vs MPFR at matched whole-process budgets, lift the 12-split cap and use the original independent checker to validate every new bound; evaluate end-to-end 0.05 closure and Lu+model task value separately. Retain all previous conventional-library and signed-acceptance research as immutable references.
