# Cognitum C14 P4E G13: End-to-End Assurance Integration

**Date:** 2026-10-28  
**Status:** offline, Protobuf-native, synthetic-research integration checkpoint; **NOT** a Lu/Windows release gate.  
**Scope:** Cognitum only. No Lu repository, GitHub branch, Windows AppData directory or original G12 checkpoint changed.

## Objective and actual test path

G13 connects the existing reference computation and assurance stages. It uses an explicitly bounded typed interface rather than parsing an LLM's prose into authority:

1. **Scientific reference**: G9 `causal_interval_comparison` computes a synthetic interval and replay-checkable calculation receipt for a G7-style seeded dataset. The candidate result is not necessarily an external DoWhy/EconML worker output; G13 does **not** exercise the genuine-library worker path itself.
2. **G10**: `causal_assurance_policy` verifies the calculation receipt, compares against pinned G9 synthetic calibration, and refuses known confounding/positivity/undercoverage claims.
3. **G11**: `causal_holdout_assurance` replays G10 and evaluates the independent synthetic holdout gate. It can narrow or preserve, but cannot expand, G10's permissions.
4. **G12**: `causal_adversarial_assurance` replays G11 and an independent *count-based numerical verifier* over the 960-record synthetic study. It rejects unverified reports and refuses transfer of calibration to G12's new generator family.
5. **G13**: `causal_integrated_assurance` replays the complete G12 request/decision/receipt chain, confirms the pinned G12 source, inspects **typed** caller intent and untrusted assertions, and emits a new `IntegratedAssuranceDecision` plus a request-bound `IntegratedAssuranceReceipt`.

Output **never** authorizes intervention recommendations, real-world causal claims, external tool actions, or Lu host authority. The most permissive G13 result is `INTEGRATION_DESCRIBE_SYNTHETIC_DIAGNOSTIC_ONLY`, allowing only an explicitly qualified synthetic *stress-test diagnostic*; it **does not upgrade** G10/G11/G12 abstentions about causal identification. All output messages are fixed safe templates; untrusted caller prose is never echoed or executed.

## Key files

- `proto/cognitum/causal/v1/integrated_assurance.proto`: typed G13 request/decision/receipt and caller-intent enums.
- `cognitum/proto/causal_integrated_assurance_pb2.py`: compiler-derived Protobuf descriptor binding.
- `cognitum/causal_integrated_assurance.py`: fail-closed policy composition, scope binding, and replay-verifiable receipt.
- `tests/test_c14_p4e_g13_integration.py`: simulated malicious caller, tampering, replay across scopes, upstream-abstention and authority tests.
- `tools/run_c14_p4e_g13_acceptance.py`: reproducible 32-case simulated-caller matrix; **not** a real LLM benchmark.
- `tools/run_c14_p4e_g13_verify_report.py`: separate report-shape and authority audit, with deterministic functional replay option.
- `tests/test_c14_p4e_g13_evidence.py`: evidence-auditor negative tests.
- `docs/components/causal/P4E-G13-adversarial-caller-evidence.json`: per-case machine-readable result hashes, dispositions, and reason codes. Untrusted caller narratives are not stored in this report.

## Distinct threat cases and expected safeguards

| Challenge | Result |
|---|---|
| Valid clean/hidden-confounding/etc. synthetic cases, descriptive intent | Qualified **synthetic stress-test** description only; no point-causal certainty |
| LLM asks to assert established causality | `INTEGRATION_ABSTAIN_CAUSAL_OVERREACH` |
| LLM asks for intervention or execution | `INTEGRATION_ABSTAIN_CAUSAL_OVERREACH`; no tool call |
| LLM asserts it verified causal proof or received Lu authority | `INTEGRATION_ABSTAIN_UNTRUSTED_ASSERTION` |
| G10/G11 upstream abstains | `INTEGRATION_ABSTAIN_UPSTREAM`, no synthetic description upgrade |
| Unknown G12 scenario or altered G12/G11/G10 evidence or receipts | `INTEGRATION_REJECT_UNVERIFIED` |
| Prompt-injection text in untrusted narrative | No text execution, no echo; the hardcoded descriptive message stays unchanged |
| Replayed result across different conversation, task, trace, or caller-intent | Deterministic receipt verification fails |
| Forged `may_trigger_external_action`, Lu-host bit, or causal-proof bit | Deterministic verifier rejects |
| Unknown enum, missing scope, out-of-range input | Abstain or reject malformed input, never authorize |

