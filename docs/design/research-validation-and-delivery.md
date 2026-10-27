# Cognitum Revision 1.5 — Cross-Technology Research, Verification and Delivery Program

**Design type:** executable research and engineering acceptance **plan**, not completed experimental findings.  
**Companions:** [Master architecture](../Cognitum_Comprehensive_AI_Architecture_R1_5.md) · [C01–C19 technology portfolio](technology-portfolio-C01-C19.md) · [Historical 1.4](../sources/Cognitum_Source_Informed_Revision_1_4.md)  
**As-of:** 2026-10-27. Cognitum's C01–C05 test successes and Lu draft-branch security tests do not validate future scientific claims.

## 1. Scientific philosophy: integrative research without inflated product claims

Cognitum has two lanes with distinct outputs:

**Production-adapter lane:** reliable, minimal, audited capabilities with strong conventional incumbents. The first production candidates are exact math, existing Lu-owned canonical search/memory and typed revisioned state. The system may remain useful even when no learned challenger wins.

**Scientific-challenger lane:** optional investigations into HDC, KAN, learned temporal representations, object-centric reasoning, learned dynamics, TDA and multi-component synergies. A negative result is useful research and is preserved. Research is never prohibited because an incumbent is currently superior; **default deployment is withheld** until an actual task benefit is reproduced.

Only **one active high-variance research hypothesis** should consume the project’s main research/benchmark capacity at a time. Safe infrastructure, security fixes, memory integrity and ordinary component tests may proceed in parallel.

Do not equate **correctness of a tool call** with correctness of the original natural-language problem, or **the AI's explanatory confidence** with scientific calibration.

## 2. Cross-component hypotheses and preregistered ablations

Each composition is a Lu-owned **typed task DAG**. Each step consumes explicit Protobuf artifacts with source revisions, scopes and method versions. No specialist secretly invokes another CE, accesses new source files or changes a selected model. A composed experiment is optional and teardown-safe.

### R01 — HDC + canonical temporal state (priority first research composition)

**Hypothesis:** Relational hypervector retrieval conditioned on revisioned temporal project state yields more accurate **current** answers on multi-hop questions after decision reversals than a strong exact state + SQLite/graph/BM25/embedding baseline.

**Arms:** A Lu model + exact canonical state; B same + conventional full-text/graph state retrieval; C same + HDC-derived relation index only; D HDC index + typed state transitions. Add conventional graph + state composition as separate strong control. The **synergy interaction** must exceed each single challenger and the conventional composition, at adequate confidence, after accounting for stale/deleted evidence.

**Dataset:** predeclared 2–6 hop questions with revisions/retractions, ambiguous aliases, entity renames, deleted records, concurrent updates and past/present qualifiers. Preserve exact canonical answer and source revision, and split by project/time to prevent near-duplicate leakage.

**Metrics:** current-answer accuracy, false citation, deleted-content leakage (critical zero-tolerance gate in acceptance testing), false contradiction, source-revision correctness, update cost, p95 latency, RAM and energy. **Failure:** HDC returns an old user preference after deletion; derived index must fail closed.

**Stop/go:** do not promote if conventional graph+state matches or beats accuracy at lower total cost, or if tombstones leak; archive negative outcome without treating HDC itself as useless.

### R02 — HDC + object/scene continuity

**Hypothesis:** Versioned relational binding helps preserve persistent object identity under occlusion, aliasing and scene edits, above a deterministic scene graph + conventional tracking/embedding.

**Arms:** scene graph, graph+ordinary perception embeddings, graph+HDC binding, optional graph+HDC+temporal event state. Exact object ID and coordinate frames remain canonical; approximate matches are candidate links only. Use consented synthetic scenes and approved Film Studio Workspace data.

**Tests:** disappearance/reappearance, mirrored scenes, identical objects, identity swap, coordinate transforms, deletion, conflicting modalities and moved geometry. Report IDF1/association accuracy, false reidentification, provenance, memory and frame latency. Do not claim learned capsule equivalence.

