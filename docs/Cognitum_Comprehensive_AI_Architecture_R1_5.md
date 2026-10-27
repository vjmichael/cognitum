# Cognitum — Complete AI Technology Architecture, Revision 1.5

**Design baseline:** Cognitum Source-Informed Revision 1.4 (preserved, not overwritten)  
**Design date:** 2026-10-27  
**Classification:** Normative *design proposal* for an optional Lu DLC Core Extension (CE); implementation status is tracked separately  
**Scope:** All 19 ordered technology components, the original 12 scientific research areas, compositional experiments and the host integration/release system  
**Companion documents:** [Technology specifications, C01–C19](design/technology-portfolio-C01-C19.md) and [Research, evaluation, delivery and decision program](design/research-validation-and-delivery.md)

> **Mission:** Enable the transformer already selected in Lu to perform more reliably on tasks requiring accurate computation, explicit persistent context, typed state, verification, search, uncertainty, structured objects and scientifically defensible learned assistance. Cognitum is an optional capability and cognitive-integrity layer, not a replacement model, a new independent agent or a guarantee of general intelligence.
>
> **Non-negotiable invariants:** Lu is the security and execution authority; Cognitum uses native Protobuf internally; data is not silently elevated into permissions or truth; disabled modules degrade honestly; experimental techniques compete with strong incumbents; production promotion is evidence-based; Lu's desktop interface remains customizable and usable independently of all DLCs.

## 1. Purpose, evidence classes and historical continuity

This is a **forward design** consolidating established user decisions, implemented Cognitum components C01–C05, pending C06–C19, and the recovered 12-area research vision. It does not represent the design-only sections as running capabilities. Revision 1.4, original 1.0, strengthened 1.1/1.2 and the critical changes recorded in 1.4 remain historical source material. New implementation decisions should be appended to architecture-decision records; do not rewrite past experimental results.

Evidence must be labeled as one of:

1. **User decision:** binding architectural requirement, even before code exists.
2. **Inspected implementation:** repository file and immutable commit verified by reading code.
3. **Tested behavior:** named test, environment, timestamp and reproducible CI/build run.
4. **Research source:** original published/user-supplied hypothesis or pilot, not freshly replicated.
5. **Proposed design:** not implemented, authorized or validated.
6. **Experimental measurement:** real observations with independent task labels, controls, uncertainty and failure accounting.

Code coverage, a signed message, or a synthetic replay is not proof of scientific gain, publisher honesty, kernel isolation, understanding user intent or a correct natural-language final answer.

### 1.1 Snapshot at design freeze

| Workstream | Verified Cognitum baseline as of the 2026-10-27 main snapshot | Unfinished gate |
|---|---|---|
| C01 Core | Registry, typed capability result, metadata-only tracing, Protobuf native domain messages and developer-authored inert Lu handoff | Approved real Lu installation, model tool mapping and effect-free declaration |
| C02 Security | Bounded Protobuf worker framing, negative security acceptance plan, strict signed host-receipt parser; local launch gate denies | Prove the live Lu+Cognitum worker path, permissions, revocation, OS isolation and cross-platform signed CE acceptance |
| C03 Evaluation | Synthetic arithmetic checks plus Protobuf A/B/C/D benchmark plan and optional-presence metric capture | Genuine matched loaded-model trials and independently instrumented grading/measurement |
| C04 Lu integration | Native Protobuf collector receipt verification against caller-pinned key/nonce/digests | Authenticated Lu telemetry/consent adapter, native CE registration and end-to-end worker |
| C05 Math | Exact rational calculator plus six **bounded, not advertised** scientific reference specialists | Reliable real-model selection and intent checking, independently validated error bounds and production CE exposure |
| C06–C07 Memory/state | Research/design only in Cognitum | Canonical ownership, Lu interoperability, privacy/deletion/versioning tests |
| C08–C09 HDC/KAN | K4 and default-off depth-addon archives recovered and independently CPU self-tested; **not integrated** | Typed derived-index/checkpoint adapters and held-out host baselines |
| C10–C19 Other AI tech | Baseline specification and candidate research, not production code | P0 research, approved dependencies, P1/P2 components and P3 trials |

