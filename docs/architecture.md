# Architecture and boundaries

**Active implementation roadmap:** [Component development lifecycle and tracker](roadmap.md). Every component now follows its own P0 research/standards/hardware survey, P1 implementation, P2 smoke testing, and P3 standard-baseline benchmarking. Historical global phases from Revision 1.4 are retained as archival design input, not the execution schedule. Existing prototype verification is reusable evidence, not automatic P3 certification.

Host proposes an explicit operation → registry chooses its nominated enabled provider → core validates operation input → deterministic policy authorizes → worker executes → core validates output → structured response and trace return to host.

The host owns conversations, identity authentication, consent, natural-language formalization and synthesis. Cognitum has no model client, agent loop, scheduler, desktop observer, network server or transport dependency. The future Lu interface is `Runtime.call(Request, HostContext) -> Response`; Lu must construct trusted context after authenticating the user. A model or retrieved document must never construct that object. The Python interface is local, not an authenticated remote API.

**Project boundary:** In this Cognitum repository, Lu code and configuration are **read-only**. Required Lu-side support is tracked as proposals in the [DLC Core Extension Addendum Register](lu-dlc-ce-addenda.md), to be evaluated and implemented only by the separate Lu development project. Cognitum is an optional Lu-native **Core Extension**, not a mandatory base-core dependency or specialized DLC Workspace.

## Lu-controlled transformer collaboration (user decision, 2026-10-26)

**Normative host/augmentation contract:** [Lu × Cognitum — Transformer-Centered Collaboration](lu-cognitum-integration.md). **Lu controls whichever transformer is loaded or selected**, including model/provider lifecycle, capability advertisement, chat/agent loop, session and workspace, tool dispatch, authorization and final response. Cognitum components provide **optional, typed, bounded cognitive services** to that host; they do not replace the transformer's conversational role, silently modify model weights, create a competing agent loop, or independently grant permission.

The selected transformer may propose operations and interpret their returned evidence, but **Lu policy determines whether a request may execute**; Cognitum's local registry resolves an explicitly nominated enabled provider *within* a host-approved capability. Model/tool interoperability must follow existing Lu-native CEs and dispatcher contracts. Structured results return with outcome, assurance, provenance, failures and limitations, and the host/model must preserve these distinctions. **Production value must be benchmarked on Lu + the selected transformer** relative to host-only and strong conventional tools; component-only measurements are necessary but insufficient.

## Contracts

The envelope follows Revision 1.4's contract label `1.3.0`, with an intentionally reduced Phase 0 surface. Exact contract and operation-schema version equality is required; there is no speculative compatibility range. Canonical frozen Python contract objects generate JSON Schema for operation input/output. `Shape` supports only closed objects of required bounded strings; it is not a full JSON Schema engine. Add a reviewed typed schema implementation before memory/state/solver structures require richer types. Do not silently accept unsupported schema features.

Manifest snapshots include plugin version, operation schema versions, input/output hashes, declared effects, determinism, assurance and research track. The calculator's exact value lives in the operation-specific result, independent of execution status. Assurance applies only to the formal expression. Interpretation remains assumption-bound: this core cannot verify whether a natural-language request was translated correctly. No calibrated confidence or proof claims are emitted.

The manifest compatibility golden file is checked in; updates require deliberate review. It is a fixture, not a cross-language conformance claim. No Protobuf, MCP, or Lu converter has been implemented. Add those only after inspecting the actual host's source/contracts.

## Lifecycle and concurrency

`Registry.install` constructs a trusted provider, validates its manifest and runs health/self-test before swapping a single immutable entry under a lock. Validation failure leaves the prior entry intact. Explicit champion nomination avoids provider-order routing. No automatic research promotion exists. Research providers require explicit trusted opt-in and nomination; ordinary CLI operation never enables them.

An admitted call holds its old entry snapshot. Disabling or replacing a plugin affects subsequent admissions; an in-flight call completes or reaches its deadline. Reload is explicit class replacement; Python source hot-reimport, cancellation tokens, dependency graphs, drain management and rollback after a later execution failure are not implemented. Factory classes must be top-level/importable for Windows spawn.

## Permissions and isolation

Effects are sets of exact `(kind, scope)` pairs, compared to trusted host grants after identity/workspace checks. No glob/path-prefix matching is attempted; host adapters must later resolve canonical path/domain scopes and enforce them in an OS boundary. All effectful operations remain denied even with a grant, because this starter has no scoped execution boundary. This intentionally prevents a placeholder permission check from enabling real writes or transmissions.

Plugins, manifests, lifecycle hooks and worker factories are trusted installed Python code. Their declarations are not evidence of actual behavior. A plain worker process can access the user's files/network and is NOT a sandbox. Lifecycle hooks run in the parent and can block; the trusted plugin assumption is essential. The calculator is safe by restricted grammar and bounded computation, not by process privilege reduction. No dynamic untrusted plugin loading is exposed.

Worker timeouts include spawn startup and execution wait, with bounded termination cleanup overhead afterward. The worker is terminated and joined on timeout. CPU/memory quotas, descendants containment and session budgets are not implemented. The output size check happens after IPC deserialization; it cannot contain a hostile Python provider or oversized serialized message. Do not install adversarial providers into this runtime. Before untrusted code, implement and experimentally verify OS-enforced permissions, resource caps and a bounded serialized protocol without Python pickle.

The calculator caps source length (256), AST nodes (64), recursion (16), numeric token length (40), integer powers (absolute exponent ≤16) and intermediate rational bit lengths (1024). Decimal literals are exact rational decimals; exponent notation and symbolic operations are unsupported. Python's ordinary `0**0 == 1` convention is retained. Limits are part of its supported domain, not universal math semantics.

## Replay and privacy

Replay accepts sanitized fixtures, not live traces. It creates a fixed evaluator identity with no grants, requires deterministic inert operations and refuses fixture authority fields. Side effects are denied before dispatch. This is safe for trusted declared-inert providers, not a security guarantee against lying code.

Metadata traces contain request/correlation IDs, operation, module/version, status, error category and latency. Trace writes are serialized. No payload/result retention or payload hashes are enabled; even hashes can expose low-entropy private values. IDs should be opaque and never contain secrets. Trace retention/rotation/encryption are the host's responsibility. Trace I/O failures propagate rather than silently losing audit records. A response's computation reference links the request; a persisted full formalization/model artifact is not yet provided.

## Next engineering gates

These are cross-cutting prerequisites and suggested dependencies, **not project-wide phase numbers**. Plan, execute, and verify each relevant component using the independent P0–P3 lifecycle in [the active roadmap](roadmap.md).

1. Audit actual Lu/HDC sources when available; adapt existing tools rather than recreate them. Add strict native/JSON conversion fixtures at the real boundary.
2. Add richer operation schemas, typed artifacts, formalization hashes/restatements under explicit retention consent, dependency checks and per-session resource/call budgets.
3. Implement an OS-enforced worker boundary before any effectful or untrusted provider. Verify read/write/network denial, resource exhaustion, cancellation and orphan cleanup.
4. Add one canonical SQLite claim ledger and typed state event store, transactional migrations, provenance, contradiction/supersession, scoped grants, idempotency journal and deletion propagation.
5. Add explicit bounded composition plans and dependency failure tests. Avoid hidden plugin-to-plugin calls and universal vector assumptions.
