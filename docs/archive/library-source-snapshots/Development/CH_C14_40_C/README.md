# Cognitum CH40-C — Independent producer-rule replay and research attestor gate

**Research scope only.** Full source archive is SHA-256 pinned to original CH39 frozen proofs. It does not rewrite older certificates or modify Cognitum production, Lu, or CH39 services.

## What this phase verifies

- Exact original 127-node topology per case (15 frozen cases; 1,905 nodes), including exact rational split partitions and inherited-bound ancestry.
- Recognized producer numerical modes: direct, coupled logdet-dual, and fallback to direct; independently recomputes conservative safe upper enclosures with the separate CH40-A/B Python `decimal` implementation.
- Exact equality of each historical displayed inherited cap to `min(local displayed cap, parent's displayed cap)`. **This checks recorded arithmetic consistency, not the numerical soundness of those caps.**
- For each node, evaluates whether an independently valid conservative upper is at most the producer's *displayed* local/inherited number. A `False` result means **NOT VERIFIED**, not necessarily mathematically wrong.
- Refuses any archived Newton contraction/exclusion not independently verified; historical CH29 certificates have **zero accepted Newton events**. Taylor and Krawczyk rules have prospective original-data tests, but no archived Taylor/Newton actions to independently replay.
- Protocol-only CH39 research attestor admission demonstration: pinned original case certificate hash, pinned checker signing key (configured outside untrusted client input), Ed25519 domain separation, one-use nonce, source digest, exact checker-result commitment, explicit `NO_GO`, and **no promotion to producer-certified or unrestricted global claim**. Attestor never reads sealed mathematical sources or recomputes math.

## Critical mathematical limitation

The original producer certificates contain 127 per-node `*_upper_bound_display` floating-point numbers but **not** the per-observation tangent support points and directed-rounding proof trace needed to independently reproduce every optimized producer local bound. Conservative alternative enclosures can often be looser. Therefore:

- Independently reconstructed proof geometry or consistent inheritance **does not prove producer cap soundness**.
- `producer_optimized_rules_fully_certified` is always `false` and the attestor returns research-only acceptance with `may_publish_CH39_production_witness=false`.
- The finite-box 0.05 objective gap and unrestricted global optimum remain unproven. `scientific_release=NO_GO`.
- The independent Decimal arithmetic library is different from MPFR, but has **not** been formally verified at the implementation level.

## Running on Windows

Extract this full ZIP into a short directory. Run `RUN_CH40C_WINDOWS.cmd`, or:

```cmd
python batch40c.py --jobs 4 --out CH40C_RESULTS
python -m unittest discover -s tests -p test_rule_attestation40c.py -v
```

The mathematical replay requires only Python 3.13+ standard library; the **mock Ed25519 attestation regression** also uses Python `cryptography`. Unlike the prior CH25-31 bench, no Windows MPFR DLL is needed. Each of the 15 case reports is written atomically. A rerun recomputes the math rather than blindly treating unsigned cached outputs as trusted.

## What is next

1. Extend producer certificates to preserve exactly defined dual matrix, per-observation tangent p0, interval upper witnesses, Taylor centers/Hessian enclosures, Krawczyk matrices and accepted exclusion/contraction scope, with their source hashes.
2. Verify those richer witnesses with the independent code, not by trusting `*_display` float fields.
3. Introduce a real separate checker signing identity and durable nonce registry into CH39's Linux service topology. Test cross-user access, hard exits, orphaned records and source rollback. No actual CH39 service connection is claimed in CH40-C.
4. Run new Windows CH40-C package and independently check results. Prior CH25–31 113/113 Windows numerical results remain unchanged.