**Primary source of present implementation evidence:** Cognitum main at commit 7776a423bd9b94bf2848af53b502fda76d601f83, C05 scientific math PR #14, with four-platform post-merge CI run 40465875778 showing 232/232 unit tests, 12/12 legacy replay, 10/10 arithmetic evaluation and 8 compiled Protobuf schema matches **per job**. These are component/test metrics, not end-to-end Lu benchmark scores.

**Important updated Lu observation (read-only):** the Lu branch lu/ce-desktop-consent-typed-validation at 2437c76174f6a67009bb0c9a795773d7663739a0 already contains a supervised **diagnostic** worker with Windows AppContainer/Job Object and Linux isolation, Protobuf validation and native desktop-consent development; the Linux **signed CE** runtime is separately experimental, while its Windows/macOS signed-CE paths fail closed. Lu Core CI run 40466015873 passed the Linux signed CE and Windows diagnostic-worker isolation jobs. The Lu changes remain in staged draft PRs and do **not** prove Cognitum's production path is integrated. Do not repeat the older broad assertion that Lu has no real OS sandbox tests.

## 2. The host boundary is the architecture

### 2.1 Ownership

**Lu Core (mandatory host)** owns: human identity, user/session/conversation and task provenance; selected transformer/provider and model configuration; desktop consent UI; tool catalog visibility and sequencing; typed native ToolCall/ToolReply dispatch; CE trust store, signing-key enrollment/rotation/revocation; scope/effect authorization; OS-level worker supervisor; file/network access broker; cancellation, uninstallation/draining and crash recovery; workspace registration/activation; canonical conversation history; and release security policy.

**Cognitum CE (optional)** owns: mathematical and domain-specific capability logic; narrow domain Protobuf messages; externally reviewable model-use/avoid descriptions; domain-result validation; explicit execution/outcome/assurance/provenance distinctions; opt-in derived indexes; scientific candidate models; independent test harness and research observations. Cognitum must not mint grants or install itself by claiming approval in a message.

**Lu DLC Workspaces** (e.g., full IDE or Film Studio applications) have their own specialized full UIs and registries, composed from Lu Core plus approved reusable CEs. A Workspace can be detached without bringing down Lu or sibling Workspaces. Vanilla Lu remains available and customizable. A Cognitum capability may be offered to vanilla chat, one Workspace, several Workspaces or none, only through Lu host policy. Cognitum is *not* itself a mandatory workspace or an MCP server.

**Canonical memory/state owner:** a **single explicitly agreed** Lu-managed or Lu-authorized domain store, not two independently authoritative ledgers. Lu's existing ANSF/conversation knowledge system must be inventoried before any C06/C07 persistence is built. Cognitum may maintain transactionally consistent derived indexes, caches or specialized state projections; they never silently replace canonical user decisions.

### 2.2 Intended call sequence

1. User requests work in Lu or a specialized Workspace. The selected Lu model may **propose** a tool call.
2. Lu derives authorized session/task lineage, checks capability catalog, user consent, publisher trust, resource scope, model/tool compatibility and allowlist.
3. Lu validates generated external arguments at the model boundary and converts them to an exact **Protobuf** domain request. Unknown/duplicate/semantically invalid fields fail closed.
4. The Lu supervisor dispatches through a real OS-restricted worker for untrusted/effectful code, or through a separately audited in-process trusted mechanism where the policy explicitly permits it. No silent subprocess fallback.
5. Cognitum runs only its assigned bounded operation. It cannot call another CE secretly, select or retrain a different base transformer, write to Lu memory without host authorization, or enlarge requested permissions.
6. Cognitum returns a versioned, typed domain result and *honest* limitations. Lu validates the domain output, maps errors to its native ToolReply outcome and checks stale-call/revocation state.
7. Lu sends only allowed, relevant structured evidence to the selected model. The model synthesizes the answer while keeping computation, data provenance, inferred assumptions and uncertainty distinct.
8. Lu enforces cancellation, drain/recovery, audit redaction, retention and data deletion. No completed call is resurrected after revoke/unload.

### 2.3 Internal serialization: Protobuf is normative

