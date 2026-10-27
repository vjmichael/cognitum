# C03 / P1–P2 — Lu+Model Benchmark Plan and Host-Capture Contracts

**Scope:** Cognitum only; Lu and its loaded transformer remain read-only and uninvoked.  
**Status:** Implemented **versioned Protobuf configuration and untrusted capture-shape validation**, not a running host benchmark or P3 performance result.  
**Prerequisites:** [C03 component smoke](P1-P2-protobuf-component-smoke.md), [C03 methodology](P0-research.md), Lu native CE/ModelToolCatalog integration C04 and the **still-blocked C02 OS worker gate**.

## Contract surfaces

[**`proto/cognitum/benchmark/v1/benchmark.proto`**](../../../proto/cognitum/benchmark/v1/benchmark.proto) defines a distinct `cognitum.benchmark.v1` domain so it cannot accidentally promote the existing `cognitum.eval.v1` component smoke report to an end-to-end model benchmark.

| Message | Contents | Security and provenance limit |
|---|---|---|
| `BenchmarkPlan` | Lu build SHA-256, **the exact selected model artifact hash**, backend, quantization, hardware/platform ID, host policy hash, context hash, dataset and grader revision hashes, fixed sampling settings, seed, tool budget, repeats, each arm's catalog and comparator, case SHA-256 references and **all scheduled trials** | Host/model/corpus metadata is **declared by the caller**, not authenticated by Protobuf. No raw user prompts or access grants |
| `ArmConfiguration` | A: host only, B: conventional library/tool, C: one Cognitum tool, D: bounded composition (at least two Cognitum tools), per-arm available/blocked reason and tool-catalog hash | Must not contaminate A/B with Cognitum; **HOST_APPROVED_RUNNABLE is a declaration, not a real host approval or permission** |
| `ScheduledTrial` | Exact case, arm, repetition and matched seed, counterbalanced by rotating arm order across cases/repeats | A schedule is a plan, not an execution record |
| `TrialCapture` | Outcome status (not run/completed/abstained/tool-selection/arguments/tool-execution/denied/timeout/provider error), separate tool-use judgment, separate final-answer grade, sanitized error code, optional answer hash and resource observation | Cannot prove truthful grading or tool use; no model text/prompt/credentials |
| `ResourceObservation` | **Optional presence-aware** total and first-token latency in milliseconds, peak host RAM/GPU memory in bytes, energy in millijoules, input/output tokens, attempted/rejected tool calls, optional USD micro-cost | Missing measurement stays **absent**. A **present zero** is distinct and does not mean unmeasured |
| `BenchmarkCapture` | Plan SHA-256, capture/collector IDs, collector build hash and a row for **every scheduled trial**, explicitly `NOT_RUN` where not observed | Host identity and actual measurements still require independently trusted Lu provenance; any promotion claim is rejected |

C03 does **not** invent latency/VRAM/energy values to fill empty cells. `model_context_sha256` is a nonsecret committed context reference; the trusted Lu host must maintain the actual model-policy/tokenization/task context and dataset locally under appropriate retention rules. Neither datasets nor raw model answers are stored by this schema.

## Comparable benchmark design

Every A/B/C/D comparison uses a **single declared** Lu build, selected model hash, backend, quantization, sampling settings, context, hardware profile, host policy and task split. Tool catalogs may differ *only* as explicitly fixed arm configurations and comparator variants; the conventional alternative must have its own pinned version/build and catalog. The B conventional baseline is not interchangeable with a disabled-tool straw man. D composition must contain at least two Cognitum specialist tools and meaningful ablations must be pre-registered separately when those capabilities exist.

The plan's schedule is deterministic and complete across all case × repetition × arm combinations; the same seed is reused across all four arms for each case/repetition. Assignment order rotates (A/B/C/D, B/C/D/A, etc.) to reduce arm-order confounding. This does not itself guarantee stochastic determinism or eliminate cache/hardware confounders. Maximum 32 task references × 8 repetitions × 4 arms, with a 64 KiB plan size limit and 512 KiB capture size limit. Capped tool advertisements at 16. Unknown message fields, duplicate wire tags, changed case IDs/seeds/order, missing cases, catalog mismatches and additional unplanned trials fail closed.

