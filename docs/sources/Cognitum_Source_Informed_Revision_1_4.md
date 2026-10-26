# Cognitum — Cognitive Augmentation and Hybrid Research Architecture

**Revision:** 1.4 — source-informed design recovery, architecture hardening, and implementation plan  
**Date:** 2026-10-25  
**Original creator:** Michael Vang  
**Basis:** Original Cognitum 1.0 (`hybrid_ai_design.md`), Strengthened 1.1, Review 1.2, and Critical 1.3  
**Status:** Design proposal and critical revision; **not** an implemented, tested, or validated system.

> **Mission.** Cognitum investigates and deploys complementary computational capabilities around an LLM: explicit memory, structured state, symbolic reasoning, search, uncertainty, spatial representation, simulation, and candidate learned components. The system must make the resulting *compositions* useful and trustworthy, not merely increase its tool count. It does not claim an ensemble is inherently smarter or that valid computation proves the interpretation of a natural-language task was correct.
>
> **Integrity invariant.** Missing, failing, uncertain, or unauthorized capabilities cannot be concealed by confident prose. Graceful degradation means *honest reduced capability*, not the ability to answer every request.
>
> **Research invariant.** Research is free to explore capabilities that established baselines do not yet express. **Default-on promotion** requires reproducible end-to-end benefit against competent controls. An experiment's failure retires the tested hypothesis, not an entire mathematical field.

---

## 0. Executive decision and change record

Revision 1.2 made a valuable strategic pivot: **adapters first for dependable user-facing capabilities, challengers second for deployment**. Revision 1.3 keeps the 12-module research vision, the three initial baselines (`calc`, `memory`, `state`), the optional-plugin rule, and the champion/challenger evaluation model. It changes the runtime contract and the meaning of verification.

### What 1.3 established (preserved in 1.4)

1. **Separates execution status from domain outcome, evidence, and assurance.** `OK` does not mean `PROVEN`; `SAT` is not the same as `OPTIMAL`; a solver's formal guarantees do not validate the LLM's interpretation.
2. **Introduces a formalization gate** between natural-language intent and exact engines; human confirmation is reserved for ambiguous or consequential cases, not every routine calculation.
3. **Makes plugin permissions compositional.** Effects are sets of capabilities with scoped grants, not a single `SideEffects` enum.
4. **Separates an application-stateful service from a stateless request interface.** Cognitum memory and state are persistent even when its RPC calls are independent.
5. **Adds memory lifecycle and belief revision.** Provenance does not make a statement true; claims may be contradicted, superseded, retracted, expired, or confirmed.
6. **Prevents evaluation replays from performing real-world actions** and protects trace data from becoming an uncontrolled private-data repository or a contaminated benchmark.
7. **Defines host boundaries.** Cognitum can be a standalone benchmarkable capability service or an embedded Lu component; it should not fork or duplicate Lu's already-existing tools, IPC, or agent loop.
8. **Separates smoke-test task sets from statistical promotion evidence.** Ten to twenty tasks can start a harness; they cannot establish a general performance win.
9. **Adds development ergonomics.** Plugin reloads and manifest refresh should not require reinstalling an entire development integration after every edit.
10. **Moves the project’s differentiator beyond wrappers:** reliable *cognitive handoffs* (formalization, uncertainty, belief revision, compositional reasoning, failure disclosure).

**New in 1.4:** source lineage and original-intent reconstruction; concrete 1.0 static-code findings; distinct production and research lanes; rejection of a universal vector space as a system invariant; recovered HDC–state/object, KAN-surrogate, learned-dynamics, multimodal, routing, and self-improvement hypotheses; factorial ablations; a source-informed Phase 4B and eight additional test templates.

**Source chronology note:** Revision 1.2 says its underlying 1.1 revision was dated **2026-10-26**, one day after the date on this document (2026-10-25). Preserve that discrepancy as a source-metadata issue until the source revision history is checked; it is not evidence that a build or review happened on that future date.

---

## 0A. Design lineage and original intent recovered

This revision was prepared **after inspecting the original 2,983-line 1.0 implementation specification and the 1.1 and 1.2 revisions**, rather than inferring the initial vision only through 1.2. Original version numbers and dates are copied as source labels; they do not independently establish chronological execution order. In particular, 1.1/1.2 identify 2026-10-26 even though 1.3 was dated 2026-10-25.

| Source | What it contributed | What was later lost or changed |
|---|---|---|
| **1.0: `hybrid_ai_design.md`** | Twelve heterogeneous computing areas; LLM-mediated multi-module chains; typed user-facing operations; a shared representation hypothesis; future HDC–SSM, HDC–capsule, KAN-surrogate, multimodal, and self-improvement ideas | Some technologies were prematurely described as eliminating an LLM failure class; illustrative code contained real defects; an eight-week completion estimate was unvalidated |
| **1.1: `Cognitum_Strengthened_Revision_1.1.md`** | Radical optionality, core/plug-in split, versioned contracts, a registry, risk analysis, measurement before promotion | Removed most of 1.0's testable technical sketches and future experimental compositions without replacing them with research specifications |
| **1.2: `Cognitum_Strengthened_Revision_1_2(1).md`** | Mature-tool controls, champion/challenger slots, safe fallbacks, bounded harness, formalization disclosure, security | Used the standard-tool baseline as the dominant lens and partially buried research into *new* joint capabilities that have no clean one-plugin incumbent |
| **1.3: `Cognitum_Critical_Revision_1_3.md`** | Execution/outcome/assurance separation; rigorous formalization; permissions; canonical belief revision; host/Lu boundaries; safe test replay | Was authored from 1.2 and therefore did not yet restore some concrete research questions from 1.0 |

**Corrected design thesis:** The first production layer should use reliable conventional engines; the *research agenda* should ask whether new combinations produce capabilities, quality, efficiency, or adaptation that neither a raw LLM nor conventional single-slot tools offer. These are compatible goals, not competing doctrines.

**Do not reinstate the original universal 10,000-dimensional vector space as a requirement.** HDC binary/bipolar hypervectors, learned embeddings, SSM hidden states, capsule/object poses, and TDA point clouds have different geometries, units, and semantics. Translation between them is an explicit, versioned, measured adapter. It is a **hypothesis** that shared representation might be beneficial, not a default architectural fact.

**What stays deliberately unproven:** HDC does not automatically repair hallucinations; KAN is not an exact calculator; a random-state linear recurrence is not a semantic consistency checker; coordinate vectors are not learned capsule networks; heuristic search does not prove optimality. The original sketches are design inputs, **not verified implementations**.