**All native Lu↔Cognitum application protocol messages and domain payloads are binary Protobuf.** This includes discovery plans, operation types, structured results, state/claim revisions, evaluation plans/captures, lifecycle events and integrity references. JSON remains an **external model/API compatibility projection**, never an alternate privileged native messaging protocol. No MCP transport should be created to integrate Cognitum natively into Lu.

Protobuf alone does not implement authentication, canonical semantic truth or secure execution. The Lu host independently binds caller identity, signature identity, CE version and resource scope. Descriptor-backed type URLs must use a tightly reviewed namespace such as type.googleapis.com/cognitum.math.v1.SymbolicRequest. Unknown schema versions and ambiguous field values are rejected. Reserve removed field numbers and enum values; additive changes must be assessed for strict-wire compatibility. Numeric measurements use explicit units and **presence-aware** optional fields; unknown is not zero.

**Required abstract envelope:** operation ID, exact input/output type URL, version, schema/descriptor digest, scoped trace/correlation handle, bounded deadline/cancellation handle, host-authenticated context *out of band*, validated domain bytes, and tagged result/error. This is conceptual, not a proposal to replace lu.v1.ToolCall/ToolReply. Lu retains the actual envelope; Cognitum defines specialist payloads only.

## 3. Cognitive-integrity contract

For every invocation or belief-changing action, keep the following separate:

| Axis | Required reporting |
|---|---|
| Execution | Completed, denied, timed out, canceled, unavailable, validation failed |
| Domain outcome | Mathematically distinct SAT/UNSAT/UNKNOWN, feasible/optimal/infeasible/unknown, bracketed approximate, retrieved/no match, hypothesis conflict, etc. |
| Assurance | Exact within entered model, independently checked witness, numeric approximation with bound/without bound, empirical confidence calibrated/not calibrated, unverified source |
| Formalization | Original user question → approved typed meaning, variable/unit mapping, assumptions, ambiguity, alternative interpretations |
| Provenance | Canonical record revision, dataset checksum, source location/type, simulation/instrument revision, derived-index version |
| Limitations | Incomplete evidence, model intent not verified, OOD, rounding/discretization, missing permissions/sensors |
| Resource/cost | Actual measured time, memory, tokens, energy or cost with absent data explicitly unknown |

**Formalization gate:** The mathematical engine checks *what it is given*, not whether Lu interpreted the user's problem correctly. Typed ranges, dimensional analysis, round-trip representations and counterexample probes help detect mistakes. Consequential/ambiguous decisions may require user's confirmation. Never convert an LLM's uncalibrated self-confidence into a permission grant or proof of correctness.

**Failure is information.** If an exact solver is unavailable, disclose it or use a clearly labeled non-exact route if host policy and task risk allow. If a citation was deleted, do not serve it from stale HDC/embedding indexes. If a proof checker returns UNKNOWN, do not claim UNSAT. If the model cannot call tools reliably, Lu must use a tested structured mediation flow or say the capability is unavailable.

## 4. Security, trust and isolation gates (C02/C04)

1. **Artifact trust:** Publisher identity enrollment and rotation under Lu; pinned hashes/signatures; key revocation invalidates dependent executables, grants, in-flight calls and caches as applicable.
2. **Permission:** Host-derived, scope-bound, expiring rights, effect sets (not a single misleading enum), consent at appropriate risk level and explicit denial of model-supplied grants.
3. **Sandbox:** Per-platform true restricted identities/containers/namespaces, scoped file handles/network broker, no real user profile/credentials inheritance, per-job quotas for CPU/RAM/process/time, strict process descendants reaping and no insecure fallback.
4. **IPC:** Exact Protobuf type URLs, bounded canonical frames, semantic validation, replay/session checks and sanitized errors.
5. **Lifecycle:** Install disabled; verify; enroll publisher; approve scope; activate; execute; cancel/revoke; drain/reap; detach; recover. Restart cannot resurrect trust or an expired grant.
6. **Provenance:** A signed worker receipt proves only that a specified signing key signed bytes; it is not a substitute for independent kernel observation or an authenticated collector.
7. **Defense-in-depth:** Reject dangerous inputs, large parameters and unexpected data in Cognitum even when Lu has already authorized the tool.

