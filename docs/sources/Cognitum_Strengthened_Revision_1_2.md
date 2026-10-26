# Cognitum — LLM Augmentation Architecture

**Revision 1.2 (review revision)**
**Based on:** Strengthened Revision 1.1 (2026-10-26)
**Status:** Design review + restructure. No module code changed.
**Creator:** Michael Vang
**Review note:** External tool and benchmark statements in this revision come from Oct 2026 searches. Re-check versions before depending on them.

> Cognitum is a cognitive augmentation system for large language models built from optional, disable-able plugins. The system must remain correct and useful with any subset of plugins present, including none.
> **Added in 1.2:** when a plugin that guards an exactness-critical answer is missing or fails, Cognitum says so. It does not guess.

---

## 0. What changed in this revision (read first)

1. **Review added (Section 2):** pros, cons, and a module-by-module check against existing standard tools.
2. **Two tracks.** Most of the 12 modules are *adapters* that wrap mature tools (Z3, OR-Tools, SymPy, pgmpy, DoWhy). A few are genuine *research* bets (HDC, KAN, capsules, SSM-style state). Different rules for each.
3. **Champion/challenger slots.** Every capability slot (for example `memory.recall`) gets a boring baseline plugin first. Research plugins compete against it in the same slot. This is what makes "measurement before promotion" executable.
4. **Evaluation moved into Tier 0** (Section 10), with named baselines, a one-page pre-registration template, and a claims ledger.
5. **Contract tightened** (Section 6): per-operation schemas, solver-style statuses, assumptions and provenance fields, side-effect declaration.
6. **Fallback rules split** by whether the answer is exactness-critical (Section 8).
7. **Security section added** (Section 11).
8. **Failure-class table corrected** where the technology did not match the failure it was assigned to.
9. User changed title to better reflect this project. It augments instead of being itself a self contained Hybrid AI.

---

## 1. Executive Summary

The LLM is the orchestrator and natural-language interface. Specialized modules handle well-documented LLM failure classes: exact memory, arithmetic, long-term state, spatial reasoning, planning, causality, uncertainty, physics, formal verification, optimization, adaptation, topology.

Rev 1.1 said "three solid, well-measured modules beat twelve shallow ones," then kept all twelve in the headline. Rev 1.2 acts on that sentence:

- **Cognitum v1 = Core + three baseline plugins** (exact calculator/code sandbox, exact memory store with search, typed state store) **+ the evaluation harness.**
- **Research plugins** (HDC, KAN, capsules, SSM-style ideas) enter as *challengers* against those baselines.
- **The other adapter modules** are built on demand, one at a time, when a real task needs them.
- The full 12-module vision stays on the page. It is a backlog with an owner-controlled order, not a delivery commitment.

**Integration pattern (every module):**

```
User request
    │
    ▼
┌─────────────┐
│    LLM      │  1. Parse intent, identify sub-problem type
│ (Interface) │  2. Choose a capability slot (via native tool calling)
└──────┬──────┘  3. Formulate the sub-problem in that slot's input schema
       │
       ▼
┌─────────────┐
│ Policy guard│  Validates input against schema; checks enable flags,
│  (Core)     │  tool budget, permissions; logs a trace event
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Module X   │  Stateless request handler. State lives in its own store.
│ (Plugin)    │  Never calls other modules.
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Policy guard│  Validates output; attaches status, exactness, assumptions,
│  (Core)     │  evidence; applies fallback rules if the call failed
└──────┬──────┘
       │
       ▼
┌─────────────┐
│    LLM      │  4. Interpret and synthesize
│ (Synthesis) │  5. Disclose modules used / skipped / unverified claims
└─────────────┘
```

---

## 2. Review of Rev 1.1

### 2.1 Verdict

Rev 1.1 is a strong *process* document and a thin *technical* document. It is good at "how to stay disciplined" and weak at "what exactly is each module, and what does it beat." The risk analysis is the best part. The biggest gaps are: it rebuilds infrastructure that standard protocols already provide, it names no baselines even though its central rule is measurement, and several modules are paired with failures they do not address.

### 2.2 Pros (keep these)