An **unrunnable arm** has an explicit cause such as `security_gate_blocked`, `lu_ce_bridge_missing`, `tool_call_unsupported` or `baseline_unavailable`; it must report only `NOT_RUN`. If an arm is declared runnable by a trusted future host, the format can carry results, but this local validator **does not confirm that host approval happened**.

## Scoring boundaries

Keep these metrics distinct:

- **Final task outcome:** `CORRECT`, `INCORRECT`, `APPROPRIATE_ABSTENTION`, `INAPPROPRIATE_ABSTENTION` or `NOT_GRADED`. A host-owned rubric/grader revision hash is pinned, but true grade independence remains to be established.
- **Tool choice:** `APPROPRIATE`, `UNNECESSARY_CALL`, `MISSED_REQUIRED_CALL`, `INCORRECT_CAPABILITY`, or `NOT_ASSESSED`. This differs from syntactically valid arguments and from execution success.
- **Failures:** separate status for tool not selected, invalid arguments, execution failure, host denial, timeout, provider failure, and `NOT_RUN`. Failure returns sanitized, allowlisted category, no graded result/answer. An explicit abstention is not a timeout or failure.
- **Resource cost:** optional measured time, first token, RAM, VRAM, energy, tokens, attempted/rejected calls and financial cost, with internally consistent comparisons (e.g. TTFT ≤ end-to-end latency).

Any plan/control mismatch or unobserved arm is reported without filling missing cells or inventing a win/loss figure. Capture summaries must exclude `NOT_RUN` from denominators and explicitly disclose coverage; no pooled efficacy claim is valid across unmatched arms.

## Integrity verification versus actual experiment

[`cognitum/benchmark_capture.py`](../../../cognitum/benchmark_capture.py) implements exact bounded binary Protobuf serialization, rejection of unknown/noncanonical fields, paired schedule validation, resource presence and failure/grade consistency. `empty_capture_template(plan)` creates only **all-`NOT_RUN`** rows. `CaptureShapeReview(format_valid=True, model_execution_authenticated=False, paired_effect_verified=False, promotion_evidence=False)` is intentional—even when example/test records say `COMPLETED`.

**A SHA-256 value supplied by a caller is not proof that a model checkpoint, task, grader, or OS reading exists.** Neither a Protobuf frame, matching configuration, nor illustrative unit-test `CORRECT` grade constitutes actual model benchmarking. Cognitum has not attached to Lu, generated model outputs or run a conventional-tool baseline. C02 sandbox admission remains unconditionally denied.

Before actual P3, the separate Lu team must approve a **read-only/sanitized trusted capture adapter** that supplies correct model and build hashes, event boundaries, token counters and OS resource measures, uses host-owned permissions and session context, and can authenticate the collector. Then independently freeze a representative real task set and rubric **before** running matched A/B/C/D trials with honest unavailable-arm reporting. Confidence intervals, variation by repetition/model/hardware, conventional comparator version and costs must be computed from genuine observations.

### Test gates

[**`tests/test_benchmark_capture.py`**](../../../tests/test_benchmark_capture.py) contains offline fixtures with **intentionally fake SHA strings and illustrative grade/resource records**. It tests four-arm comparability, schedule/seed rotation, no experimental contamination of baseline arms, version/fingerprint checking, metric presence (including zero versus absent), distinct failures and abstentions, missing/mismatched trial rejection, resource arithmetic, raw-data/promotion rejection and no C02 launch bypass. These **test-only mocked captures are not performance observations**.

CI compiles the **sixth** native Protobuf schema against descriptor-backed Python bindings and runs all earlier C01/C02/C03 tests plus 12-case replay and the previous 10-case calculator component smoke on Windows/Linux Python 3.11/3.13.

## Remaining Lu handoff (proposed)

Cognitum's [Lu addendum register](../../lu-dlc-ce-addenda.md) tracks **LU-CE-010**: a trusted Lu host telemetry bridge (model version/hash, model tool-call reliability, prompts/tasks as consented opaque hashes, grader provenance, time/resource measurement scopes and session-bound event IDs), OS-level worker restrictions, and non-invasive export of safe Protobuf records. The host—not the model or a generated document—must decide which tools were actually enabled, which calls occurred, which answer was graded and which measurements are reliable.
