# C03 / P0 — Evaluation, Replay and Lu+Transformer Augmentation Benchmarks

**Date:** 2026-10-26  
**Status:** **P0 in progress** — research, baseline/measurement architecture and data-governance design begun; exact tasks, frozen thresholds, host telemetry adapter and P0 exit review remain open.  
**Owner:** Cognitum. **Lu is read-only**; host-requested changes are **proposals**, tracked in [the DLC CE addendum register](../../lu-dlc-ce-addenda.md).  
**Governing requirements:** [Per-component P0–P3 roadmap](../../roadmap.md) · [Lu/Cognitum collaboration](../../lu-cognitum-integration.md) · [Build order](../../build-order.md)

## 1. Central scientific question

**Does a Cognitum capability measurably help the exact transformer chosen/loaded in Lu complete a real task, compared both with that same Lu+model configuration without Cognitum and with strong conventional libraries/tools?**

Isolated algorithm speed, reduced RAM or a good synthetic accuracy figure is **not** evidence that the host transformer makes better end-user decisions. C03 must measure **both** (a) component correctness/performance/security and (b) end-to-end task quality, routing reliability, latency and resource cost. A negative result is legitimate; no experiment is forced to justify production promotion.

## 2. Existing Cognitum baseline reviewed

- [`cognitum/evaluation.py`](../../../cognitum/evaluation.py): frozen synthetic fixture replay with deterministic no-effect host context, duplicate case rejection, per-case status/result comparison, suite and registry digests, and **`promotion_evidence=false`**.
- [`evals/smoke.json`](../../../evals/smoke.json): the synthetic smoke-suite input. The repository's archived handoff reports **12/12** case passes and **31** unit methods on its original Windows environment. These are engineering checks, not live model comparisons.
- [`cognitum/tracing.py`](../../../cognitum/tracing.py): metadata-only JSONL trace sink in main; a **separate, not-yet-merged** [trace allowlist hardening branch](https://github.com/vjmichael/cognitum/blob/cognitum/c01-tracing-guard/docs/components/core-runtime/P1-P2-tracing-hardening.md) passed 9/9 independent focused Linux tests. Its full repo regression remains pending.
- [`tests/test_core.py`](../../../tests/test_core.py), [`tests/test_calculator.py`](../../../tests/test_calculator.py): current baseline tests for contracts, trust, worker, exact arithmetic and replay.

**Explicit gap:** there is no real Lu/selected-transformer benchmark adapter, no representative held-out corpus frozen for these new component claims, and no measured improvement over conventional tools.

## 3. Maintained library and standards review (initial)

| Candidate | Official source | Evaluation fit and decision |
|---|---|---|
| **Inspect AI** | https://inspect.aisi.org.uk/ | Broad evaluation framework with composable dataset/agent/tool/scorer primitives and agentic tool tasks. **Assess as an optional research harness**, not a mandatory Lu runtime dependency. Require consent/privacy checks on logs and external backends |
| **EleutherAI LM Evaluation Harness** | https://github.com/EleutherAI/lm-evaluation-harness and https://lm-evaluation-harness.readthedocs.io/ | Established standard academic tasks and model backends; useful for **model-only control and model-quality context**, but not automatically a matched comparison of the Lu desktop's tools, memory and orchestration |
| **OpenTelemetry GenAI semantic conventions** | https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/ and https://github.com/open-telemetry/semantic-conventions-genai | Useful names and structure for execution/retrieval/agent/tool spans. Propose **local, consent-aware import/export only**. No default collector, external telemetry or raw-prompt logging |
| **Python stdlib unittest/json/hashlib/statistics** | https://docs.python.org/3/library/unittest.html | Retain for deterministic core smoke and reproducible report fixtures; zero extra Cogntium runtime dependencies for C03 initial stage |
| **SQLite / FTS5 lexical retrieval baseline** | https://www.sqlite.org/fts5.html | Competent conventional comparison for C06/C08 context retrieval; index-build/deletion cost must be counted |
| **TorchHD library baseline** | https://torchhd.readthedocs.io/ | Candidate conventional HDC implementation control in research; not a drop-in Lu memory database or a user authorization system |

**P0 library posture:** prefer a small export/import adapter and deterministic scorers inside Cognitum, while evaluating Inspect/LM Eval Harness for reusable task suites. No new production dependency or Lu tool/IPC change is selected by this survey.

## 4. Four comparison arms to pre-register

| Arm | Execution | Meaning |
|---|---|---|
| **A — Host alone** | Same Lu, selected model, settings, context and normal host tools, **without the experimental Cognitum capability** | Measures baseline transformer+host ability |
| **B — Conventional tool** | Same Lu/model with a maintained competent established library/service for the same capability | Tests whether Cognitum improves on the practical alternative, not a straw-man |
| **C — Cognitum candidate** | Same Lu/model with the one enabled candidate Cognitum CE component | Measures marginal task benefit or regression and routing overhead |
| **D — Cognitum composition** | Same Lu/model with the exact proposed bounded combination, with meaningful single-component ablations | Tests whether HDC+state+planning/etc interactions create a real benefit |

If an arm is impossible due to unavailable Lu CE support, model tool-call limitation or license, **mark not runnable**. Do not fabricate results or compare a different model as if it were controlled. Preserve no-CE, default-off and denied/unavailable observations.

## 5. Initial task suite design (not yet frozen)

1. **C05 exact calculator:** user arithmetic word tasks and unambiguous formal inputs; score exact rational output, units, question formalization, abstention on unsupported syntax and whether tools were chosen correctly.
2. **C06/C07 retrieval and belief revision:** multi-turn revisions, contradictions, deleted claims, old versus current decisions and cross-workspace denial. Score temporal correctness, provenance accuracy, false recall, leakage and clean abstention.
3. **C08 HDC candidate index:** multi-hop relational and retrieval/update/delete cases; matched SQLite FTS5/BM25, dense/binarized embedding+rerank and exact lookup controls. Score recall@k, MRR/nDCG, index build/update memory and *transformer final-answer correctness*.
4. **C09 KAN numeric specialist:** held-out/OOD numerical function prediction against matched MLP and conventional approximation; calibration/fallback; model tool invocation accuracy and task outcome, with CPU/GPU profiling when available.
5. **C10–C12 proof/optimization/planning:** formally checkable constraints, violations, solution quality/bound gap, unsat/unknown distinction, resource/time limits and host answer honesty.
6. **C13–C19 advanced specialists:** create only when a real task/strong control is defined; avoid bulk toy benchmarks or automatic claims of world-level cognitive improvement.

Use synthetic **smoke** suites for negative and boundary cases and separate representative **held-out P3** samples for scientific claims. Pre-register case counts, prompts, seeds, leakage exclusions, challenge sets, human grading protocol (if any), labels and thresholds **before** running an efficacy benchmark. For small samples, show intervals/uncertainty and avoid generalization.

## 6. Common trace and result provenance contract (design only)

A proposed local report record may contain these **nonsecret** fields, subject to retention review:

- Run metadata: `schema_version`, random `run_id`, `case_id`, `arm`, benchmark source/version/hash, task group and preregistered scorer revision.
- Host and model: Lu commit/build, platform, user-approved backend identifier, model family/version/quantization/context, prompts/system-policy hash **only when consented and non-revealing**, sampling/seed and token budget. Do not confuse an approximate vendor model label with a pinned checkpoint.
- Component: CE ID/version, operation/protobuf contract version, enabled capability set, exact environment/library versions, CPU/GPU selection, registry snapshot hash and security-policy revision.
- Outcomes: tool selection validity, rejected/denied calls, invalid JSON/Proto, errors/timeouts, confidence/assumptions, verifier result, correctness rubric, latency p50/p95, throughput, RAM/VRAM, worker and serialization overhead, energy/financial cost where genuinely measured.
- Provenance: source entry/revision identifiers, derived-index revision and scorer result; clearly label unverified model outputs and generated explanations. Do **not** default-store raw user messages, prompts, credentials, private document contents or unconstrained tool outputs.
- Reproducibility: immutable config and task hashes, independent controlled baseline records, and limitations. Mark a run **`synthetic_smoke`**, **`component_benchmark`** or **`lu_model_e2e`** explicitly.

Lu is authoritative for session/model/tool-execution provenance. Cognitum should accept **user-approved, sanitized exports or a future trusted host event adapter**, not attach itself to the desktop process, secretly scrape chats or start model inference independently. This host request is tracked as **LU-CE-010**, not implemented here.

## 7. Evaluation integrity and safety gates

- **100% critical negative gate** for permission escalation/cross-profile disclosure/deletion revival, schema version rejection and invented exact results, on an agreed frozen suite. This is a safety requirement, not a claimed achieved rate.
- For efficacy, require a **predeclared task-specific practical effect size and uncertainty bound**, no critical safety/reliability regression and comparison with the conventional control. No universal minimum percent or fictitious win-rate target before baseline characterization.
- Model settings, prompts, tool budgets, hardware/backend and run order must be balanced; if not comparable, document the confound.
- No private prompts or raw task data exported to third-party evaluation services by default; dataset licensing, consent, train/test split and retention/deletion rules apply.
- A model can refuse tools, lack tool calling or hallucinate a tool result. Record **tool-selection error, argument-validity error and tool-execution error separately**; do not treat syntax-correct JSON as a correct decision.
- P3 promotion requires transparent wins/ties/losses and measured overhead. Baselines must be nontrivial and logs reproducible; testing on Lu's real AMD Radeon AI PRO R9700 is future hardware work, not a current result.

## 8. Next P0 activities and blockers

- [x] Inspect existing Cognitum replay/tracing shape and inherited test provenance.
- [x] Review Inspect AI, LM Evaluation Harness, OpenTelemetry and standard retrieval/HDC baseline sources at the planning level.
- [x] Define four augmentation arms, data-handling rules and needed tool-selection/error categories.
- [ ] Select 1–2 representative *user-approved* real Lu tasks and concrete loaded-model configuration; freeze paired cases and scores before testing.
- [ ] Choose whether Inspect/LM Eval Harness should wrap an offline Lu event adapter or whether Cognitum needs only a small native scorer; pin version/license/dependency after a minimal compatibility spike.
- [ ] Define exact host event export contract with Lu team **via the addendum register**, not by editing Lu.
- [ ] Implement static, synthetic offline scorer fixtures in Cognitum, then run P1/P2 validation; do not claim results for a transformer not actually loaded and evaluated.
- [ ] Run fully matched P3 A/B/C/D only after C04 CE bridge and trusted Lu host telemetry exist.

**Current result:** C03 **P0 started**, no end-to-end model benchmark carried out or new benchmark scores fabricated.