### R03 — KAN surrogate for numeric solver or simulator

**Hypothesis:** A verified-domain KAN predicts repeated bounded numerical quantities at lower latency/energy than a full solver while meeting an explicit error threshold and detecting OOD regimes.

**Arms:** exact/reference solver, conventional interpolation/regression, MLP/B-spline MLP and KAN; for host outcomes compare model+solver versus model+surrogate+fallback. Fix train/validation/heldout split, preprocessing/checkpoint hashes and hardware budget.

**Tests:** interpolation, extrapolation, discontinuities, boundary perturbations, units, missing numeric features, checkpoint drift, OOD false negatives and forced escalation to exact solver. Score worst-case error, validated interval coverage if supported, OOD detection, fraction escalated, training/inference energy and end-user task correctness. A learned predictor **cannot certify constraints**.

### R04 — Learned temporal state / SSM or Neural ODE

**Hypothesis:** On labeled temporal dynamics, a learned sequence model improves prediction or anomaly detection beyond event-sourced state and appropriate conventional filters.

**Arms:** typed event log (C07), Kalman/HMM/classical filter where appropriate, generic sequence baseline and learned SSM/Neural ODE. Train/test separated forward in time; no use of future events to construct input features.

**Tests:** abrupt reversals, irregular sampling, missing observations, covariate shift, long-range dependencies and semantically benign topic switches. Score future prediction, calibration/OOD, false anomalies, resource cost and state consistency. Do **not** infer contradiction from oscillatory random latent dimensions.

### R05 — Multimodal spatial and temporal memory

**Hypothesis:** An explicit object/event graph, synchronized multimodal provenance and optional derived representations improve queries over long videos or scenes beyond a caption-only LLM and conventional tracking.

**Arms:** caption/model-only; scene graph+temporal association; baseline embeddings+graph; optional HDC/SSM or learned object challenger. Only use media explicitly provided to the authorized Lu Workspace; ingestion and retention remain consented.

**Tests:** occlusion, source-time mismatch, falsely synchronized events, changed viewpoints, duplicate objects, deleted footage, unseen categories, adversarial captions and temporal ambiguity. Metrics include evidence-timestamp agreement, temporal ID accuracy, question correctness, privacy and VRAM/latency.

### R06 — Learned capability routing for local models

**Hypothesis:** A task-aware, policy-constrained selector can reduce wrong and missed tool calls as the catalog expands.

**Arms:** flat exact Lu catalog, curated family tools, deterministic host rules, learned candidate scorer. **Never** give a scorer authority to bypass Lu allowlists, publisher trust, permission, budgets or user consent.

**Tests:** 4/8/12/20 described capabilities, confusing near-synonyms, adversarial tool descriptions, invalid JSON-to-Protobuf input, unavailable tool, injected source instructions, and no-tool cases. Score end-task outcomes, wrong/missed calls, request repair failures, added tokens/latency and hallucinated claims. The output is advisory ranking only.

### R07 — Consented learning from errors and traces

**Hypothesis:** A narrowly trained capability-selection or error-prediction policy, learned from past non-sensitive outcomes, improves future tasks without leakage, privacy loss or regressions.

**Arms:** frozen deterministic policy, ordinary tuning on development data, optional meta-learning or approved learned policy. **Never** train the selected transformer or Cognitum checkpoint merely because chat transcripts are available. Use explicit opt-in; keep data labels, sources and erasure obligations.

**Tests:** forward-chained future holdout, hard negatives, poisoned traces, deletion requests, source drift, false reward signal, rollback, off-switch, catastrophic forgetting and repeatability. No self-approved promotion; signed trial records are claims until trusted source provenance exists.

### R08 — Optional scientific math composites

**Hypothesis:** Domain-aware combination of exact arithmetic, symbolic checks, interval enclosure and numerical simulation catches more **formalization or numerical errors** than one math engine without unacceptable latency.