| # | Strength | Why it matters |
|---|----------|----------------|
| P1 | **Honest risk section.** Names routing, drift, observability, resource, discipline, over-reliance on AI codegen, and false completeness. | Rare in design docs, and the risks are the right ones. |
| P2 | **Radical optionality + pure-LLM fallback.** | Gives you an ablation baseline for free and keeps the system bootable. |
| P3 | **Measurement before promotion.** | The single most valuable rule in the document. Without it twelve modules rot into prototypes. |
| P4 | **Exact stores are truth; approximate indexes are derived.** | Matches the HDC handoff conclusion (SQLite canonical, HDC optional derived index). Same pattern vector databases use. |
| P5 | **Core/plugin split with a right-sized core.** | Registry, router, session, trace, fallback is the correct minimum. |
| P6 | **Contract basics:** IDs, status, latency, version, health, resource budget, isolated self-test. | A sound skeleton to tighten. |
| P7 | **Tiering by expected ROI; any build order allowed as an experiment.** | Keeps exploration cheap while keeping promotion strict. |
| P8 | **Contract written to be handed to an implementation model.** | Practical for local-model-assisted development. |

### 2.3 Cons (fix these)

Severity: **H** = changes the plan, **M** = changes a section, **L** = polish.

| # | Sev | Problem | Fix in 1.2 |
|---|-----|---------|-----------|
| C1 | H | **Reinvents existing standards.** A capability registry, versioned tool schemas, health, and discovery are what MCP already specifies (current revision 2026-07-28, with version negotiation and server discovery). Tracing is covered by OpenTelemetry's GenAI conventions. Tier 0 as written is a large custom build before any module runs. | One canonical schema, thin façade for MCP clients, JSON-lines trace log shaped for OpenTelemetry. Rely on the host LLM's native tool calling instead of building a rules-engine router (Sections 7, 8). |
| C2 | H | **Failure-class table mismatches technology.** KAN assigned to arithmetic, MAML to domain adaptation, Neural ODEs to physical intuition, SSM to conversation consistency, HDC to hallucination and retrieval. In most rows the right fix is an existing exact tool, and the interesting technology is a challenger, not the fix. | Corrected table (2.4) and two-track structure (Section 12). |
| C3 | H | **No baselines named.** "Measure end-to-end benefit" has no control arm. A module that beats the raw LLM but not *LLM + the standard tool* has not earned a slot. | Champion/challenger slots; two controls per slot (Section 10). |
| C4 | H | **Evaluation is deferred** to "Next Actions #3" although it is the central gate. | Evaluation harness is Tier 0 (Sections 5, 10). |
| C5 | M | **"Strict contract" has an untyped envelope.** `payload` and `result` are `dict[str, Any]`, so strictness is aspirational. The status enum cannot express solver outcomes (unknown, infeasible, partial). `confidence` is undefined. No provenance, assumptions, side-effect declaration, idempotency, or cancellation. `correlation_id` is optional. Default timeout of 5 s is wrong for anytime and solver workloads. | Section 6. |
| C6 | M | **Router under-specified, tool-count ignored.** Twelve modules times several operations is dozens of tools. Small local models already skip tools unless reminded when the tool list is long (an existing local toolkit of roughly 80 tools shows this). More tools make it worse. | Tool budget, family entry points, deterministic policy guard (Section 8). |
| C7 | M | **Fallback semantics wrong for exact classes.** "Honest fallback to pure LLM" for arithmetic or verification recreates the exact failure Cognitum exists to prevent. | Fallback matrix (Section 8). |
| C8 | M | **Optionality testing does not scale.** Random subsets of 12 modules is 4,096 configurations. "When modules are chained" also contradicts independence. | No module-to-module calls; structured test matrix of about 40 configs (Section 9). |
| C9 | M | **No threat model.** Several modules execute code or solver input derived from LLM text. Retrieved memory and tool output re-enter the prompt. Memory writes can poison the exact store. | Section 11. |
| C10 | M | **Formalization risk missing.** SMT, planners, optimizers and causal tools are exact on their *formal input*. The LLM's natural-language-to-formal translation is where errors enter. | `assumptions` and `formalization_echo` fields; mandatory echo step (Sections 6, 12). |
| C11 | M | **Scope bleed and no non-goals.** Model-internal ideas (SSM layers, KAN layers, capsules inside the network) sit in the same document as external plugins. They are different projects with different test rigs. | Non-goals (Section 4); SSM and capsule rows split by scope (2.4). |
| C12 | L | **Document is not self-contained on evidence.** It says HDC "succeeded" without recording what is validated, and the HDC row claims retrieval benefits that the pilot results do not support. | Claims ledger (Section 10.5). |
| C13 | L | **Owner is the bottleneck (R6), but there is no mechanism.** No WIP limit, time-boxes, or kill rules. | Section 13. |