**C02 gate state:** still **closed for production Cognitum workers**. Lu's passing diagnostic Windows/Linux tests are meaningful *partial* host evidence; signed arbitrary CE cross-platform execution, Cognitum-specific permission-to-worker-to-revocation tests and actual desktop integration are separate acceptance criteria. A test-only Cognitum calculator or math-reference function must not be reclassified as a permitted third-party worker.

**Trust/evidence separation:** (a) payload schema validity, (b) trusted signer identity, (c) authenticated host provenance, (d) proven OS confinement and (e) scientific task correctness are five different claims. None automatically implies the next.

## 5. Data architecture: canonical context, memory and revision

**Initial default proposal pending Lu agreement:** use Lu's single canonical conversation/ANSF history and profile/workspace identity as source of truth. Add a transactionally controlled claim/state layer through Lu-owned grants or an explicitly named delegated storage service. Cognitum runs retrieval, revision checks and *derived* relational indexes; it does not silently fork user memory into a second conflicting source.

Every claim/event needs: stable claim ID; subject/predicate/value with typed schema; source identity + source revision; observed/asserted/valid times; scope and access policy; asserted/by-whom, verified state, supersedes/contradicts/retracts edges; confidence **only when calibrated**; cause of transition; redaction/deletion tombstone; retention limit and store schema version. An event log may be append-only for audit, but it must not preserve user-erased sensitive content indefinitely; deletion must cover indexes, caches, backups and replicated exports under a documented retention policy.

**Update pattern:** read expected revision → validate user/host authority → propose new event → atomic compare-and-set update → append scoped provenance → update materialized current state → invalidate affected FTS/embedding/HDC/scene indexes → record acknowledgement. Multi-source disagreement is represented explicitly, not last-writer-wins hallucinated truth. Imported documents and model guesses have different epistemic labels from a confirmed user decision.

**Safe retrieval:** filter by user/workspace scope **before** ranking, prevent deleted/tombstoned content in candidates, resolve canonical revision after approximate index hits, redact evidence delivered to models, refuse stale derived indexes if consistency is required. Logs should contain metadata-only traces unless separate content collection consent exists.

## 6. Universal component lifecycle and manifest

Every C01–C19 component, including a derived index, learned candidate or scientific solver, follows:

- **P0 — Research/design:** task and falsifiable hypothesis; authoritative/incumbent controls; relevant published standards and licensing; boundary, data provenance, representation and operational risks; scoped Protobuf I/O; CPU/GPU/FPGA and other workload/hardware analysis; success metric, real-data/consent requirements and stopping rule.
- **P1 — Build:** audited implementation or thin optional adapter to mature library; bounded runtime/dependencies; strictly typed inputs/outputs, schema version and error codes; reproducible fixtures; no hidden permissions or undisclosed model switch; documented feature-disabled path.
- **P2 — Verification:** positive/negative/adversarial semantic tests; malformed Protobuf, timeout/denial/revocation/crash/restart; platform applicability; independent oracle where feasible; degradation when plugin missing and derived data stale; CI and artifacts with exact commit hash. A **test-only** reference path cannot prove safe production execution.
- **P3 — Evaluation:** real Lu-selected-model end-task trials with a competent existing-tool comparator and unaugmented control, matched task/model/environment budgets, honest unavailable-arm treatment, independent outcome grading, uncertainty, latency/energy/memory costs, adverse effects, replication and explicit promotion decision.

**Minimum manifest attributes:** canonical component/module ID; version + descriptor hash; family/operation IDs; exact request/result type URLs; domain semantics and applicability; pure/effect set + resource scopes; module dependency DAG; source and signer lineage; optional runtime and hardware requirements; limits/quotas; feature flags; health/readiness; schema migrations; responsible maintainer; test/benchmark evidence IDs; use/avoid guidance; fallback disclosure.

**Lu-owned model visibility:** do not advertise all nineteen families to a context-limited model at once. Start with a bounded, host-approved catalog filtered by actual task, model compatibility, trust/grants and cost. Lu currently caps its reviewed model-visible tool catalog at 16 entries. Benchmark flat versus family-grouped exposure and explicit user-triggered operations before adding learned routing.

## 7. Hardware and computational portability