**Arms:** ordinary calculator, established SciPy/SymPy/verified solver, Cognitum single specialist, and a declared composition (e.g. symbolic derivative + numerical value + domain check). Keep solver certainty and model formalization validation separate.

**Tests:** missing/ambiguous units, multiple roots, ill-conditioned matrices, incorrect model physical assumptions, numeric precision loss, false invariants, tool refusal and cancellation. Attribute observed gains to **which stage** caught an error, not just to adding more modules.

## 3. Experimental design protocol: no convenient winner selection

### 3.1 Before gathering results

Preregister:

- The user-visible task, supported domain, gold answer and authoritative grading source.
- Hypothesis and its intended advantage (accuracy, unique capability, efficiency, privacy, safety).
- Controls A (bare Lu model), B (competent conventional tool), C (Cognitum specialist) and D (declared composite) where available. If one arm cannot run, mark NOT_RUN and do not claim a complete four-way win.
- The loaded Lu model identifier **and exact weights/checkpoint hash**, backend and quantization; Lu/CE builds, tool catalog revision, prompts/context, sampling temperature/top-p/seed, tool/time budget and hardware/platform.
- Dataset origin, licensing, consent/privacy class, train/development/test split, contamination checks and scorer version. Simulated labels remain labeled synthetic.
- Primary endpoint, minimum meaningful effect, adverse-effect guardrails, uncertainty interval and **stop/go** rule; secondary outcomes; subgroup analyses fixed before results.
- The prospective number of cases and repeats with a power or uncertainty rationale. A 10-case smoke pass is not a population estimate.

**Protobuf design:** C03 BenchmarkPlan/BenchmarkCapture already specify matched arms and optional presence-aware metrics; C04 receipt binds bytes to declared collector identity and hashes. Before real trials, Lu must add **independent provenance**, secure nonce consumption, actual telemetry and trusted scoring; the signed receipt alone is not evidence of genuine execution.

### 3.2 A/B and factorial analysis

For a single candidate C versus B, compute paired per-task difference in correctness and paired latency/cost. Report counts, confidence intervals and method for ties/missingness. Do not pool unavailable arms into denominator, and distinguish technical failure from an appropriate abstention.

For two-component synergy, use a **2×2 factorial** on the same tasks:

| Neither | Component 1 only | Component 2 only | Both |
|---|---|---|---|
| Y00 | Y10 | Y01 | Y11 |

The interaction estimate on the chosen outcome scale is **Y11 − Y10 − Y01 + Y00**. A positive raw outcome in Y11 does not establish synergy if the stronger component or conventional composition already achieves it. Predeclare metric scale, uncertainty calculation and how ordering/tool-budget effects are controlled. For task quality, measure the full answer—not just a convenient intermediate kernel.

Evaluation order should be randomized/counterbalanced with independently recorded allocation seeds; fixed rotating schedules help reduce systematic order bias but cannot alone guarantee blinding. Independent graders must not see hidden arm labels or unsupported model reasoning when feasible. Preserve failures and unsuccessful candidate runs.

### 3.3 Benchmark tiers

| Tier | Use | Status claim |
|---|---|---|
| S0 Contract/unit | Protocol and domain semantics under pinned fixtures | Correct within tested fixtures, **not** model benefit |
| S1 Synthetic smoke | 10–20 safe artificial or public cases | Harness/debugging only |
| S2 Development | Labeled domain challenge set and real representative user tasks | Tuning and regression, not held-out promotion |
| S3 Held-out | Pre-registered independently graded paired tasks; initial planning target 100+ per slot subject to variance/power | Eligible for limited evidence claim |
| S4 Replicated | Fresh seeds/models/tasks/hardware and adversarial failure classes | Eligible for recommendation under trust/security gates |
| S5 Release monitoring | Consented production-like exposure with rollback triggers | Eligible for default-on only when optionality/revocation is proven |