### 2.4 Module-by-module check

| Module | Rev 1.1 pairing | Problem | Rev 1.2 role. Standard tools to wrap or beat |
|--------|-----------------|---------|----------------------------------------------|
| **HDC** | Hallucination, unreliable retrieval, no online learning | Retrieval was not HDC's win in the B1 pilot: on scifact nDCG@10, dense 0.718, binarized-plus-rescore 0.717, BM25 0.646, best HDC word pipeline 0.520. Retrieval alone also does not stop hallucination; grounding plus citation checking does. | **Research challenger** for `memory.relate` and `memory.index`: binding, relational composition, noise tolerance, continual update, as a *derived index over SQLite*. Baseline to beat: SQLite FTS5/BM25 + binarized embeddings with float rescore (sqlite-vec or FAISS). Library: TorchHD. Agent-memory layers for comparison: Mem0, Zep/Graphiti, Letta, Cognee. |
| **KAN** | Arithmetic errors, numerical approximation, function fitting | Exact arithmetic is not a function-fitting problem. Fair-comparison studies find KAN beats MLP mainly on symbolic-formula fitting, and that edge traces largely to the B-spline activation. | **Split.** (a) `calc.*` adapter, exact: Python/NumPy/SciPy, SymPy, mpmath, `fractions`/`decimal`. (b) `fit.symbolic` research challenger vs PySR (symbolic regression) and an MLP with B-spline activations. Reference implementation: pykan. |
| **SSM** | Inconsistency in long conversations, no state tracking | A state-space model is a sequence architecture, not a drop-in tracker. 1.1 defines no input/output for it. Conversation consistency is mostly an explicit-state problem. | **Adapter:** `state.*` typed, versioned, event-sourced store (SQLite). **Research:** SSM/Mamba-style layers belong to the model-architecture project (Zog Zoo), not to Cognitum, unless a concrete I/O is specified (Open Question 1). |
| **Capsules** | Spatial/3D errors, no object permanence | Capsule networks have not reached mainstream adoption. The failure class is better served by explicit scene representation. | **Adapter:** `space.*` over geometry and scene graphs: shapely, trimesh, scipy.spatial, networkx; PyBullet/MuJoCo for object permanence and contact. **Research:** capsule or object-file model only after the adapter exists to beat. |
| **MCTS + DP** | No multi-step planning, no backtracking | MCTS is one search algorithm; the right one depends on problem structure. The hard part is formalizing the problem. | **Adapter:** `plan.*`. LLM writes the formal spec (PDDL or state-transition), classical planner searches, verifier checks the plan. Tools: Fast Downward or pyperplan, OR-Tools, mctx (JAX MCTS) where MCTS is truly needed. |
| **Causal models** | Correlation/causation confusion | Needs a DAG and data. The LLM can propose assumptions; identification and estimation are statistical. | **Adapter:** `causal.*`. Tools: DoWhy, EconML, causal-learn. Output must list assumptions and an identifiability check before any estimate. |
| **Bayesian networks** | Uncalibrated uncertainty, base-rate neglect | Most chat cases need a closed-form Bayes update, not a network. | **Adapter:** `prob.*`, start with `bayes_update`. Tools: scipy.stats, pgmpy, PyMC, NumPyro, Stan. Cheap Tier 2. |
| **Neural ODEs / physics** | No physical intuition, no trajectories | A neural ODE *learns* dynamics from data. Simulating known physics needs a solver or simulator. | **Adapter:** `sim.*` using SciPy `solve_ivp`, Pint (units), PyBullet/MuJoCo/Brax. torchdiffeq or diffrax only if learning dynamics from data is a real task. |
| **SMT / provers** | Cannot formally verify claims | The guarantee covers the formal model, not the English claim. Results are sat / unsat / unknown, not pass/fail. | **Adapter:** `verify.*` with mandatory formalization echo and tri-state result. Tools: Z3, cvc5; Lean 4 for proofs; CrossHair or Dafny for code. |
| **Combinatorial optimizers** | NP-hard problems, no optimality proof | Solvers return feasible-with-gap, optimal, infeasible, or unknown. | **Adapter:** `optimize.*`. Tools: OR-Tools CP-SAT, HiGHS (`scipy.optimize.milp` or highspy), PuLP. Report status and gap. |
| **Meta-learning (MAML)** | No domain adaptation | For LLMs, adaptation is done with LoRA/QLoRA adapters, RAG, and in-context examples. MAML is impractical at LLM scale and is not an inference-time plugin. | **Replace** with an adapter manager (load a domain LoRA at runtime in runtimes that support it) or park. learn2learn only for small-model experiments. |
| **TDA** | No topological reasoning | Niche; no common LLM failure class behind it. | **Park.** Build as a data-analysis adapter when a real task needs it. Tools: GUDHI, ripser, giotto-tda. |

