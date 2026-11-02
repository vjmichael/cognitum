# Cognitum CH-C14-30 — In-process incremental MPFR certificate replay

**Research only.** Cognitum C14/G25 scientific promotion **NO-GO**. No production C14, Lu, Windows, model runtime, or G25 changes.

## Scope and invariants

CH29's 224-bit independent verifier recomputed every bound for every ancestor when replaying each certificate. For each of the original 15 CH23 datasets, the saved fixed/127 certificate is an extension of the fixed/63 proof tree, preserving all original proof-relevant node data except that previously terminal nodes acquire validated splits.

CH30 implements `VerifiedSession` in `verifier30.py`:

1. **Cold replay**: independently verify every bound in the original 63-node CH29 certificate, including its root, design/model, duals, tangent anchors, exact partition and feasible incumbent. Retain exact 224-bit MPFR caps and a deep copy of the verified tree **in memory only**.
2. **Incremental replay**: before reusing caps, bind the new 127-node certificate to the same original CH23 input, all proof-relevant protocol fields, identical exact dual matrices and replay precision. Require every old node's proof-relevant fields to remain byte-for-byte equivalent; only an old leaf may acquire a partition, which must be fully verified. Reuse the 63 prior MPFR caps, compute 64 new node bounds at 224 bits, propagate certified parent caps, validate the entire binary subdivision, and re-evaluate the final feasible incumbent and leaf gap.
3. **Refuse on mismatch**: structural or binding changes, unverified contracted boxes, falsified claims, altered original input, or missing nodes fail closed. An exception does not commit a new checkpoint; the previous verified session state remains usable.

Checkpoint state has no import/export or file serialization. A **fresh process must always perform cold full replay first**. The in-process cache is not a general authorization mechanism or protection against arbitrary malicious code executing in the same Python interpreter. Display-only upper bounds are not proof authority; independent original CH29 verifier can still replay each certificate cold.

The only allowed protocol difference for continuing an existing verified proof is a node-budget extension or a CPU stopping budget. Other numerical/proof parameters must remain identical. This avoids incorrectly reusing caps computed at a different rounding precision.

## Reproduction

From the directory containing original `CH_C14_24/`, `CH_C14_25/`, `CH_C14_26/`, `CH_C14_27/`, and `CH_C14_29/` as siblings:

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
python -m pytest -q CH_C14_30/tests/test_incremental.py
python CH_C14_30/benchmark30.py --workers 3
python CH_C14_30/audit30.py
```

The prospective benchmark protocol and SHA256 are in `frozen_protocol.json` and `frozen_protocol.sha256`. The benchmark compares each case's CH30 cold/63 plus warm/127 CPU against the archived original CH29 verifier's independent cold/127 CPU; each of the 15 historical cases is evaluated from its own exact CH23 input hash. This is **verifier CPU**, not solver CPU or wall-clock throughput. Check the engineering report and `benchmark_results.json` for precise timings.

## Proof and science boundaries

- Valid finite coefficient box only (`[-10,1] × [-5,5] × [-5,5]`); epsilon objective gap target 0.05 remains unproven for all historical cases.
- This is a **verification optimization**, not a tighter likelihood/Fisher bound, interval-Newton result, proof of uniqueness, unbounded global optimality, causal identification, or confidence-interval calibration.
- Both cold and incremental paths use the existing MPFR bound implementation. Independent replay and malicious-input tests reduce implementation risk but are not a formal third-party proof assistant.
- The original CH23 ambiguity refusals are unchanged. No production estimator was promoted.
