# C14 P3D — Synthetic causal-discovery evaluation and descriptive cross-backend comparisons

Date: 2026-10-27. **Status: bounded functional-reference and validation harness; no real external library execution.** Based on the immutable C14 P3C checkpoint. This does **not** conclude all C14 production work.

## Purpose

Test *candidate* undirected PC-stable skeletons and P3A subgroup estimates without converting observational associations into verified causal relationships. Existing C14 P1/P2/P3A/B/C wire contracts remain intact; the P3D additive Protobuf schema is `proto/cognitum/causal/v1/validation.proto` and its compiler-derived binding is `cognitum/proto/causal_validation_pb2.py`.

## What is implemented

- `cognitum/causal_validation.py` accepts bounded Protobuf frames and rejects unauthorized or disabled evaluation calls. **This is an offline host-flag simulation, not Lu authentication.** No subprocess is started, and no model/cognition services are invoked.
- **Graph comparison:** requires the exact existing P3B reference discovery result to pass deterministic replay against a bound observation set; accepts an optional P3C causal-learn candidate with byte-identical dataset/parameters and an existing request-bound *shape* check. Reports overlap/Jaccard and (only when a synthetic truth fixture is explicitly declared) precision, recall, F1 and symmetric-difference counts. Empty-truth-and-empty-candidate F1=1 is an explicitly defined empty-set convention, not a demonstration of general causal learning.
- **Numerical comparison:** checks P3A empirical subgroup-standardization result with independent arithmetic and checks P3C candidate shape/binding; reports per-subgroup absolute differences, mean and maximum. **EconML LinearDML and empirical standardization can target different statistical estimands**, so a discrepancy is descriptive, not a causal estimation failure or evidence of invalid software.
- Both paths return bounded failure statuses, no partial graphs after failed validation, request SHA-256 binding, deterministic arithmetic replay receipts, and explicit assurance limitations. Every causal-structure/identifiability/real-world proof boolean remains false. The existence of a plausible external Protobuf reply does not authenticate the origin of that reply; only a trusted host, an actual runtime, and a signed provenance chain can establish it.
- New adversarial regression tests cover mutated source data, mismatched task methods, fabricated orientations, altered digests, falsified reference outputs, noncanonical synthetic graph edges, missing pairs, disabled gates and fabricated scoring.
- Deterministic small synthetic tests include a three-node chain, a negative-control independent Gaussian data set, five seeded chain samples, and an **analytic observational Markov-equivalence counterexample**: X→Y→Z versus X←Y→Z can have exactly the same Gaussian covariance. Thus these data cannot establish which of those structures caused the observations.

## Limitations and nonclaims

1. The P3D graph evaluator takes `has_declared_synthetic_truth` from an offline fixture author. It **does not authenticate the fixture**; real-world graphs must never be treated as established ground truth just because a caller supplies edges.
2. No genuine DoWhy 0.14, EconML 0.17.0 or causal-learn 0.1.4.8 runtime was exercised. Their installed packages remain unavailable here; synthetic candidate frames only test the comparison contract.
3. No causal discovery performance claim, calibrated posterior, independent PC implementation comparison, full FCI/PAG ambiguity analysis, front-door/IV identification or causal neural methods are implemented by this milestone. Those require later evaluation.
4. Python `-I`, SHA checks, and simulated `host_authorized` arguments do not satisfy Windows Job Object containment or authenticated Lu C02/C04/C06 admission. Production worker invocation stays default-off.
5. The P3D tests run on Linux Python 3.13. Neither Windows x86-64 installer/runtime nor actual target hardware has been tested.
6. External score receipts only prove *comparison arithmetic replay of the supplied captures*, not real causation or actual mature-library execution. A plausible counterfeit frame can pass a shape check and must not be promoted to provenance proof.

## Paired LLM quantization-methodology update

The former 10-arm plan is replaced by [`docs/components/evaluation/Cognitum-Lu-10-arm-model-augmentation-matrix.md`](../evaluation/Cognitum-Lu-10-arm-model-augmentation-matrix.md). Rather than 10 heterogeneous model builds, each comparison holds the **exact source checkpoint, quantized model artifact, K-cache type, V-cache type, inference build, hardware, task set, seed and base prompt fixed** and varies only Cognitum availability. Families and sizes are analysis strata; different families cannot be used as a weight-quantization substitute. A separate offline external JSON preflight validator `evals/quantization_pair_validation.py` detects mismatched arm settings, source checkpoints, KV quantization mismatch/fallback and absent matched arms. It is NOT the native Lu Protobuf inference runner or evidence that runtime values were really measured.

## Verification commands

```shell
PYTHONPATH=.:tests python -m unittest tests.test_c14_p3d_validation tests.test_c14_p3d_quantization_protocol -q
PYTHONPATH=.:tests python tools/run_c14_p3d_smoke.py
PYTHONPATH=.:tests python -m unittest discover -s tests -p 'test_c14*.py' -q
PYTHONPATH=.:tests python -m unittest discover -s tests -p 'test_c13*.py' -q
PYTHONPATH=. python tools/verify_protobuf_schemas.py --require
python -m compileall -q cognitum evals tests tools
```

See `P3D-functional-test-evidence.json` for the actual observed results and known missing gates.

## Next milestones

- C14 P3E/P4: bootstrap/alpha sensitivity analyses under statistically justified designs, independently run pinned causal-learn/EconML checks and statistical coverage studies *when dependencies can execute*; richer ambiguity semantics (CPDAG/PAG) only when their assumptions and graph encodings are explicitly modeled.
- Genuine DoWhy/EconML/causal-learn runtime, Windows Job Object containment, Lu host admission, and reviewed offline transitive dependency wheelhouses remain **open**. Do not start protected workers from model calls.
- Later: implement model inference benchmark harness; only then run the quantization-stratified, paired Lu/Cognitum study and independently score results.