---

## 3. Risks

Rev 1.1 risks R1–R7 stand: integration and routing complexity, interface drift, observability burden, resource and energy reality, discipline dilution, over-reliance on "the AI will implement it," and false sense of completeness.

New in 1.2:

- **R8. Tool overload.** Too many exposed tools degrade selection accuracy, especially for small local models. Mitigation in Section 8.
- **R9. Exact engine, inexact input.** Solvers can be right about the wrong problem. Mitigation: formalization echo, assumptions list, known-instance tests.
- **R10. Silent degradation.** The LLM answers an exactness-critical question itself when a module is off and nobody is told. Mitigation: fallback matrix and mandatory disclosure.
- **R11. Evaluation debt.** Tests are costly to run; the owner gets tired and promotes on feel. Mitigation: bounded, reusable harness, one-page pre-registration, kill rules (Sections 10, 13).
- **R12. Memory poisoning.** Model-originated or retrieved text becomes "fact." Mitigation: provenance on every write, quarantine for model-originated facts (Section 11).

---

## 4. Design Principles (revised)

1. The LLM is the orchestrator and interface, never the sole computer for exact or structured work.
2. **Radical optionality.** Any plugin can be disabled or deleted. The core still works.
3. **Adapters before inventions.** If a mature tool already does the job, wrap it. Build novel components only as challengers against a working baseline.
4. **Champion/challenger slots.** One capability slot, one champion, any number of challengers. Promotion is by measured result.
5. **One canonical schema.** Everything else (Pydantic models, JSON Schema for tool calling, MCP façade) is generated from it.
6. **Modules are stateless request handlers that never call other modules.** Composition happens only in the core's plan layer.
7. **Exact stores are truth; approximate indexes are derived.** Model-originated content never enters the exact store without provenance.
8. **Exactness-critical answers never degrade silently.**
9. **Every claim is tagged validated, negative, or open** in the claims ledger.
10. **Local-first runtime.** No cloud dependency at inference time.
11. Observability on every call; the trace log is also the source of evaluation tasks.

**Non-goals:** training or modifying the base LLM; multi-user or multi-tenant operation; being a general agent framework; chasing public leaderboards.

---

## 5. Minimal Cognitum Core (Non-Optional)

- LLM interface + synthesis layer (disclosure of modules used/skipped/unverified)
- Session manager
- Event/trace log (JSON lines; correlation ID on every record)
- Module registry: manifest ingestion, schema validation, enable/disable flags, capability slots
- **Policy guard:** input/output validation, tool budget, permissions, fallback matrix
- **Evaluation harness v0:** replays logged tasks against a chosen module configuration and scores them
- Router: **native LLM tool calling** over the registry, plus the deterministic policy guard. No separate rules engine in Phase A.

Everything else is a plugin.

---

## 6. Module Contract 1.2

Canonical schema lives in one place (see Section 7). Illustration in Pydantic v2 style:

