# Cognitum CH40-A — independent Decimal/rational finite-box certificate checker

**Date:** 2026-11-03. **Research only; not production promoted.**

## Scope and trust

This is new independent mathematical implementation, not a second process of the inherited MPFR routine. It does **not** import Cognitum CH23–CH39 mathematical modules in the checker. `exact_decimal40.py` uses CPython/libmpdec 85-digit directed-decimal operations (roughly 282-bit decimal significance); `.exp()` and `.ln()` are correctly rounded half-even in Python decimal, then widened by one representable step. Model, proof-tree, matrix symmetry, Sylvester SPD and split geometry use Python `Fraction` exact rational numbers. No binary floating point is used in proof decisions.

The independent checker:

1. Accepts only the exact original CH39 reproduction ZIP SHA256 (`9e713b10...`); verifies each CH33 checkpoint file against frozen CH39 SHA256, each envelope and compressed original certificate and the original CH29 case protocol digest.
2. Rebuilds every 127-node binary branch-and-bound partition from exact decimal/rational endpoints. Validates all parent/depth/effective boxes and 64 leaves; refuses unverified Newton contraction.
3. Checks grouped Bernoulli model counts, nonzero exact-rational design minor, and all dual matrices for exact SPD.
4. Recomputes 64 **independent, conservative Firth-logistic objective upper bounds** per certificate using monotone per-row log-likelihood bounds and Hadamard information-determinant upper bounds; obtains an incumbent lower bound from a positive exact Cauchy–Binet reference minor and independent direct interval determinant evaluation.
5. Independently checks whether the finite-box gap is proven, refusing any false `CERTIFIED_BOUNDED_GAP`. Retains original `NO_GO` for all observed cases.
6. Writes an atomic, source-fingerprint-bound JSON result after each case, including failures, allowing interrupted runs to resume only with the exact same code and original archive.

## Important limitations

- Conservative **independent** bounds are deliberately weaker than the source's optimized coupled-information/Taylor/interval-Newton bounds; CH40-A **does not certify all producer local upper-bound numerical values or equivalence with the CH39 verifier**, and therefore is not yet appropriate as a CH39 attestation gate.
- Original CH33 127-node data contain no Newton-contracted nodes and so contraction verification is explicitly refused rather than faked.
- Only original frozen finite coefficient boxes are checked. No full R^d global optimum and no 0.05 gap bound was demonstrated. All 15 remain `NO_GO`.
- Python/libmpdec is an independent arithmetic implementation, but not a formally proven proof assistant. Its exp/ln guarantee depends on Python Decimal's correctly-rounded contract. Next phases should establish a separately coded rigorous coupled bound, affine/Taylor bounds, and a recognized proof-checker specification.
- The CH39 archive pin is embedded in source code and independently verified through prior GitHub/witness evidence. Protection from a malicious actor who can replace both program and pin requires an external trust root.
- This checks independent arithmetic, NOT Linux UID isolation, signing service, journaling durability or off-host witness.

## Windows execution

Extract the complete CH40-A ZIP. Double-click `RUN_CH40_INDEPENDENT.cmd`. Uses working `python.exe`, fallback `C:\Python314\python.exe`, **no pip or MPFR DLL required**. Saves `CH40_RESULTS/CH40A_original15_results.json` after each original case; rerunning resumes with strict code/archive fingerprint checks.

## Development acceptance

- All 15 original frozen cases: `PASS_INDEPENDENT_REPLAY_UNRESOLVED`.
- 1,905 exact partition nodes and 960 independent upper-bound computations verified.
- 19 original-data and adversarial tests passed, including fake scientific certification, out-of-domain incumbents, altered parent/partition, non-SPD duals, illegal release, and nonfinite arithmetic rejection.
- Original CH39 and CH23–39 sources unchanged.

## Next: CH40-B

Implement an independently derived and interval-verified *coupled likelihood–Fisher dual* upper bound (plus independently checked Taylor/Newton domain contraction when applicable); compare objective enclosures on held-out and adversarial cases and integrate only after independently established bounded-gap claims and adversarial tests.
