# Cognitum — Resume development here

**Active 2026-10-27 checkpoint: C14 P1 — Exact discrete structural causal models.**

Complete cumulative source ZIP in `Library / Cognitum / Development`:
`Cognitum_C14_P1_Structural_Causal_Counterfactual_2026-10-27.zip`

## Current engineering phase

Implement the full component portfolio with **standards-first mature baselines and explicitly optional, documented research tracks**. Keep thorough provenance, failure codes, host-authorized Protobuf boundaries, independent verification, metadata-only audit, benchmark-ready hooks. **Defer comprehensive comparative, hardware and real-model benchmarks** until the portfolio is built, but run targeted functional and synthetic mathematical tests. C08 HDC and C09 KAN remain deferred: reuse archived K4 rather than rebuild.

## C14 P1 content

- `proto/cognitum/causal/v1/scm.proto` and compiler-derived `cognitum/proto/causal_pb2.py`: typed interventions, factual evidence, counterfactual query, sufficient backdoor checks, assurance and provenance receipts.
- `cognitum/causal.py`: exact finite structural causal models with shared latent causes; observational vs `do` intervention separated; factual abduction-action-prediction with a shared exogenous world; NetworkX d-separation and an independent recursive model/checker; fail-closed assurance, metadata-only audit and disabled host gate.
- `tests/test_c14_causal.py` (26 focused tests, plus 60 randomized small counterfactual tasks), `tools/run_c14_smoke.py` (6 cases), `docs/components/causal/P0-P1-causal-models-and-identification.md` and `P1-functional-test-evidence.json`.
- Structural equations, exogenous noise distribution, and causal graph are **assumptions**, not identified from observational data; a failed backdoor criterion is **not** a proof of nonidentifiability. DoWhy/EconML/causal-learn are assessed but not executed here. No raw-data effect estimator or causal discovery has been implemented yet.

## Actual functional verification (Linux Python 3.13)

- **1,060 Python unittest methods accounted for across completed groups: 1,058 passed, two optional C13 runtime dependency skips, zero failed**.
- **C14: 26/26 tests**; **6/6 C14 smoke**, **28/28 Protobuf schema source-to-binding matches**, **12/12 legacy replay**, **10/10 C03 smoke**, Python compileall passed.
- The combined C11 regression stalled; its 30, 33, 18 test modules completed separately without failure. See JSON evidence record.
- No comparative benchmarking, real-world causal data, authenticated Lu host, native Rust compilation, Windows execution, or external model run.

## Next task

**C14 P2 — Mature causal identification, observational treatment-effect estimation and refutation.** Assess/install optional DoWhy worker in isolated, pinned host environment; implement typed identification of backdoor/frontdoor/IV where supported, legitimate adjustment with positivity/overlap checks, effect estimation and uncertainty, and reliability/sensitivity refutations. Preserve separate identification versus estimation versus refutation evidence and never claim real-world causation from assumptions alone. Keep the runtime unavailable flag explicit if dependencies cannot run. C14 P3 should add optional EconML CATE and causal-learn discovery with explicit epistemic provenance; then C15.

## Rehydrate

Extract the latest ZIP into a new working directory. Verify its per-file SHA-256 manifest with `PYTHONPATH=. python tools/build_library_checkpoint.py verify <archive.zip>`; run `PYTHONPATH=.:tests python -m unittest tests.test_c14_causal -v` and `PYTHONPATH=.:tests python tools/run_c14_smoke.py`.

Cognitum owns only its reference source; **do not change Lu or either GitHub repository** without explicit direction. Lu ANSF memory remains canonical; C02/C04/C06 production integration and authenticated Windows CE gates are unresolved. Prior Library checkpoints stay immutable.