---

## 0B. Two lanes with different success criteria

**Production lane:** improve actual user outcomes with exact stores, solvers, sound validation, and secure invocation. An incumbent standard tool is the deployment default until a contender shows value on matched cases.

**Research lane:** test hypotheses about *composition* and representation, including experiments that need two or more components and have no single-slot incumbent. Each study still specifies baseline, falsifiable predicted advantage, cost, negative controls, and held-out data. A research artifact can be scientifically useful without being deployed or winning immediately.

**Promotion gate is not an idea-generation gate.** Separate `hypothesis`, `prototype`, `replicated`, `recommended`, and `default_on`. A failed trial is recorded with its exact task and conditions. New hypotheses require new preregistration, not retrospective threshold changes.

**Compositional evaluation:** report single-component A, single-component B, conventional A+B, experimental A+B, and host LLM alone where applicable. Measure incremental **interaction benefit**, not merely whether A+B beats doing nothing.

---

## 1. Critical audit of Revision 1.2

The criticisms below are proposed design changes, **not** reports of bugs observed in a running Cognitum system.

| Priority | Finding | Why it matters | Resolution in 1.3 |
|---|---|---|---|
| P0 | `Status`, `Exactness`, and `confidence` imply a stronger guarantee than a plugin can provide | A solver can finish correctly with `UNKNOWN`; a formal proof can describe the wrong model; numerical libraries can return rounded values | Separate execution, outcome, assurance, and interpretation validation |
| P0 | `SideEffects` is a single-valued enum | A module can read state, write files, and reach the network in one call | Declare a set of effects plus file/path/network scopes; enforce least privilege |
| P0 | Replaying logged tasks is treated as benign | Evaluations could accidentally repeat deletions, state writes, or outbound requests | Read-only snapshots, fake tools, side-effect denial, and replay isolation |
| P0 | “Sandboxed subprocess” may be interpreted as a sufficient security boundary | Plain subprocesses do not reliably contain hostile generated code | OS-enforced isolation with deny-by-default access and hard resource limits |
| P1 | “Exact store is truth” conflates durable storage with epistemic authority | User assertions, imported text, and model hypotheses can all be stored precisely and still be wrong | Canonical claim ledger with provenance, verification state, temporal validity, and revision |
| P1 | Formalization echo is not an independent validation | An LLM can repeat the same misunderstanding in English and equations | Type/range/unit checks, round-trip probes, invariant tests, and risk-based confirmation |
| P1 | `INFEASIBLE` is used as a generic status | Solver outcomes vary by domain: SAT/UNSAT/UNKNOWN; FEASIBLE/OPTIMAL/INFEASIBLE/MODEL_INVALID | Per-operation outcome schemas and generic transport status |
| P1 | Core, plugins, transport, and host are not sharply distinguished | Risks reimplementing tools, memory, and agent routing already present in Lu | Host adapter layer; embed instead of rebuild |
| P1 | Preregistration lacks statistical safeguards | 10–20 convenient tasks, repeated tuning, and leakage can promote false wins | Held-out sets, paired comparisons, CIs, version-locked baselines, reproducibility |
| P1 | Permission grant semantics are underdefined | A model may mistake retrieved instructions for authorization | Only trusted user/policy grants; sensitive writes confirmed per action |
| P2 | “Stateless” is overloaded | Modern MCP stateless requests do not prohibit persistent app data | Stateless call semantics; explicitly stateful backing services |
| P2 | Canonical `.proto` to JSON Schema conversion sounds automatic | Some semantics do not project losslessly across schema systems | Explicit schema projections plus cross-format golden tests |
| P2 | All-or-nothing optionality hides feature dependency realities | A memory index might require a store, and a plan verifier requires a plan artifact | Explicit declared dependencies, optional derived indexes, no hidden calls |
| P2 | Energy equation is oversimplified | Idle-subtracted watts × time ignores variable load, thermal and concurrency effects | Sampled energy integrals and matched operating conditions |
| P2 | “One or two days per adapter” is not a defensible schedule | Verification, error handling, version compatibility and sandboxing dominate effort | Estimate by measured gates, not by library import time |

### Source-code-level corrections from 1.0 (static inspection, not runtime tests)

The original included concrete Python sketches. Several require repair **before they can serve as prototypes**:

1. **HDC method/attribute collision:** `HDCMemory.__init__` assigns `self.store` a dictionary while also defining `store(...)` as a method. Instance attribute lookup hides the method, so `mem.store("key", "value")` attempts to call a dict. The retrieval path also contains an unfinished `pass` and does not reconstruct values as advertised.
2. **HDC binding algebra:** elementwise multiplication of arbitrary normalized Gaussian vectors is not generally self-inverse. Multiplying the bound vector by the same key again yields approximately `value * key**2`, not guaranteed recovery. Choose a *declared* VSA family (such as BSC/MAP) with tested unbinding semantics; keep a cleanup dictionary and independent exact key/value storage.
3. **Shared-vector assumption:** the original uses 10,000-dimensional hashed text vectors for HDC while its SSM hidden state has 128 dimensions and capsule positions have six physical coordinates. These are not interchangeable semantic spaces. Hash-generated random vectors also do not encode natural-language synonym similarity on their own.
4. **Capsule geometry:** normalizing position/orientation to unit length and rescaling by existence confidence alters physical coordinates. Distance and rotation tests therefore cannot be trusted as representations of the original input coordinates. Store coordinate frames/poses separately from existence probabilities; learned capsule routing is a distinct, testable model.
5. **SSM consistency:** a random linear recurrence followed by random-axis oscillation analysis does not establish whether two natural-language claims contradict. Structured claim comparison is the conventional control; a learned temporal state challenger needs labeled semantics and a defined readout.
6. **Math/parser security and labeling:** the numerical module's `eval(...)` path is not an acceptable untrusted-expression boundary; `sympify(...)` also requires care with untrusted input. Use a restricted AST, allowlisted functions, and isolation. A SymPy calculator is not a KAN; exact arithmetic must not be credited to the learned function approximator.
7. **Planning assurance:** the simple MCTS returns a searched path but does not establish an optimal sequence. Do not call the answer optimal without a domain-appropriate bound or proof. Likewise, an LLM-generated confidence above `0.90` is not proof that an exact solver can safely be skipped.

These are **specific reasons to harden 1.0**, not reasons to throw out the 12-topic research portfolio.