These are **evidence categories**, not guaranteed statistical sample-size formulas. Safety-critical unauthorized effects require targeted negative tests beyond routine end-task accuracy.

### 3.4 Primary risk guardrails

No default-on release if **any** of these occurs in acceptance scenarios: unauthorized access, cross-profile leak, deleted record returned as current, unreaped hostile process tree, valid late reply accepted after revoke, silent tool failure represented as success, unverified SAT/UNSAT/OPTIMAL claim, copied private data into logs, or hidden model/provider substitution. A research benchmark win does not override these release blockers.

## 4. Reproducibility record and honest metrics

Every experiment retains a typed run manifest with: git commit; OS and Lu build; CE package/publisher identity; dataset and scorer SHA; model weights/quantization/backend; prompt context; parameter settings; exact operation descriptor hashes; source revision and trust/sandbox status; generator seed; consent/privacy class; CPU/GPU/FPGA model/driver; measured hardware utilization; dependency lockfiles; warm/cold and concurrent load; permitted trace retention; trial schedule; failures/denials; and evaluator code hash.

**Accuracy:** report grounded final answer and independently checked math/proof/witness separately from the model's intended formalization. Record calibration and appropriate abstention. For retrieval, include citation source correctness, revision recency, deletions and cross-workspace denials. For scientific simulation, distinguish model error, discretization error and observation error.

**Latency:** end-to-end turn completion and tool-internal time must not be conflated. Capture time to first token, process startup/sandbox setup, model inference, validation, IPC, computation, retries and overhead separately if actually instrumented. Unknown clocks and missing fields remain absent.

**Memory and energy:** peak RSS/cgroup/Job Object utilization, GPU VRAM and power sampling methodology. Report measured joules per task from time-integrated power with idle-matched baselines, meter resolution, concurrency, thermals and uncertainty; do not infer energy just by multiplying nominal TDP by duration.

**Reliability:** timeouts, failures, denied/canceled/revoked calls, inability-to-formalize events, resource exhaustion and checkpoint/restore failures are denominators, not hidden exclusions.

**Privacy:** no default raw prompts in traces or signed receipts. Use opaque source handles and opt-in, scoped, erasable local artifacts.

## 5. P0–P3 dependency and stage plan

### Lane A: safely usable baseline

| Order | Acceptance milestone | Gate |
|---|---|---|
| A1 | Finish Lu native CE effect-free/effectful definitions and model-visible semantic validation | Lu host review; no self-approved Cognitum metadata |
| A2 | Complete C02 end-to-end sandbox acceptance on the **actual Cognitum** worker path | Signed package and host consent, file/network/handle denial, child reaping, cancel/revoke/restart; OS-specific pass |
| A3 | Integrate **one** bounded C05 exact calculator through true Lu ToolCall/ToolReply | Chosen model correctly uses/declines it and sees honest result limitations |
| A4 | C03 trusted collector + independent grader for A/B/C comparisons | Genuine matched task measurements, not synthetic signed shapes |
| A5 | Decide C06 canonical store ownership with Lu and implement revision-aware retrieval | Cross-profile security, update/deletion/restart tests |
| A6 | Implement C07 typed claim/state revision on that *same* canonical authority | Long-turn decision reversals, stale versions, retract/conflict tests |
| A7 | Promote selected C05/C06/C07 capabilities only if end-user quality improves safely | P3 preregistered controls and no safety regression |

### Lane B: broad conventional expert adapters

Choose C10 SMT/proofs, C11 optimization, C12 planning, C13 probability, C14 causal analysis, C15 scene geometry, C16 general physical simulation as specific task demand emerges. Each module is independent where feasible. **No requirement** to implement all at once or force-install SciPy, SymPy, solver distributions or GPUs. Scope consent, licensing, hidden effects and packaging per optional CE.

### Lane C: original AI research portfolio