```python
from __future__ import annotations
import uuid
from enum import Enum
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field

CONTRACT_VERSION = "1.2.0"


class Status(str, Enum):
    OK = "ok"                        # finished; result valid
    PARTIAL = "partial"              # budget hit; best-so-far returned (anytime)
    UNKNOWN = "unknown"              # engine could not decide (e.g. SMT "unknown")
    INFEASIBLE = "infeasible"        # proven: no solution under stated constraints
    INVALID_INPUT = "invalid_input"  # caller error; do not retry unchanged
    TIMEOUT = "timeout"              # retryable with a larger budget
    UNAVAILABLE = "unavailable"      # disabled, unhealthy, or missing dependency
    ERROR = "error"                  # module fault


class Exactness(str, Enum):
    EXACT = "exact"          # correct by construction, given valid input
    BOUNDED = "bounded"      # approximate with a stated error or optimality gap
    HEURISTIC = "heuristic"  # no guarantee


class SideEffects(str, Enum):
    NONE = "none"
    READS_STATE = "reads_state"
    WRITES_STATE = "writes_state"
    EXTERNAL = "external"    # network, or filesystem outside the sandbox


class Budget(BaseModel):
    max_latency_ms: int = 5_000
    max_memory_mb: Optional[int] = None
    anytime_ok: bool = False         # caller accepts PARTIAL results


class OperationSpec(BaseModel):
    name: str                        # e.g. "calc.eval"
    slot: str                        # capability slot, e.g. "calc"
    input_schema: dict[str, Any]     # JSON Schema generated from a typed model
    output_schema: dict[str, Any]
    exactness: Exactness
    side_effects: SideEffects
    deterministic: bool
    idempotent: bool
    typical_latency_ms: int


class ModuleManifest(BaseModel):
    name: str
    version: str
    contract_version: str = CONTRACT_VERSION
    track: Literal["adapter", "research"]
    maturity: Literal["experimental", "candidate", "recommended", "default_on"]
    provides: list[OperationSpec]
    champion_for: Optional[str] = None    # slot this module is the baseline for
    challenges: Optional[str] = None      # module it must beat to be promoted
    needs_gpu: bool = False
    safe_to_delete: Literal[True] = True  # documented, tested property


class ModuleRequest(BaseModel):
    contract_version: str = CONTRACT_VERSION
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str                   # required; set by the core
    operation: str
    payload: dict[str, Any]               # registry validates against input_schema BEFORE dispatch
    budget: Budget = Field(default_factory=Budget)
    dry_run: bool = False                 # validate and estimate cost only


class Evidence(BaseModel):
    kind: Literal["exact_store", "derived_index", "computation", "proof", "model_output"]
    ref: str                              # row id, file+line, proof hash, ...
    note: Optional[str] = None


class ModuleError(BaseModel):
    code: str                             # stable, machine-readable
    message: str
    retryable: bool


class ModuleResponse(BaseModel):
    contract_version: str
    request_id: str
    correlation_id: str
    status: Status
    result: Optional[dict[str, Any]] = None   # registry validates against output_schema
    exactness: Exactness
    assumptions: list[str] = Field(default_factory=list)
    formalization_echo: Optional[str] = None  # plain-language restatement of the formal input
    evidence: list[Evidence] = Field(default_factory=list)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)  # only with a published calibration test, else None
    error: Optional[ModuleError] = None
    latency_ms: float
    resources: dict[str, float] = Field(default_factory=dict)  # peak_mem_mb, est_joules, ...
    module_name: str
    module_version: str
```

**Why the envelope is still generic:** `payload` and `result` stay `dict[str, Any]` at the envelope level so one transport serves every module. Strictness comes from the registry validating each against the operation's own JSON Schema *before dispatch and before the result reaches the LLM*. A schema failure is `INVALID_INPUT` or `ERROR`, never a pass-through.

**Required of every module:**