### Preserve from 1.2

- Optional modules, with a core that can explain what is unavailable.
- Champion/challenger slots and *standard-tool* baselines.
- HDC as an algebraic/relational memory research candidate, **not** an automatic retrieval win.
- KAN as a symbolic-function-fitting candidate, **not** a calculator.
- The twelve-module map, but not twelve simultaneous delivery commitments.
- One active research experiment at a time; explicit stop/go rules.

---

## 2. Architecture and non-goals

### 2.1 Boundary model

```text
User / application request
          |
          v
+----------------------------+
| Host (Lu or standalone UI) |
| Conversation, auth, UI     |
+-------------+--------------+
              |
              v
+----------------------------+
| Cognitum orchestration     |
| Intent / slot selection    |
| Policy / budgets / grants  |
| Formalization risk gate    |
| Plan + disclosure + trace  |
+-------------+--------------+
              |
              v
+----------------------------+
| Capability registry        |
| Champion + challenger      |
| Typed contracts / routing  |
+-------------+--------------+
              |
       +------+------+-----------------+
       |             |                 |
       v             v                 v
  Exact adapters  Durable services  Research challengers
  calc / verify  memory / state     HDC / KAN / etc.
  plan / opt...  SQLite + indexes   disabled by default
       |             |                 |
       +-------------+-----------------+
              |
              v
    Validated results + evidence
              |
              v
  Host LLM synthesizes with assurance
  and explicit inability when required
```

**Cognitum is not another agent runtime.** The host owns user sessions, UI, user consent, and existing tool invocation. Cognitum owns its plugin contracts, slot selection policy, cognitive result validation, research comparisons, and capability-specific stores when genuinely needed. Integrate through a native host adapter first; add an MCP façade for clients that need it.

**No hidden module-to-module invocations.** The core composes explicit dependency steps. A module may declare `requires: [artifact_type, capability]`, but cannot secretly call another module or acquire the other's permissions. Multi-step plans carry typed intermediate artifacts and bounded budgets.

### 2.2 Service state versus handler state

Handlers should be **reentrant** and not rely on process-local conversational state. `memory` and `state` remain explicitly **persistent services** with scoped stores. Modern MCP request statelessness describes the wire protocol, not a requirement to discard application state between calls. State handles, workspace IDs, and snapshot IDs travel explicitly in requests.

### 2.3 Non-goals

- Training/replacing the base LLM or claiming AGI.
- Running twelve specialized networks in memory by default.
- Rebuilding Lu's desktop shell tools, scheduler, IPC, transport, or conversation stack.
- Multi-tenant SaaS governance during the first local prototype.
- A broad autonomous desktop observer: desktop learning/data collection belongs to a separately consented Lu ingestion feature, **not** to Cognitum's initial runtime.
- Treating a benchmark score or a solver return code as proof of end-to-end understanding.

---

## 3. Core invariants

1. **Honest degradation:** a disabled exact capability results in a clear limitation, not a fabricated answer.
2. **Least privilege:** module availability and permission to execute are separate decisions.
3. **Typed boundaries:** inputs and outputs are checked against the *specific operation* schema, not merely a generic envelope.
4. **End-to-end assurance:** formal validity, input interpretation, evidence source, and result completeness are reported separately.
5. **Storage is not truth:** source assertions have provenance, lifecycle, and confidence labels independent of whether they are durably stored.
6. **Replay is inert:** tests cannot execute production writes or network actions unless separately authorized in an isolated fixture.
7. **Comparison against competent baselines:** a challenger competes with the standard technique and the host's real existing tools, not a crippled straw-man baseline.
8. **No invisible privilege escalation:** retrieved text, documents, web pages, or model outputs never become authorization.
9. **Measured optionality:** disabling a plugin cannot crash core startup or silently corrupt the canonical store.
10. **Evidence before promotion, creativity before commitment:** prototype freely, deploy conservatively.
11. **Representations are typed:** hypervectors, embeddings, hidden states, pose/geometry, and topological structures cannot silently share a coordinate system.
12. **Composition is first-class:** test whether combinations offer benefits above the best single component and mature-tool composition.
13. **Scientific negative results are durable:** archive a defeated hypothesis, retain reproducible data, and allow distinct preregistered hypotheses.

---

## 4. Capability contract 1.3

This section defines semantics; the final generated models may be Protobuf for Lu's native boundary and strict JSON Schema/Pydantic at Python and external tool boundaries.

### 4.1 Four different dimensions

| Field | Purpose | Examples |
|---|---|---|
| `execution_status` | Did the handler execute and return a well-formed result? | `completed`, `partial`, `invalid_input`, `timed_out`, `cancelled`, `unavailable`, `error` |
| `outcome` | Domain-specific answer, typed per operation | SMT `sat/unsat/unknown`; optimization `optimal/feasible/infeasible/model_invalid/unknown`; recall `matches`; arithmetic `value` |
| `assurance` | What guarantee applies *to the stated formal input*? | `proved`, `exact_arithmetic`, `bounded`, `numerical`, `heuristic`, `unverified` |
| `interpretation` | Was the problem formulation checked against user intent? | `checked`, `user_confirmed`, `assumption_bound`, `unresolved` |

A handler with `execution_status=completed` and `outcome=unknown` is a **successful call that did not resolve the question**. `assurance=proved` only applies to a verified proof or sound solver claim *under explicit assumptions*, not to an English paraphrase. Exact arithmetic is not promised for ordinary floating-point NumPy code.

### 4.2 Required request fields (conceptual)

```yaml
contract_version: "1.3.0"
request_id: "uuid"
correlation_id: "uuid"
operation: "verify.smt"
operation_schema_version: "1.0.0"
workspace_id: "opaque-scope"
subject_id: "opaque-user-or-agent-identity"
payload: {}                      # validated against operation schema
budget:
  timeout_ms: 5000
  max_memory_mb: 512
  max_calls: 1
  anytime_ok: false
execution:
  dry_run: false
  idempotency_key: null          # required for retryable writes
  cancellation_id: null
  source_taint: ["user_input"]
permission_context: "opaque-trusted-grant-reference"
```

### 4.3 Required response fields (conceptual)

