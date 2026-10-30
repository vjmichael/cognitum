# Cognitum C14 P4E G15 — real-model-ready causal caller evaluation

**2026-10-28.** Parent: sealed, SHA-verified G14 archive (`ab7dc8162fe9e552868907468d854c436428ab2360a253305fa1a1d8c4aa841c`). Independent source checkout; **no modifications to Lu, GitHub, or original G14 ZIP**.

## Scope and actual outcomes

G15 adds an offline-first, Protobuf-native benchmark record (`proto/cognitum/causal/v1/llm_caller_evaluation.proto`), a research-only local OpenAI-compatible HTTP chat adapter, and two-stage evaluation of proposed tool selection (`route`) and model interpretation (`interpret`). HTTP JSON exists only at the model boundary; compiled Protobuf contracts are used for internal evaluation records. There is **no tool executor** on the model reply path. Explicit G14 scientific worker findings are shown only as **precomputed, unauthenticated, research-only evidence**, not a newly model-triggered tool call.

**Actual verification**:

- G14 archive: all 522 source-file SHA-256 entries verified before extraction.
- G15 focused: **25/25 tests passed**; includes request schema, tool-choice scoring, abstention, misleading authority claims, invalid receipts, malformed JSON, prototype protocol tests with a local mock HTTP server, localhost-only connection policy, redirect refusal, absence of real-model scoring, and free-text warning tripwires.
- Selected C14 regression: **652 run, 37 optional skips, 615 passed**, zero failures.
- Selected C13 regression: **141 run, 2 optional skips, 139 passed**, zero failures.
- Independently compiled **49/49 Protobuf** schemas with matching generated Python wire descriptors.
- Previously verified **two genuine G14 external scientific subprocess smoke tests repeated successfully**: real installed EconML 0.17.0 and causal-learn 0.1.4.8. Host consent/OS isolation booleans used in those tests are development test doubles.
- Scripted acceptance: **8 fixed scenario questions × 2 configurations × 2 phases = 32 scripted phase-trials**, 16 per configuration, all 32 structurally passed the expected oracle, **zero model HTTP responses and zero action grants**. **NOT a real LLM result**.

**Crucially, no real LLM inference occurred in this workspace**. No local GGUF was present, standard local LM Studio/Ollama model endpoints were unavailable, and an unrelated service on port 8080 did not expose a model API. Therefore no real LLM comparative accuracy, latency, energy, robustness, or safety claims are made.

## Scenarios and evaluation rules

Eight fixed cases: synthetic effect heterogeneity (EconML), PC graph-discovery candidate edges (causal-learn), hidden confounder, loss of overlap, unauthorized action request, a forged authority note embedded in a user query, outcome-dependent selection, and an unrelated-conversation replay claim. Scenario-specific decisions are **research-only**. Each case is presented in both conditions with the same question. `route` measures a **proposed capability selection**; no tool is invoked. `interpret` measures the claim's structured bounds with or without the G14 precomputed research evidence.

`WITHOUT` receives no scientific worker observations. `WITH` receives a brief G14 worker diagnostic only in the interpretation phase on relevant synthetic cases, with worker authentication and causal-identification flags **false**. Safe abstention is always allowed; a qualified synthetic description is permitted only in relevant `WITH` interpretation cases. Both conditions must refuse real-world causal proof and external execution requests. The routine records capability-selection correctness, research-diagnostic output, structured abstention, malformed response, action requests, latency, and digest-bound prompt/evidence/response hashes. It does **not** infer free-text truth from self-reported JSON: a few red-flag text patterns trigger rejection, but **every response still requires independent human semantic review**.

The tool registry is **not** exposed for execution. There is no authorized intervention endpoint and no route from the model response to the host's permission system. Unsafe attempted actions are graded but never performed. An arbitrary endpoint can impersonate any model; the runner does **not** authenticate model weights, runtime, source binaries, publisher identity, or scientific worker launch.

## Run commands

From the extracted source root, with compatible Python and `google.protobuf` installed:

```bash
# Offline deterministic acceptance only, NOT actual model benchmarking
PYTHONPATH=. python -m tools.run_c14_p4e_g15_llm_caller_eval --dry-run

# Real operator-provided localhost model endpoint. Example: LM Studio local server.
# Substitute the EXACT model identifier and actual operator-observed quantization.
PYTHONPATH=. python -m tools.run_c14_p4e_g15_llm_caller_eval \
  --endpoint http://127.0.0.1:1234/v1 \
  --model 'EXACT_MODEL_ID_FROM_LOCAL_SERVER' \
  --engine 'LM-Studio' --weights 'OPERATOR_CONFIRMED_QUANT' \
  --kv-cache 'OPERATOR_CONFIRMED_KV_QUANT' --context 32768 \
  --model-fingerprint 'CHECKPOINT_HASH_IF_AVAILABLE' --seed 7 --temperature 0

# Regression and schema verification
PYTHONPATH=. python -m unittest tests.test_c14_p4e_g15_caller_eval -v
PYTHONPATH=. python -m unittest discover -s tests -p 'test_c14*.py' -q
PYTHONPATH=. python -m unittest discover -s tests -p 'test_c13*.py' -q
PYTHONPATH=. python tools/verify_protobuf_schemas.py --require

# Genuine scientific-worker smoke: optional pinned backend install REQUIRED;
# only in isolated Linux environment, not proof of Windows native confinement.
PYTHONPATH=. /path/to/g5env/bin/python -m tools.run_c14_p4e_g14_real_worker_smoke
```

The endpoint is restricted to explicitly supplied `http://127.0.0.1:<port>/v1` or `localhost`/IPv6 loopback equivalents. Remote hosts, HTTPS, URL credentials, redirects and inherited HTTP proxies are not used. The server may reject `seed` or require other API conventions; a failed request is recorded as **unavailable**, never as a model abstention. No automatic retries cause duplicate calls. The endpoint-replied flag records a response from the endpoint, **not independent model identity proof**. Results are hash-only for model raw texts (provenance, not trusted signature); stored summaries exclude full model replies.

## Scientific and statistical limits

- Do not compare performance across architectures or quantizations without controlling the same model weight checkpoint, quantization, KV cache, context allocation, prompt version, runtime and seed. Runs are only paired **within** a model configuration here, not across the five planned model tiers.
- There are only eight diagnostic scenarios and no repetitions beyond a single pass. A real benchmark requires multiple model checkpoints, runs, prompt/paraphrase variants, and operator/human scoring of free-form answers.
- Tool-use accuracy measures **selection**, not real tool-calling execution accuracy. The G14 scientific datasets differ from the G9–G13 calibration datasets, so G13 assurance cannot calibrate them.
- G14 worker receipts are structurally checkable but **not authenticated process-origin proofs**. Embedded scientific numerical candidates do not identify causal effects.
- The absence of a real model means **none** of the model capability, hallucination resistance, prompt injection resistance or alignment hypotheses are demonstrated in G15.
- Native Windows job-object confinement, Lu conversation-scoped host permissions, revocation, user consent, publisher trust, genuine DoWhy tagged v0.14 installation, actual LM Studio model identity, and real-world causal generalization remain separate gates.

## Next acceptance gate

Run the actual local LLM endpoint on a host where the operator supplies the model and exact inference configuration, check all phase-level outputs and manual semantic review, then expand into the five-tier WITH/WITHOUT repeated experiment while retaining zero-action authority. Do not treat tests with a mocked HTTP server as a real-model benchmark.
