# CH40-M.8 — Exact-key independent-bound verification reuse

**Date:** 2026-11-03 America/Phoenix (2026-11-04 UTC)  
**Engineering gate:** PASS for an opt-in *research* verifier, subject to CI and packaging review.  
**C14 scientific release:** **NO_GO**; no finite-root 0.05 global proof and no causal-identification claim.

## Problem and solution

M.7's 15 frozen original CH23/CH40-K cases each have two accepted same-formula Gram search journals (native FLINT/Arb and native MPFR). The independent rational/Decimal audit re-evaluated all 242 new child upper bounds. However, both arms often split *exactly the same parameter box*, resulting in identical mathematical upper-bound propositions being checked twice.

M.8 constructs a **volatile, in-process, independent-proof cache** keyed by:

```
(original_trace_sha256, 'PSD_GRAM_DOMINANCE', canonical_exact_rational_parameter_box)
```

Each cache entry is computed by the unmodified independent CH40-J rational/Decimal checker through `independent_psd_check.independent_bound` in the **auditor process**. On every new journal child, the independently established sufficient Gram upper bound is compared against *that child's* claimed local upper cap. A parent cap inheritance, exact binary split, selection policy, backend metadata, source hash, journal digest chain, and reported final frontier are checked even on a cache hit. No upstream witness boolean is treated as proof. Different original traces **never** share computations. No cache or external numerical witness is loaded from disk; an evidence ledger is emitted *after verification* and is **not a future trusted input**.

The two native producers are **not imported by the verifier**. The preexisting signed CH40-J chain, C14 optimizer, and Lu are not modified.

## Measured original-data experiment

Environment: Linux Python 3.13, independently executed rational/Decimal checker. Original M.7 accepted 30 journals and all 15 CH40-K trace+certificate SHA pins; same ordering and audit code with the cache toggled, sequential runs, isolated process CPU timers (`time.process_time`). No native FLINT/MPFR is required to run the verifier.

| Measured value | No memoization | Exact-key memoization |
|---|---:|---:|
| Frozen cases | 15 | 15 |
| Original search journals | 30 | 30 |
| Child upper-bound checks | **242/242** | **242/242** |
| Independent rational/Decimal computations | 242 | 130 |
| Safe duplicate-proposition hits | 0 | 112 |
| Unique proved `(source, formula, box)` propositions | 130 | 130 |
| Auditor process CPU | **25.60230 seconds** | **16.44764 seconds** |
| Peak RSS (reported by `/usr/bin/time`) | 618764 KiB | 618896 KiB |
| Final journal receipt commitment | same | same |
| Proof ledger commitment | same | same |

**Measured verifier CPU reduction: 35.76%, or 1.5566x audit throughput.** This is not an optimized whole C14 pipeline, a claim of native-library superiority, or an equal-RAM whole-solver benchmark. Timing includes loading the original evidence in each verifier process and recomputing the original tree/partition checks; producer search was not rerun. Single sequential paired runs are not a confidence interval.

The two modes produced identical 30 audit receipts (`archive_sha256` `f3a5207f0b01a326ff8f1a8bea0dfb141aebd9ef901608d93f3c054323add05c`) and identical 130 exact-proof entries (`proposition_ledger_sha256` `6f9cef6a65d0e69195953f283c7d0f44ec0d630a6785910c08774a37c81956af`). Every occurrence still has a bound comparison, and every distinct proposition is independently computed from the frozen data. A cache hit is a mathematical *same-input reuse*, not an assumption that two close-looking numbers are equal.

**12/12** focused negative, identity, original-fixture and acceptance tests pass, including a deliberately rehashed under-bound journal that remains refused even after the cache is populated. The old independent M.7 audit for the selected pilot case has the same final upper, journal tip and child count.

## Source and evidence

- `audit_m8.py` — read-only standalone 15-case batch rational auditor with exact-key in-process memoization and proof ledger. `--mode fresh` disables reuse but otherwise runs the same verifier.
- `test_m8.py`, `test_m8.log` — original-fixture checks and adversarial tests (no synthetic acceptance replacement).
- `evidence/all15_cache.json`, `evidence/all15_fresh.json` — full original-source-bound receipts, 130 numbered proof statements and 242 child-to-proof references, plus measured process CPU.
- `evidence/CH40M8_ACCEPTANCE.json` — matched-result acceptance summary and refusal/test verdicts.
- `input_m7/` — exact source M.7 original 30 research journals and previously accepted independent audit receipts (copied read-only for reproducibility); **does not include the original ~800 MB CH40-K frozen traces or the CH40-J signed chain**.
- `MANIFEST_SHA256.json` — per-file SHA-256 of research bundle members; no invented code certification key.

From an isolated Linux research environment with the **original** CH40-J, CH40-K, CH40-L/L2 and CH40-M5 paths and the M.7 input journals:

```bash
export CH40M8_WORKSPACE=/path/to/research/workspace
python audit_m8.py --input "$CH40M8_WORKSPACE/CH40M7/accepted" --mode cache --output /tmp/m8-cached.json
python audit_m8.py --input "$CH40M8_WORKSPACE/CH40M7/accepted" --mode fresh --output /tmp/m8-fresh.json
python -m unittest discover -s . -p test_m8.py -v
```

The verifier never silently substitutes synthetic cases if originals are unavailable; the CLI refuses missing data and the original-case unit suite explicitly skips.

## What this does NOT prove

- It does **not** sign or authenticate a proof cache across processes, nor accept imported proof attestations. Persisted caches would require a separate authorization, integrity and verifier-identity design.
- It does **not** establish that a local optimizer finds a global maximum or validate causal identification.
- It does **not** improve any CH40 original upper cap or close the target finite-root 0.05 objective gap.
- It does **not** make reduced-precision or unverified numerical computations admissible. The independent mathematical reference is unchanged.
- It does **not** revise historical signed CH40-J evidence or enable Cognitum or Lu production.

Next research gate: integrate the cache within the fully trusted verifier service without trusting external proof blobs; measure end-to-end worker-plus-auditor cost against identical-case runs; run larger frozen frontiers under bounded resources. If a persistent receipt store is proposed, establish trusted verifier key management and explicit independent replay requirements first.