```yaml
contract_version: "1.3.0"
request_id: "matches-request"
correlation_id: "matches-request"
operation: "verify.smt"
module: {name: "z3_adapter", version: "0.1.0"}
execution_status: "completed"
outcome: {kind: "smt", value: "unsat"}  # domain-specific, typed
assurance:
  level: "proved"
  applies_to: "formal_model_only"
  error_bound: null
interpretation:
  level: "assumption_bound"
  formalization_hash: "sha256:..."
  restatement: "No assignment satisfies the submitted constraints"
  assumptions: ["Constraints represent the requested problem"]
evidence: [{kind: "solver_artifact", ref: "hash-or-artifact-handle"}]
result: {}                       # validated per operation
side_effects_observed: []
resource_usage: {latency_ms: 12, peak_memory_mb: 40}
error: null
```

**Manifest additions:** `operations`, `input/output schema hashes`, `required_capabilities`, `requires_artifact_types`, `effects: [read_state, write_state, read_file, write_file, network, execute_code]`, scoped `paths/domains`, deterministic/seed support, idempotency policy, cancellation semantics, and an API-compatible version range.

The policy guard must check **actual effects against declared and granted effects**. It also enforces read scopes, not only writes. `dry_run` must suppress mutations by construction; cost estimates are explicitly estimates, not guarantees.

### 4.4 Compatibility, lifecycle, and isolation