- `manifest() -> ModuleManifest`
- `handle(request) -> ModuleResponse` (stateless; state lives in the module's own store)
- `health() -> Status`
- `self_test()` runnable without the rest of the system
- Respect for a runtime enable/disable flag
- Contract conformance test: fuzz inputs from `input_schema` (for example with Hypothesis and hypothesis-jsonschema) and check every response validates
- Documentation line: "Safe to delete. System continues with reduced capability."

**Rules:**

- `confidence` is `None` unless the module ships a calibration test. An uncalibrated float invites the LLM to treat it as a probability.
- Operations with `WRITES_STATE` or `EXTERNAL` require explicit permission in the policy guard.
- Contract changes follow semantic versioning; breaking changes require a version bump and a deprecation window.

---

## 7. Interop and Transport

- **Canonical schema:** one source of truth. If Cognitum is hosted by a native-registration host that uses protobuf internally, make `.proto` canonical and run `buf breaking` in CI to catch interface drift (Rev 1.1 risk R2). Otherwise Pydantic models are canonical. Do not hand-maintain two copies.
- **JSON Schema for tool calling** is generated from the canonical models (Pydantic `model_json_schema()` or equivalent).
- **MCP façade:** a thin server that exposes the registry's family tools to any MCP client (LM Studio and others). MCP's current revision (2026-07-28) is stateless with explicit version and capability discovery, which matches the "modules are stateless handlers" rule. The façade is an adapter. Cognitum's internals do not depend on it.
- **Trace log:** JSON lines. Fields chosen to map onto OpenTelemetry GenAI span attributes later, so a self-hosted viewer (Phoenix or Langfuse OSS) can be added without re-instrumenting. Call logging is the first thing to add if the host's tool-registration layer has none.

---

## 8. Routing and Fallback

### 8.1 Phase A (implement first)

- Modules register at startup with a manifest. The registry holds the live enabled set.
- **Native tool calling does the selection.** The core exposes tool schemas; the LLM chooses.
- **Tool budget:** expose at most *N* tools per turn. Start with N = 8 and tune from measurement. Test two styles with the actual local model: a flat list of the few relevant tools, and one *family tool* per slot (`calc`, `memory`, `state`, `solve`, `prob`, `space`, `sim`) with an `op` argument. Small models may do better with fewer, simpler tools or with family tools. Measure, do not assume.
- **Policy guard (deterministic):** schema validation, permissions, enable flags, tool budget, fallback matrix.
- A small tool-selection test set is built from the trace log (Section 10).

### 8.2 Phase B (optional, later)

A learned scorer that ranks candidate modules. It can never override explicit disables, permissions, or the fallback matrix.

### 8.3 Fallback matrix

| Class | Slots | If module is missing or fails |
|-------|-------|-------------------------------|
| **Exactness-critical** | `calc`, `verify`, `optimize`, `plan` (validity) | The LLM does **not** answer the exact part from its own weights. It states that the result is unverified or declines the exact claim. It may still explain the method. |
| **Grounded-soft** | `memory`, `state`, `space`, `prob`, `causal` | LLM fallback allowed. The response must not claim retrieval, verification, or computation that did not happen. Skip is disclosed. |
| **Advisory** | `sim` hints, `tda`, adaptation | Free fallback; recorded in the trace only. |

### 8.4 Disclosure

Every final response carries a structured trailer (shown or hidden by host preference):

```
modules_used:     [name@version, ...]
modules_skipped:  [{name, reason}]
claims_unverified:[short text, ...]
```

---

## 9. Making Optionality Real

- Configuration file or runtime API controls which modules load.
- The router never assumes a module exists.
- **No module-to-module calls.** If a task needs two modules, the core's plan layer sequences them. A missing step triggers the fallback matrix for that step only.
- **Test matrix (about 40 configurations instead of 4,096):**
  - all modules on; all modules off
  - each module alone (12)
  - each module removed (12)
  - a pairwise covering array across the on/off factors (roughly ten rows; tools such as allpairspy generate these)
  - champion-to-challenger swap for every slot with a challenger
- Each plugin documents "Safe to delete" and the matrix proves it.

---

## 10. Evaluation, Promotion, and the Claims Ledger

This is Tier 0. Keep it small and reusable. The harness exists once; each module adds a task file and a pre-registration.

### 10.1 Baselines per slot (two controls each)

| Slot | Control A | Control B (standard tool) | Primary metric |
|------|-----------|---------------------------|----------------|
| `calc` | LLM alone | LLM + code interpreter (Python/SymPy) | Exact-match accuracy; tokens |
| `memory.recall` | LLM + full context or plain-file scratchpad | LLM + SQLite FTS5/BM25 + binarized embeddings with float rescore | Recall@k; end-task accuracy; RAM; latency; joules/query |
| `memory.relate` (HDC) | Same as above | SQLite recursive CTEs / graph queries | Correctness on compositional queries; noise tolerance; update cost |
| `state` | LLM + raw transcript | Typed JSON/SQLite state | Consistency errors per 100 turns |
| `fit.symbolic` (KAN) | MLP at equal FLOPs | PySR and MLP with B-spline activations | RMSE at equal FLOPs; formula recovery |
| `verify` / `optimize` / `plan` | LLM alone | LLM + solver without the echo step | Wrong-but-confident rate; solver-status correctness |

For memory, public suites such as LoCoMo and LongMemEval are useful as *harnesses*. Vendor-reported scores are self-reported and disputed between vendors, so they are not a scoreboard. A plain-file agent baseline has been reported to do well on LoCoMo, which is why Control A for memory includes it.

### 10.2 Pre-registration (one page, written before running)

```
Module / slot:
Hypothesis (one falsifiable sentence):
Control A:            Control B (named standard tool):
Task suite (n, source, held-out?):
Primary metric:       Secondary: latency, tokens, joules/task, RAM
Win threshold (fixed now):
Kill condition:
Time box:
Result / decision / report link:
```

If the win condition cannot be written in five lines, the module is not ready to build.

### 10.3 Promotion ladder

| Level | Requirement |
|-------|-------------|
| experimental | Runs; passes conformance tests and `self_test()` |
| candidate | Beats Control A on its pre-registered suite |
| recommended | Matches or beats Control B on accuracy at lower cost on at least one axis (energy, RAM, latency, offline operation), or does something B cannot |
| default-on | Recommended + passes the optionality matrix + two weeks without regression in the trace log |

Any regression demotes. A module that ties Control B at higher cost is archived with a report, not promoted.

### 10.4 Measuring energy

Joules per task = measured watts above idle × seconds. The wall-plug meter is ground truth. GPU sensor logging (for example HWiNFO CSV logs on Windows) is a useful second signal but does not capture CPU, FPGA, or whole-system draw.

### 10.5 Claims ledger (initial HDC entries)

Transcribed from the owner's validation handoff dated 2026-10-24 and B1 pilot notes. **Confirm against the original reports before treating as final.**

| Status | Claim |
|--------|-------|
| Validated (pilot-level, not production-certified) | Algebraic correctness of BSC and MAP operations; superposition associative-memory knee around N = 200–500 at D = 10k; nearest-neighbor index holds to N = 20k; paired-input C1 passed 40/40; C5 shared-graph and 100k-operation C6 restart tests completed |
| Negative | Word-level lexical retrieval: HDC pipelines lost to BM25 and to binarized learned embeddings with rescore (scifact B1). HRR and FHRR deprecated for this project |
| Process lesson | A TorchHD adapter bug (float32 cast dropped the VSA type) invalidated an earlier ranking; adapter fixed with regression tests |
| Open | C7; total-memory-budget test; relational composition and continual update on realistic data; any real-data win over SQLite plus a derived binarized index |

Every plugin keeps its own ledger in the same format.

---

## 11. Security and Safety

- **Sandbox code execution.** Anything that runs code or solver input derived from LLM text (`calc`, `verify`, `optimize`, `plan`, `sim`) runs in a restricted subprocess, container, or WASM runtime with CPU, memory, time, filesystem, and network limits. Use whichever isolation the host OS actually supports; do not assume Linux-only tools on Windows.
- **Untrusted text.** Retrieved memory and tool output are data, not instructions. Label them in the prompt and never act on instructions found inside them. Consider taint labels on retrieved text so downstream permission checks know where content came from.
- **Memory write gating.** Every write carries provenance: `user`, `tool`, or `model`. Model-originated facts are stored quarantined and are not returned as ground truth until confirmed.
- **Permissions.** `WRITES_STATE` and `EXTERNAL` operations need explicit grants in the policy guard, per module, per session.
- **Resource caps.** Hard limits per call and per session so a runaway solver cannot starve the host.
- **Reference:** OWASP's LLM application risk list is a useful checklist for review.

---

## 12. Modules: Two Tracks

### 12.1 Track A — Adapters (wrap mature tools; correctness comes from the tool)

Low novelty, high reliability, usually a day or two each. The hard part is the LLM's formalization, so every adapter that accepts formal input returns `assumptions` and a `formalization_echo`, and ships with known-instance tests.

| Slot | Wraps | Notes |
|------|-------|-------|
| `calc` | Python sandbox + SymPy/mpmath/decimal | **Baseline #1.** Exactness-critical |
| `memory` | SQLite (WAL) exact store + FTS5 + binarized embedding index | **Baseline #2.** Canonical truth for all memory challengers |
| `state` | Typed, versioned, event-sourced SQLite store | **Baseline #3.** Replaces the SSM row for conversation consistency |
| `verify` | Z3 / cvc5 (Lean 4 later) | Tri-state results; echo required |
| `optimize` | OR-Tools CP-SAT, HiGHS | Report status and gap |
| `plan` | pyperplan / Fast Downward, OR-Tools | LLM writes spec, planner searches, verifier checks |
| `prob` | scipy.stats, then pgmpy / PyMC | Start with closed-form `bayes_update` |
| `causal` | DoWhy, EconML | Assumptions and identifiability first |
| `space` | shapely, trimesh, networkx, PyBullet | Scene graph plus geometry |
| `sim` | SciPy `solve_ivp`, Pint, MuJoCo/PyBullet | Units mandatory |

### 12.2 Track B — Research (novel; must beat a Track A baseline in the same slot)

| Challenger | Slot | Hypothesis shape |
|------------|------|------------------|
| HDC | `memory.relate`, `memory.index` | Beats SQLite-derived indexes on compositional/relational queries, noise tolerance, or update cost at lower energy or RAM |
| KAN | `fit.symbolic` | Beats PySR and B-spline-MLP at equal FLOPs on formula recovery |
| Capsule / object-file model | `space.objects` | Beats the scene-graph adapter on object-permanence tasks |
| SSM-style state | (model-architecture project) | Out of Cognitum scope until a concrete I/O is defined |

### 12.3 Tiers (revised)

- **Tier 0 — Core:** registry, contract, policy guard, trace log, evaluation harness.
- **Tier 1 — Baselines:** `calc`, `memory`, `state`.
- **Tier 2 — First challengers (one at a time):** HDC in `memory.relate`; then KAN in `fit.symbolic`.
- **Tier 3 — Adapters on demand:** `verify`, `optimize`, `plan`, `prob`, `causal`, `space`, `sim`.
- **Tier 4 — Park:** TDA, MAML/adaptation, capsules, SSM-in-plugin.

Everything can still be built in any order as an experiment. Promotion rules do not change.

---

## 13. Roadmap and Working Rules

**Phase 0 — Core minimum.** Trace log, manifest and schema validation, policy guard, slot registry, enable/disable flags. No custom router.

**Phase 1 — Baselines and harness.** `calc`, `memory`, `state`; harness v0; a task set built from real prompts in the trace log (10–20 tasks beats a synthetic benchmark for relevance).

**Phase 2 — First challenger.** HDC in `memory.relate` against the Phase 1 memory baseline, with a pre-registration. Then KAN.

**Phase 3 — Adapters on demand.** One at a time, when a real task needs it.

**Working rules:**

- **WIP limit = 1 active experiment.**
- **Time-box** each challenger's first gate (suggestion: 3–5 working days; adjust once, then hold).
- **Kill rule:** if a challenger misses its pre-registered threshold, archive it with a short report. Reference results stay in the ledger. Do not rerun with new thresholds.
- **Bound evaluation cost:** reuse the harness; one-page pre-registration; no new test machinery unless the old one cannot express the hypothesis.
- **Owner-controlled order.** The AI implements; the owner prioritizes, rejects weak integrations, and signs off promotions.

---

## 14. Open Questions for the Owner

1. **SSM module:** what are its actual inputs and outputs? If there are none, it moves to the model-architecture project.
2. **Host:** native registration with protobuf internally, or an MCP client such as LM Studio first? This decides which schema is canonical and which transport ships first.
3. **Hard refuse vs disclose:** for each exactness-critical slot, should a missing module refuse the exact claim outright or answer with an "unverified" label?
4. **Tool budget N:** what does the target local model actually select correctly at 4, 8, 12, and 20 tools? Measure before designing family tools.
5. **First task set:** which 10–20 real tasks from daily use should seed the harness?

---

## 15. Change Log: 1.1 → 1.2

- Added review: pros, cons, module-by-module check.
- Added two-track structure and champion/challenger slots.
- Moved evaluation into Tier 0; added baselines, pre-registration template, promotion ladder, energy measurement, claims ledger.
- Tightened contract: per-operation schemas, solver-style statuses, exactness, assumptions, formalization echo, evidence, side effects, required correlation ID, calibrated-only confidence.
- Replaced custom router plan with native tool calling plus a deterministic policy guard; added tool budget.
- Added fallback matrix and mandatory disclosure.
- Replaced random-subset testing with a structured matrix and a no-module-to-module-calls rule.
- Added security and threat model.
- Corrected failure-class pairings (KAN, MAML, Neural ODE, SSM, HDC, capsules).
- Added non-goals, working rules (WIP limit, time-boxes, kill rule), and open questions.

---

**End of Revision 1.2**