**Selection policy:** CPU is the correctness/reference baseline, not a permanent ban on accelerators. Assess **CPU, GPU, FPGA and other relevant architectures per component**. The winning platform depends on real workload size, data movement, precision requirements, native driver/runtime dependencies, memory capacity, thermal/power budget and developer maintenance cost. Do not claim future R9700/FPGA/ASIC performance from CPU-only tests.

| Workload class | Baseline / first build | Candidate accelerator and evaluation question |
|---|---|---|
| Small exact arithmetic, SMT, planning trees and transactional stores | CPU with deterministic reference tests | GPUs/FPGA rarely justified for tiny branching/rational tasks; compare whole-task overhead first |
| FTS/BM25, compact HDC binding and incremental graph updates | CPU SIMD/bit packing/SQLite; correctness under revision | GPU/FPGA for *large batches* only if memory-transfer cost and update latency justify it |
| Dense/binarized embeddings, KAN/SSM training, learned perception | CPU reproducibility baseline; accelerator optional | GPU throughput/VRAM/energy and precision; compare equal hardware-budget fairness |
| Large sparse/dense linear algebra and optimization | CPU mature library, accurate constraints | BLAS/GPU only after representative matrices/solver thresholds justify dispatch |
| Numerical PDE/ODE and physical simulations | CPU validated integrator and units | GPU/FPGA vectorized solver experiment subject to physical error/invariant tests |
| Derived multimodal object representations | Typed scene graph plus CPU geometry | Optional GPU vision/video indexing in consented Workspace; still keep canonical IDs exact |

**Measurement:** capture warm/cold paths separately, p50/p95/p99 latency with errors, hardware/software versions, sustained memory, peak VRAM, power sampling integral and idle-matched energy, token overhead, batch sizes, JIT/load/warmup and instrumentation uncertainty. A separate GPU driver or CUDA dependency cannot become a silent prerequisite for all of Lu.

## 8. Privacy, safety, openness and portability

- Offline-first local inference/retrieval is preferred; explicit network operations, remote model endpoints and data transfers remain Lu-scoped permissions.
- No automatic microphone/screen capture, desktop surveillance, model weight modifications, fine-tuning or private trace retention. Future learning features require explicit consent, retention/deletion rules, holdouts and stop controls.
- Credentials, raw conversations and complete private task data never belong in provenance signatures or default logs. Signed hashes are metadata, not permission to publish underlying artifacts.
- Composable components must be unloadable, restartable, version-isolated and usable without forcing all dependencies to install. Graceful degradation is **clear unavailability or a safe qualified fallback**, not fabricated output.
- Record open-source license, transitive dependencies, native binaries, checkpoint licenses, export restrictions where relevant, supply-chain signatures and reproducible build inputs before redistribution.
- No hidden MCP requirement, Docker or WSL prerequisite is imposed by Cognitum's architecture. If an OS cannot meet real worker confinement, keep effectful/untrusted execution unavailable on that OS.
- Provenance of user-owned archived K4 HDC/KAN experiments stays intact; neither public GitHub upload nor implied license transfer follows from read access.

## 9. Reading and maintaining the complete design

The [technology portfolio](design/technology-portfolio-C01-C19.md) is the **normative functional specification** for all nineteen components, preserving the original 12-area research agenda, including capsules/object representations, Neural ODE, MAML and TDA. The [research and validation program](design/research-validation-and-delivery.md) supplies cross-component experiments, controlled benchmark methods, reproducibility cards, risk register, acceptance gates and open design decisions.

**Precedence:** explicit user decisions and audited Lu host contracts → approved architecture-decision records → Cognitum core invariants → accepted component interface versions → source-informed Revision 1.4 historical hypotheses. A design proposal cannot override a host security check or user memory deletion.

**Change policy:** append an ADR for material changes to model selection, source-of-truth ownership, permission semantics, Protobuf type URL, data retention, benchmark claim or deployment path. Run contract and security tests first; require P3 matched-task evidence to enable a research challenger by default.

**Bottom line:** finish designing all technology families now, but implement and promote them one **justified, testable, host-authorized** capability at a time. Scientific ambition and strict operational evidence are compatible.