C08 HDC relation index → C09 KAN fit/surrogate → optional R01 HDC+state factorial study → C17 SSM, C18 meta-learning, C19 TDA and capsule experiments according to **specific falsifiable tasks**. The recovered K4 archive and depth overlay stay immutable and default-off; only approved, checksum-linked copies are converted into Cognitum adapters. Preserve original owner-reported pilot comparisons, including negative retrieval results, as evidence with source tags.

### Lane D: specialized Workspaces

Film Studio may consume C07 typed scene decisions, C15 scene graph and selected C16 simulators; IDE Workspace may consume C05, C10–C12 and approved analysis tools. Workspaces are full separately installable application environments with their **own UI and registry**, not mandatory panels. Cross-workspace data transfer requires approved Lu authority and stable content/event handles; unloading one Workspace does not unload the shared Lu Core.

## 6. Implementation delivery checklist (applies to every technology)

For every component, complete and attach this acceptance sheet:

- **P0:** concrete task/use case; formal input/output/restrictions; research/literature and library/standards comparison; CPU/GPU/FPGA assessment; incumbent and unique hypothesis; privacy/license/host scope; risk and stop rule.
- **P1:** typed domain Proto source + generated descriptors; capability metadata reviewed by Lu; opt-in dependencies; secure reference logic; bounds on length/nodes/precision/iterations/resources; stable error classification; dependency and data ownership declaration.
- **P2:** cross-platform (where supported) compiler/source field compatibility, semantic/negative/malformed/failure tests, static code audit, independent oracle, startup/teardown, missing component, optionality, restart/deletion/revocation and worktree-safe CI.
- **P3:** preserved A/B/C/D capture with real Lu selected model, credible B comparator, scored held-out tasks, confidence/uncertainty and per-class failures; measured costs; scientific outcome and promotion decision; report all nonresults and unavailable dependencies.
- **Release:** install disabled by default; signer trust, publisher revocation, OS confinement, scoped consent, runtime recovery and rollback; provenance and deletion policy; exact component version and documented limitations.

A development document can satisfy **P0 design**. It does **not** satisfy P1 code, P2 security or P3 empirical benchmarking by its existence.

## 7. Risk register and mitigations

| Risk | Severity | Owner / mitigation | Can design alone close it? |
|---|---|---|---|
| Privilege escalation through model/worker-controlled authority | Critical | Lu; host-only identity, consent, grant broker and OS isolation | No |
| False claim of verified OS sandbox from signed receipt | Critical | Lu+Cognitum; independently execute hostile-worker probes, key custody, nonce consumption | No |
| Duplicate canonical memory ledgers and conflicting truth | High | Lu/Cognitum ADR on one authority; snapshot/revision/tombstone semantics | Ownership decision needed |
| Private/deleted source reappears via derived embedding/HDC cache | Critical | Canonical check on retrieve, deletion fan-out, rebuild and adversarial tests | No |
| Solver accuracy mistaken for intent/formalization correctness | High | Typed formalization gate, units/risk-based confirmation, end-task grading | No |
| Tool-routing noise saturates selected model context | Medium–high | Lu cap/family catalog; benchmark context and wrong selection | Requires real model |
| Train/test contamination and reward hacking | High | Frozen splits, independent grader, forward holdout and provenance | No |
| Learned approximation misrepresented as exact/certified | High | Domain assurance and explicit error/OOD labels; fallback to reference | Needs code/tests |
| Unbounded symbolic/numerical workload | High | Input grammar/resource limits, OS quotas, cancel/timeout | No |
| Unsupported accelerated platform or hidden driver prerequisite | Medium | Portable CPU incumbent, per-component hardware matrix and opt-in extras | No |
| Multi-step composition silently widens permission | High | Lu-host typed DAG with explicit step grants and budgets | Requires host enforcement |
| Tool or dataset licensing/provenance not distributable | High | Source audit, redistribution manifest and immutable owner archives | Requires diligence |