- Reserve retired Protobuf field numbers and names; do not reuse them. Use explicit presence (`optional` for relevant proto3 scalars or editions' explicit presence) when absent differs from zero/false/empty.
- Use `buf` breaking checks for `.proto`, schema golden tests for Protobuf ↔ JSON, and versioned fixtures for Python adapters. Do not assume conversion preserves all semantic constraints automatically.
- Repeated requests with the same `idempotency_key` must not duplicate committed side effects; use a durable operation journal/transaction boundary where possible.
- Cancellation is cooperative for modules, **plus** a host ability to terminate an isolated worker. A timeout is not itself an isolation boundary.
- Keep implementation diagnostics and sanitized failure categories out of user-facing data unless needed. Never leak secrets in error messages.

---

## 5. Formalization gate: the actual hardest problem

Cognitum's distinctive failure risk is **correct computation over incorrectly modeled intent**.

**For exactness-critical operations:**

1. **Extract** the intended problem, variables, units, objectives, scope, and constraints from trusted request content.
2. **Build** typed formal input (expression, SAT/SMT, optimization model, transition system).
3. **Validate** it: schema and units; domain/range checks; constraint consistency; known invariants; any available property tests.
4. **Echo** a plain-language summary plus the omitted assumptions. For low-risk unambiguous cases, proceed; for ambiguous or consequential cases, require the host to obtain confirmation.
5. **Execute** the solver or tool under budget and permissions.
6. **Verify** a witness, candidate solution, certificate, or independent checker when available. A solver's outcome should not be promoted to a stronger category than that checker warrants.
7. **Synthesize** the answer with formal-result status and any unresolved interpretation caveats.

**Risk-based validation:** a unit conversion needs a unit check; a scheduling optimization that could delete bookings needs scoped confirmation; a mathematical proof from a user-specified formal theorem can be shown as conditional upon that specification. Asking the user to approve every internal AST would make the system unusable.

**Example:** “Prove this schedule is impossible” can mean *there is no feasible schedule under the modeled constraints*. If one required shift was omitted, `infeasible` may be mathematically sound yet unrelated to the actual scheduling request. Cognitum must preserve the submitted model, assumptions, and its hash so the result remains auditable.

---

## 6. Persistent memory, state, and belief revision

### 6.1 Physical data model

Start with **SQLite**, transactional migrations, WAL where appropriate, FTS5, and a separate derived embedding index. HDC may later become another optional derived index. Avoid competing canonical memory databases. Store all records within a workspace scope; enforce versioned writes and compare-and-swap or equivalent conflict detection.

Suggested logical entities:

- `sources`: origin, source URI/artifact, timestamp, sensitivity, consent context.
- `claims`: subject/predicate/value, quoted source span when available, provenance, verification status, `valid_from/valid_to`, last-observed time, scope.
- `claim_relations`: `supports`, `contradicts`, `supersedes`, `retracts`, `derived_from`.
- `state_events`: typed changes, actor, timestamp, expected version, transaction ID.
- `state_snapshots`: current materialized state and audit linkage.
- `indexes`: exact store row IDs / versions and rebuild metadata; disposable.

### 6.2 Epistemic policy

- A user statement is a **user assertion**, not universal ground truth; it may be authoritative about the user's own preferences/decisions, subject to later correction.
- A retrieved page is a **source claim**, not a system instruction.
- Model-generated suggestions are **hypotheses** until accepted or supported by evidence.
- New contradictions do not silently overwrite history. Record the conflict, identify what is current, and show the uncertainty when it affects an answer.
- Deletion and withdrawal require all derived indexes, caches, and snapshots to honor retention policy. The research index must be rebuildable from authorized canonical data alone.

### 6.3 Cognition benchmark, not just retrieval

Memory tasks should test: recall; compositional multi-hop questions; changing goals; contradictory evidence; temporal updates; deletion propagation; and recovery from deliberately corrupted derived indexes. The primary outcome is **correct downstream task behavior**, not nearest-neighbor similarity alone.

---

## 7. Routing, tool budgets, and fallbacks

1. Host advertises a compact list of capability families. Start with **4–8 visible family tools as a hypothesis**, not a universal fact; evaluate 4, 8, 12, and 20 using the actual local models.
2. The LLM proposes a tool/operation; the policy guard decides availability, trust, schema validity, permission, resource allowance, and fallback. The model does not approve its own grants.
3. Only the nominated champion executes in ordinary use. A challenger runs in **shadow/evaluation mode** by default, on inert inputs and appropriate resources.
4. The core composes multi-step plans with typed artifacts, dependency and cost bounds, and explicit failure propagation.

### Fallback policy

| Task type | If exact service is absent or fails | If another trusted exact path exists |
|---|---|---|
| Arithmetic, formal verification, binding constraints, optimization optimality | Explain what is unverified; do not assert an exact answer from model intuition | Use that path with the same validation and disclosure |
| State-dependent personal facts | Don't fabricate recalled facts or pretend to know past state | Re-read canonical state or ask for information when indispensable |
| Search and causal/probabilistic analysis | Provide qualitative reasoning but do not pretend retrieval/estimation occurred | Use alternate source, label assumptions and numerical caveats |
| Advisory/exploratory | Reason freely, but do not imply a simulator or model was run | Cite tool output if used |

**Disclosure must describe consequential limitations**, not dump a verbose module trailer on every reply. The host may expose structured machine-readable fields for `modules_used`, `limitations`, `verification_level`, and `permissions_granted` in an expandable trace. Absence of a module should be surfaced whenever it materially affects answer correctness.

---

## 8. The module portfolio: adapters and research challengers

The full twelve-topic vision remains a **portfolio**, not an installation manifest. The table below specifies **production incumbents**, not the limits of permissible research. Research composites involving several slots are tracked separately (Section 8A). For wholly new capabilities, the first control is the best feasible conventional or LLM-only approach, rather than a fabricated same-slot incumbent.

| Original research area | Production slot / incumbent | Research role or disposition | First useful task |
|---|---|---|---|
| HDC | `memory.relate/index`: SQLite FTS5, graph queries, binarized embeddings + rerank | **First challenger** for compositional binding, incremental updates, noise, and energy | Multi-hop relational recall with updates |
| KAN | `fit.symbolic`: PySR + MLP/B-spline MLP | **Second challenger**, formula discovery only | Recover known expressions on held-out functions |
| SSM | `state`: typed event log + snapshot | Model architecture deferred; plugin only with concrete input/output contract | Keep decisions consistent over changing conversations |
| Capsule/object models | `space`: scene graph + geometry / simulation | Research challenger after object benchmark exists | Object permanence through occlusion/scene changes |
| MCTS + DP | `plan`: graph search, PDDL planners, OR-Tools | MCTS only for a domain with a justified branching/search model | Find and validate a short multistep plan |
| Causal models | `causal`: DoWhy/EconML as appropriate | Adapter; never infer identification from a picture of a DAG alone | Explicit assumptions, identification, sensitivity |
| Bayesian networks | `prob`: analytical Bayes, scipy.stats, then pgmpy | Adapter; calibrated probabilities only with applicable data/model | Base-rate update with labeled priors |
| Neural ODE / physics | `sim`: units + ODE solver / physical simulator | Learned dynamics is research, not a default physics oracle | Predict a simple trajectory with checks |
| SMT / provers | `verify`: Z3/cvc5; Lean for proof artifacts | Adapter; independent formulation validation | Prove/deny specified constraints |
| Combinatorial optimizers | `optimize`: CP-SAT, HiGHS | Adapter; feasible is not necessarily optimal | Schedule under constraints and report gap |
| MAML / meta-learning | Domain adapter/RAG/LoRA where supported | Defer MAML as an inference plugin | Controlled domain adaptation comparison |
| TDA | Data-analysis adapter using GUDHI/ripser when asked | Park until task-defined | Analyze persistence on a real dataset |

### Three must-ship baselines

**`calc`** — precision-aware arithmetic and restricted expression evaluation. Support exact integers/rationals/decimal and symbolic expressions as separate operations; numerical approximation must say so. Prefer an AST evaluator for ordinary arithmetic; invoking generated arbitrary Python code is a privileged, separately sandboxed operation, not the default calculator.

**`memory`** — transactional exact data store + FTS5 + optional derived embeddings. Source claims, permissions, and deletion/revision are first-class.

**`state`** — typed user/project state, event log, version checks, and belief revision. Optimize for correct continuity, not for mimicking attention or an SSM.

### HDC lessons remain intact

The 1.2 pilot notes report scifact nDCG@10: dense 0.718; binarized-plus-rescore 0.717; BM25 0.646; best HDC word pipeline 0.520. The revision also records algebraic-operation tests and a prior adapter type-casting bug. These are **owner-reported pilot results**, not independently verified here. They **do not** establish an HDC retrieval win; they do justify testing whether HDC adds value in a narrower *relational composition* slot. Keep exact canonical storage underneath.

For KAN, compare formula recovery, generalization, complexity, inference cost, and FLOPs with a symbolic-regression system and a B-spline MLP. Do not equate function fitting with reliable exact arithmetic.

---

## 8A. Recovered research hypotheses from the original 1.0

The following experiments originate in **1.0 Section 13**, reframed here as *unproven* hypotheses with clear I/O and minimum comparisons. They are not required for the production core and may be run in the standalone harness. A composite is orchestrated through typed artifacts; it does not grant one plugin hidden access to another plugin's data or privileges.

| Experiment | Hypothesized advantage | Minimum controls and primary test |
|---|---|---|
| **HDC + explicit temporal state** | Relational retrieval conditioned by task phase, decisions, and state changes | FTS5/embedding + typed state; HDC alone; state alone; combined HDC+state. Score temporal multi-hop answers after revisions, plus cost and deletion correctness |
| **HDC + persistent object graph** | Robust binding of object identity and attributes through occlusion, renaming, and scene edits | Versioned scene graph alone, graph + ordinary embeddings, and HDC-indexed graph. Measure identity/relationship accuracy under interventions; never replace exact object IDs with approximate vectors |
| **KAN as planner/simulator surrogate** | Lower inference cost for repeated, bounded-domain estimates | Actual solver/simulator, simpler regressors including MLP and B-spline MLP, and KAN. Compare error, OOD failure detection, training cost, and fraction escalated to exact engine. Surrogate may not certify constraints |
| **Learned state dynamics / Neural ODE** | Useful non-linear sequence modeling where classical filters and typed state fail | Explicit event-sourced state + conventional sequence model. Train on labeled sequences; measure held-out prediction or anomaly detection, *not* claims of semantic consistency inferred from latent-vector oscillation |
| **Multimodal temporal + spatial memory** | More consistent object tracking and state across image/video/audio observations | Stable scene tracking, temporal associations, and an LLM with caption/context baseline. Measure identity, occlusion recovery, temporal queries, synchronization, and accuracy of source attribution |
| **Learned capability selection** | Lower wrong-tool and missed-tool rates for local models with large capability catalogs | Flat list, family tools, deterministic classifier, and learned scorer. Measure end-task quality, false invocations, abstention, latency, tokens, and overhead at controlled tool counts |
| **Self-improvement from traces** | Better routing and error prediction over time | Frozen policy versus approved, trained-on-past-only policy on future held-out tasks. Explicitly audit privacy, data leakage, reward hacking, and regression. No auto-promotion without approval |

### Research protocol for every composite

1. Define the cognitive task *before* choosing its technology; state what neither incumbent composition nor LLM baseline handles well.
2. Fix source of ground truth and train/validation/held-out split. Preserve chronological ordering for continual/adaptation tasks.
3. State the required interface: inputs, outputs, supported representation, conversion costs, provenance, mutation and deletion behavior.
4. Run **factorial ablations**. For two components A and B, compare neither, A only, B only, and A+B under matched constraints; add a conventional composition control if available. Report the incremental interaction rather than attributing all gain to A+B.
5. Include adversarial/null cases: irrelevant context, misinformation, contradictory updates, deleted records, missing modalities, out-of-distribution scenes, and tool denial.
6. Measure *quality, latency, memory, power/energy, training cost, and human intervention* at whole-task scope, not only a convenient kernel.
7. Produce a claims-ledger entry even for failure. Promotion to a user's default stack requires independent replication and clean security/optionality behavior.

### Scope boundary

A composite plugin can be a separately versioned **research assembly** with its own declared inputs, internal subcomponents, and isolated process. That is not permission to secretly invoke production capabilities or modify a model's weights. Any model-internal co-training remains a separate architecture experiment and cannot masquerade as a drop-in postprocessing plugin.

**Desktop observation or training-data collection** is not needed to establish Cognitum v1. If pursued as a Lu feature later, require explicit opt-in, pause/stop controls, private-content exclusion, redaction, retention/deletion controls, and separation between observed data, evaluated labels, and training sets.

---

## 9. Evaluation harness and promotion gates

### 9.1 Three controls, not two when the host already has tools

- **A. Bare host model**, without the specific augmentation.
- **B. Host model + the existing competent conventional tool**, including what Lu already offers.
- **C. Cognitum champion or challenger**, under the same task set, permissions, model, token budget, hardware, and failure-handling rules.

If `C` merely duplicates an existing Lu tool at higher latency or complexity, it is not an improvement.

### 9.2 What to measure

| Dimension | Examples |
|---|---|
| End-task correctness | Grounded fact accuracy; mathematical correctness; state revision correctness; execution outcome |
| Invalid assurance | Wrong-but-confident answers, misreported solver status, invented evidence |
| Formalization robustness | Omitted constraints, swapped units, incorrect entity references, unreviewed assumptions |
| Resource cost | p50/p95 latency, RAM/VRAM peak, total tokens, joules/task, startup time |
| Reliability | Errors/timeout rate, recovery after restart, result reproducibility, corrupt-index handling |
| Privacy and safety | Unauthorized tool attempt rate, prompt-injection susceptibility, replay safety, deletion propagation |

### 9.3 Dataset tiers

- **Smoke:** 10–20 real tasks to prove the harness and identify gross failures. These **do not** justify promotion.
- **Development:** labeled tasks split by operation and failure class, with frozen grading criteria; never claim held-out results from a tuned set.
- **Held-out promotion:** a materially larger sample adequate for the effect being claimed (initial engineering planning target: **100+ paired tasks per tested slot**, adjusted by power/variance, with confidence intervals and per-class breakdown). For rare high-consequence safety failures, use targeted adversarial cases beyond generic accuracy samples.
- **Regression:** locked representative cases run on every contract, plugin, prompt, dependency, and host-model change.

These counts are **planning heuristics**, not statistical guarantees. Evaluate with paired differences, uncertainty intervals, and a prespecified win threshold. Record unsuccessful runs, not just successful screenshots. Version-lock baselines and use multiple seeds when outputs or routing are stochastic.

### 9.4 Pre-registration card

```yaml
experiment_id: COG-HDC-REL-001
slot: memory.relate
hypothesis: "HDC improves compositional relation accuracy at fixed memory and latency"
control_A: "bare host + exact store"
control_B: "host + SQLite graph query + baseline derived index"
challenger: "HDC derived relation index"
tasks: "specified, labeled, held-out, privacy-cleared"
primary_metric: "end-task compositional accuracy"
minimum_effect: "specified before experiment"
secondary_metrics: [p95_latency, peak_ram, joules_per_task, update_cost]
constraints: "no significant increase in hallucinated grounding or stale answers"
stop_rule: "time-box reached / no evidence of threshold / critical safety regression"
blinding_and_grading: "independent canonical answer key; no grader circularity"
artifacts: [config_hash, dataset_version, model_version, report, traces]
```

### 9.4A Composition and causality of performance improvements

When testing A+B, use a **2 × 2 ablation** (neither, A, B, A+B) plus an established composition baseline. A raw improvement over neither does not establish synergy. Test whether the A+B result exceeds the stronger component and whether the *interaction term* is robust within confidence intervals. Evaluate user-visible success and resource cost, including representation conversion and serialization.

For tasks involving moving targets, run forward-in-time tests with timestamped updates and holdouts, not randomly shuffled examples that leak future evidence. If the input is a scenario simulation, distinguish simulated ground truth from real-world validation.

### 9.5 Promotion ladder

| Level | Evidence |
|---|---|
| Experimental | Schema + conformance + worker isolation + self-test |
| Candidate | Smoke and development tasks pass; known limitations recorded |
| Recommended | Preregistered held-out advantage over competent Control B, or a distinct ability B lacks, with uncertainty and resource accounting |
| Default-on | Recommended; optionality/permission/replay tests; adequate production-like exposure and no material regression |

**Do not equate “beats Control A” with research validation.** Missing a chosen research threshold means archive that **specific hypothesis** and its report; it does not forbid learning from results and registering a new, distinctly labeled hypothesis on fresh held-out tasks.

### 9.6 Accurate energy measurements

For a task interval, measure sampled whole-system energy (integrated watts over time), then compare **matched workload-vs-idle baselines** when estimating incremental cost. Record sampling rate, idle power, concurrency, thermals, CPU/GPU/FPGA activity, warm versus cold cache, and meter resolution. `average watts above idle × seconds` is only a rough approximation when conditions are stable. Report uncertainty rather than an unearned precision figure.

### 9.7 Evaluation replay isolation

- **Never replay production traces against live write tools by default.** Use sanitized fixtures, database snapshots, synthetic credentials, mock network endpoints, and an allowlist of inert operations.
- Treat prompts and tool output as untrusted, potentially sensitive data; opt into trace retention and redact secrets and personal content.
- Label traces `training`, `development`, or `held_out`; deduplicate near-duplicates across splits.
- Keep evaluator outputs, model answers, and gold labels separately. Avoid giving the grader the same unsupported reasoning it is scoring.

---

## 10. Security model

### 10.1 Trust boundaries

1. User/host-issued grants are trusted **only within the authorized scope**.
2. Model-generated code, queries, retrieved pages, imported memories, and tool outputs are **untrusted data**.
3. Module manifests may be supplied by third-party code: installation/enablement is a separate trust decision from runtime call authorization.
4. Solver input may trigger expensive computation; code execution and filesystem/network actions need stronger isolation than schema validation alone.

### 10.2 Enforcement

- **Deny network and filesystem writes by default**, including for calculator and solver workers. Grant only exact necessary directory/domain scopes to operations requiring them.
- For Windows local use, evaluate suitable OS-native restricted accounts/tokens, Job Objects/resource limits, process separation, and/or supported container/VM isolation. **A plain subprocess is not a sandbox.** Validate isolation experimentally for the chosen environment.
- Set per-call and per-session CPU, memory, wall-clock, disk, token, and tool-call limits. Explicitly handle cancellation and orphan workers.
- Require trusted user confirmation for irreversible deletes, external transmission, dangerous bulk writes, and similar consequential actions. A model cannot approve its own proposal.
- Store plugin packages/manifests with version and hashes. Verify signatures or provenance where available; pin dependencies for reproducible deployments.
- Mark tainted memory/tool text as data; never promote its embedded instructions into the host's authority level.
- Support scoped revocation and records deletion propagation; limit trace retention and encrypt sensitive local stores as needed.

**Security test cases:** prompt injection from memory retrieval; wrong-path writes; retry-induced duplicate writes; fake module-provided evidence; solver resource exhaustion; compromised/oversized plugin output; replay of a dangerous tool call; stale consent after a session boundary.

---

## 11. Interoperability and developer workflow

### 11.1 Recommended integration with Lu

1. **Audit and reuse Lu's existing native tool registrations and host agent loop.** Cognitum should be a capability provider, not a second competing agent framework.
2. Use **versioned Protobuf contracts at Lu-native boundaries** where that is already the architectural choice. Support JSON Schema tools at external model/adapter boundaries with explicit converters and conformance tests.
3. Provide an **in-process or local IPC adapter** for fastest offline usage and tight permissions; expose an **MCP façade only when an outside client needs it**.
4. Implement a registry reload and module worker restart path so a modified module can be tested without reinstalling an entire MCP/LM Studio development package after every change.
5. Run a **standalone CLI harness** against exactly the same capability contract; this separates module research from GUI/agent-loop bugs.

### 11.2 MCP compatibility note

The **2026-07-28 MCP revision** uses a stateless request protocol and introduces `server/discover`; it does **not** forbid persistent application state. Client implementations may support older revisions, so check the **actual host SDK and negotiated version** instead of assuming all MCP clients immediately implement the latest spec. Do not make Cognitum correctness depend on MCP existing at all.

### 11.3 Plugin manifest development lifecycle

`discover -> validate -> load -> health -> run/self_test -> drain -> unload/reload`. The registry changes atomically; in-flight calls complete or are cancelled according to their contract. On failure, roll back to the last known-good module version. Maintain manifest compatibility checks and a tiny development dashboard/CLI showing enabled slots, champion, challenger, schema versions, worker status, and last error.

---

## 12. Optionality and failure testing

With 12 binary plugins there are 4,096 theoretical enabled subsets. Do **not** claim that a 40-config sample proves every possible configuration safe.

**Required subset testing:** core-only; each plugin alone; each plugin removed; critical adapter combinations; challenger-versus-champion swaps; representative pairwise covering arrays; and explicitly declared dependency failures. Record coverage as sampled, not exhaustive.

Additionally test: plugin upgrade and downgrade, corrupted derived indexes, missing schema migration, cancellation, restart under partial writes, denied permissions, no MCP installed, isolated host startup, malformed native/JSON transport payload, module timeout, and misleading tool output. A missing derived index should degrade retrieval quality or rebuild safely—not corrupt canonical records.

Define a **module disable success criterion:** host and core remain bootable; affected requests return accurate limitation reports; non-affected slots continue; no unauthorized fallback executes; stored data remain intact or are recoverable.

---

## 13. Staged build plan and acceptance gates

### Phase 0 — Host boundary and trace contract

**Build:** one native host adapter or minimal standalone host; registry; operation schemas; policy guard; request/result trace; strict null-plugin behavior; dev-mode reload; CLI harness stub.

**Exit gate:** run with all plugins absent; reject invalid schemas and unauthorized operations; reload one toy plugin; verify a trace links request, module version and result. No real solver or research model is needed yet.

### Phase 1 — Three boring baselines

**Build:** `calc` (restricted parser first), `memory` (SQLite/FTS5 + provenance), `state` (events/snapshots/revisions), plus 10–20 smoke tasks and inert replay.

**Exit gate:** arithmetic correctness suite; conflict/supersession tests; crash-recovery and deletion-propagation tests; independent tests with each baseline switched off; read/write grants enforced.

### Phase 2 — Formalization-aware exact adapter

**Build:** one of `verify` or `optimize` based on a real user task. Prefer a small typed operation and known-instance examples before generic Python execution.

**Exit gate:** distinct statuses/outcomes; bad-model test; unknown/timeout path; units/invariant checks; witness or certificate verification where applicable.

### Phase 3 — HDC relation challenger

**Build:** derived relational binding index backed by the same exact SQLite data. Include incremental update and deletion/rebuild semantics.

**Exit gate:** preregistered held-out relational tasks against exact graph/SQLite and derived embedding baselines; memory/energy/time cost measured; negative and null results accepted. No promotion for a retrieval-only story unsupported by results.

### Phase 4 — KAN symbolic challenger

**Build:** small controlled symbolic-regression comparison with PySR and B-spline MLP baseline.

**Exit gate:** formula recovery and complexity comparisons on held-out families at matched resources; no claims about general LLM reasoning from this experiment.

### Phase 4B — One compositional research experiment (optional)

**Build:** choose **one** recovered Section 8A hypothesis (prefer HDC + typed temporal state for continuity with previous HDC work). Build a small, reproducible cross-component dataset and four-way ablation before any shared representation framework.

**Exit gate:** show whether the composite beats strong conventional memory + state and the best single challenger on held-out task correctness at recorded resource cost. Preserve a negative result. A non-win means *do not deploy*, not *ban the research direction*.

### Phase 5 — Expand on demand

Add `prob`, `plan`, `space`, `sim`, `causal`, `verify`, or `optimize` according to actual tasks and feasibility. Park capsules, SSM-in-plugin, MAML, and TDA until the question and baseline are concrete.

**Work rule:** one active research challenger; however, safe core bugfixes, security patches, and baseline maintenance are not artificially blocked by that rule. Keep a claims ledger with `source`, `method`, `result`, `limitations`, `replication`, and `promotion decision`.

---

## 14. First 28 candidate test tasks

These are **proposed templates**, not completed experiments or ground-truth scored cases. Create fixtures, labels, and grading rules before running them.

| ID | Slot | Probe |
|---|---|---|
| T01 | calc | Exact rational arithmetic versus floating approximation |
| T02 | calc | Units and rounding requirements in a multi-step calculation |
| T03 | calc | Malicious code disguised as a math expression |
| T04 | memory | Recall one cited fact from many similarly worded notes |
| T05 | memory | Delete source and confirm all derived indexes stop returning it |
| T06 | memory | Update a claim and handle obsolete evidence correctly |
| T07 | state | Track a decision reversed after 40 turns |
| T08 | state | Detect contradictory project constraints without silent overwrite |
| T09 | state | Concurrent change with stale expected version |
| T10 | verify | SAT instance with a witness and independent checker |
| T11 | verify | UNSAT instance with a missing natural-language constraint |
| T12 | verify | Timeout/unknown without fabricated proof |
| T13 | optimize | Feasible, provably optimal, and infeasible cases distinguished |
| T14 | plan | Action plan that fails when one precondition is omitted |
| T15 | prob | Base-rate calculation with stated priors and likelihoods |
| T16 | causal | Observational association with non-identifiable effect |
| T17 | space | Occluded object reappears with consistent identity |
| T18 | sim | Physical trajectory with dimensional consistency |
| T19 | HDC | Compositional relation query after many incremental edits |
| T20 | system | Denied plugin, injected tool result, no safe fallback |
| T21 | composite | HDC+state multi-hop recall across reversed decisions compared with each alone |
| T22 | composite | Relation recall after removing an object and rebuilding derived indexes |
| T23 | composite | Object identity under disappearance, reappearance, and renamed aliases |
| T24 | surrogate | KAN planner surrogate detects out-of-domain constraints and escalates |
| T25 | temporal | Distinguish real contradictory claims from legitimate rapid topic changes |
| T26 | routing | Compare 4/8/12/20 family or flat tool exposures on same local-model tasks |
| T27 | adaptation | Train-on-past, test-on-future policy improvement with leakage check |
| T28 | integration | Disable each composite subcomponent mid-chain without bad or unauthorized fallback |

---

## 15. Claims ledger, unchanged claims, and unresolved decisions

### 15.1 Carry-forward claims (not independently revalidated)

- Revision 1.2 records pilot-level validation of selected BSC/MAP algebraic operations, indexing/restart checks, and an adapter type-casting issue, with tests summarized rather than supplied. Preserve those as **source-reported evidence pending original report verification**.
- Revision 1.2 reports **negative** lexical HDC retrieval comparisons relative to dense/binarized/BM25 controls on one SciFact setup. Preserve the negative result rather than promote HDC as a retrieval improvement.
- This revision specifies **no new measured benchmark performance** and **no new implemented module**.

### 15.1A Source-level audit status

The original 1.0 static-code findings in Section 1 are **inspection findings**, not results of executing the original full implementation. The original eight-week build plan and per-operation latency targets are planning assumptions, not measured performance. Likewise, a shared universal vector space and the specific hybrid synergies in Section 8A have **no demonstrated win** in the supplied documents. Store all as `open` pending isolated tests.

### 15.2 Decisions to settle in code, not by speculation

1. Which exact Lu native interface should consume Cognitum manifests and typed calls?
2. Where does the canonical shared SQLite store live, and who owns migrations, keys, backup, and deletion?
3. Which capability scopes require per-action user confirmation versus standing local grants?
4. What is the target model's empirical tool-selection accuracy at 4/8/12/20 exposed tools?
5. Which real, privacy-cleared daily tasks become the first labeled gold fixtures?
6. Which verification adapter has the first actual user task worth formalizing?
7. Can plugin workers be safely isolated and force-terminated on the target Windows host?

### 15.3 Decision summary

**Build Cognitum as a plugin-capability and cognitive-integrity layer for Lu (while maintaining a standalone test harness).** Ship a trustworthy core, calculator, canonical memory, typed state, and instrumentation first. Add an exact solver to test formalization. Then run HDC and KAN as measured challengers, and preserve one well-formed *compositional* research study. The objective is a system with reliably improved cognitive behavior—not a mere catalog of wrappers and not twelve speculative claims advertised as finished capabilities.

---

## 16. Source documents and technical references

**Primary user-supplied documents examined for 1.4**

- `hybrid_ai_design.md` — original Cognitum 1.0; 12 module specifications and future-work Section 13; static prototypes not certified.
- `Cognitum_Strengthened_Revision_1.1.md` — optionality, risks, contracts, and implementation tiers.
- `Cognitum_Strengthened_Revision_1_2(1).md` — mature baselines, measurement controls, and two-track design.
- `Cognitum_Critical_Revision_1_3.md` — architecture hardening, epistemic correctness, and Lu integration.

**Previously listed external references from 1.3 (not rechecked in 1.4):**

The following are external technical references, not proof that Cognitum is implemented or that an experimental module wins a benchmark. Recheck SDK compatibility at build time.

- MCP official 2026-07-28 protocol announcement — https://blog.modelcontextprotocol.io/posts/2026-07-28/
- MCP TypeScript SDK version/era compatibility — https://ts.sdk.modelcontextprotocol.io/v2/protocol-versions
- Google OR-Tools CP-SAT solver outcomes — https://developers.google.com/optimization/cp/cp_solver
- Protocol Buffers field presence — https://protobuf.dev/programming-guides/field_presence/
- Protocol Buffers reserved fields — https://protobuf.dev/reference/protobuf/proto3-spec/
- OWASP GenAI / Agentic AI project — https://genai.owasp.org/

## 17. Revision 1.4 change log

- Read and traced the original 1.0 and strengthened 1.1 in addition to 1.2/1.3.
- Recovered the original cross-technology research hypotheses without restoring unsupported claims of guaranteed LLM failure-class elimination.
- Added a static audit of concrete defects in original HDC, capsule, SSM, math-parser, and search code.
- Rejected a universal shared vector space as a system invariant; requires typed geometry/representation and explicit cross-space tests.
- Split **research legitimacy** from **production promotion**. Added systematic A/B/composition ablations and interaction assessment.
- Added seven research protocols with baselines, risk boundaries, and negative controls; added eight benchmark templates.
- Preserved the hardening and Lu host separation already specified in 1.3.

**End of Revision 1.4.**