Caller-supplied `conversation_id`, `task_id`, and `trace_id` are bound to the resulting checksum and **NOT evidence that a Lu host authenticated those IDs**. A malicious caller can provide arbitrary valid scope labels; host validation remains a separate, unimplemented gate. SHA-256 replay receipts are **not signatures**, and local source hashes do not provide independent publisher attestation. G13 is therefore a correctness and fail-closed prototype under a trusted local runtime, not an isolation boundary against a compromised executable.

## Results and repeatability

- **33** integration unit tests passed, plus **10** independent evidence-audit tests: **43 focused G13 tests**.
- **32** synthetic simulated-caller acceptance cases passed (six mechanisms × four typed intents + eight adversarial extras), with **zero** authorized actions.
- The acceptance report passed an independent structural/authority audit and a deterministic functional replay comparison.
- Selected C14 regression: **596 tests run, 37 skipped, 559 passed, zero failures** (includes the original 33 G13 integration tests). When the ten evidence-audit tests are included, total C14 becomes **606 run, 37 skipped, 569 passed**.
- Selected C13 regression: **141 run, two skipped, 139 passed, zero failures**.
- **47/47** Protobuf files independently compiled and checked against compiler-derived Python binding descriptors.

Run from repository root (`PYTHONPATH=.`):

```text
python -m unittest tests.test_c14_p4e_g13_integration tests.test_c14_p4e_g13_evidence -q
python -m tools.run_c14_p4e_g13_acceptance
python -m tools.run_c14_p4e_g13_verify_report
python tools/verify_protobuf_schemas.py --require
python -m unittest discover -s tests -p 'test_c14*.py' -q
python -m unittest discover -s tests -p 'test_c13*.py' -q
```

## Limitations and remaining gates

1. No actual LLM was invoked. The malicious caller is simulated via typed requests and text payloads. Real model-tool choice, honesty, and prompt-following behavior remain unmeasured.
2. G13 does **not** execute external mature-library backends end-to-end. Prior genuine EconML, causal-learn and uploaded-development-source DoWhy experiments are separate G5–G7 evidence, not G13 validation.
3. G12's independent verifier recomputes recorded synthetic counts and aggregate metrics, **not** the truth of graph assumptions, experimental randomization, data provenance, or real-world transportability.
4. No cryptographic signing, trusted publisher/version provenance, Windows Job Object confinement, authenticated Lu host admission, tool permission grant, or external action/rollback mechanism has been implemented or verified here.
5. No independent third-party formal audit. The source-integrity checks assume the local checker implementation and pinned source roots are trusted.
6. DoWhy's exact pinned v0.14 provenance and broad LLM WITH/WITHOUT Cognitum evaluation remain open.

**Next engineering gate:** attach a genuine scientific-worker result through an authenticated, OS-confined and host-permission-bound adapter; then conduct real LLM caller trials under an independently defined safety/accuracy benchmark. G13's research-only result must not be silently promoted to production authority.

## Historical replay note

During G13 final verification, a fresh invocation of G12's **full synthetic generator replay** exceeded the combined verification command's timeout; its result was **not** counted as a completed G13 check. A distinct G12 independent numerical audit *did* successfully recompute all 960 count-based records and all 12 scenario/sample-size aggregate summaries. G12's own earlier archival evidence records its historical generator replay separately.