## 8. Unresolved decisions and required ADRs

These decisions are **not** silently settled by a design author. Proposed owner and resolution test are stated explicitly.

| ADR | Open question | Proposed owner and acceptance decision |
|---|---|---|
| ADR-01 | Who owns canonical user/project memory and versioned beliefs? | **Lu + user:** map ANSF, canonical storage and granted Cognitum projections; delete/update test |
| ADR-02 | How does Lu register an effect-free math operation without claiming a workspace read? | **Lu Core:** true pure/no-effect semantics and host schema validation |
| ADR-03 | What exact Lu native CE package ABI/version and signature policy may Cognitum use? | **Lu Core:** installer/trust/rotation/revocation tests, no MCP or duplicate agent |
| ADR-04 | Which platforms have production signed-worker OS confinement for arbitrary CE binaries? | **Lu:** platform-matrix hostile-worker acceptance, no unsafe fallback |
| ADR-05 | How is user consent linked to real desktop user turns and scoped resources? | **Lu:** native dialog, replay/idempotency, worker/call revoke |
| ADR-06 | How are Benchmarks' raw task/gold labels stored, and who authenticates tool events/graders? | **Lu+Cognitum:** consented local capture/independent grader, P3 evidence |
| ADR-07 | Which model adapter handles selected transformers without native tool calling? | **Lu:** tested structured mediation or explicit unavailable |
| ADR-08 | What source license/redistribution permits K4-derived code or checkpoints? | **User + Cognitum:** preserve archive checksums, inspect licenses before public redistribution |
| ADR-09 | Which C10–C19 domains have a real initial user's task worth implementation cost? | **Product/research review:** prioritize evidence and user value, not numerology |
| ADR-10 | Which tasks justify accelerator variants or learned representation translation? | **Cognitum P0/P3:** per-domain CPU/GPU/FPGA comparisons with cost/precision |
| ADR-11 | Which scoped user/Workspace events may be remembered or used for training? | **Lu + user:** opt-in, consent, retention and erasure tests |
| ADR-12 | What minimum effect and uncertainty allow optional→recommended→default promotion? | **C03 evaluator + product owner:** preregister per-domain utility and safety thresholds |

## 9. Phase/milestone closure definition

**Design complete** means: all 19 modules have a well-formed scope and testable interface concept, original twelve areas and composites are accounted for, current implementation status is separated from plans, security/memory authority is assigned or explicitly unresolved, test/benchmark methodology and genuine dependencies are recorded, and outstanding owner decisions have traceable ADRs.

**Implementation complete** means much more: actual Protobuf source and code, verified authority boundaries, real OS-safe runtime, CI and independent representative task data. **Research benefit established** means preregistered end-task evidence against credible baselines, replication and uncertainty reporting. The phrase “finish the design” **must not be promoted** into “all AI technology is built” or “C02 is production ready.”

## 10. Immediate next engineering package (deferred until host authorization)

1. Recheck current Lu draft PR head and actual runtime interfaces read-only; identify the minimal approved effect-free C05 host bridge, publisher/trust and signed Windows CE status. Document precise blockers and correct older Lu addenda without modifying Lu.
2. Prioritize **real C02 + C04 integration** on one calculator using a Lu-owned secure sandbox and desktop consent; do not turn on six scientific specialists first.
3. Add a genuine Lu collector + independent data-quality/scorer oracle for a small honest model benchmark, proving no forged bytes become authenticated execution.
4. Settle **C06/C07 single canonical memory/state** ownership using Lu's real ANSF records and deletion lineage, with explicit approved migration before any persistent Cognitum store.
5. Only then execute the first preregistered HDC relation challenger against graph/FTS controls, reusing the preserved K4 source and, optionally, KAN research where tasks justify it.

**Final research rule:** pursue substantial new architectures without making stronger claims than the available evidence. Successful negative experiments, exact reproducible artifacts and traceable safety constraints are part of the project's contribution.
