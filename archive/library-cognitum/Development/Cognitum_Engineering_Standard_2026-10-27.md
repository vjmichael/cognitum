# Cognitum Engineering Standard: Mature Baselines, Research Extensions, Auditing, and Benchmark Readiness

**Decision date:** 2026-10-27  
**Status:** User-approved direction; architecture/policy, not a claim of implemented instrumentation or validated production gates.  
**Active source baseline:** C10 P1 at `/Cognitum/Development/Cognitum_C10_P1_Bounded_SMT_Proofs_2026-10-27.zip`.  
**Scope:** C01–C19, including previously completed components when revisited. C08 HDC and C09 KAN remain deferred; reuse archived K4, do not rebuild unless independently established new gains justify reconsideration.

## 1. Purpose and non-negotiable commitments

- Build complete, extensible AI capabilities grounded in mature implementations and the recognized standards for their domain. A hand-written reference algorithm is not equivalent to a full technology implementation.
- Support **two distinct implementation tracks** under the same typed capability contract: (a) mature, reproducible reference/production backends and (b) strictly optional research/experimental backends. If multiple mature backends are useful, support them without proliferating per-backend model tools.
- Research backends have explicit maturity labels, version/commit/paper provenance, resource/security controls, and an independent off switch. No automatic promotion to production or silent substitution during tests.
- Make each capability **auditable and benchmark-hook-ready from the start**, while deferring major real-model, comparative, hardware and end-to-end benchmark campaigns until the component portfolio is substantially implemented, as the user directed.
- Continue focused deterministic mathematical, Protobuf, code correctness, smoke, and security-boundary checks during development. Never equate passing those with production readiness or superior performance.
- Cognitum remains modular and offline-first; internal contracts Protobuf-native. JSON is allowed at explicitly labeled external boundaries/export, not as the internal source of truth.
- Lu authenticates callers, owns canonical ANSF conversation memory and protected resources; Cognitum cannot mint authority or duplicate canonical memory. Do not modify GitHub or Lu without explicit direction. Windows x86-64 is the initial deployment target; avoid Docker, WSL or manual tool installs for end users.

## 2. Component research and standards gate (before substantive implementation)

Each component must have a versioned **Capability Dossier** with:

1. Field definition and minimum conventional capability inventory, plus advanced/optional functions.
2. Dominant standards, interchange formats, applicable published test suites and reference algorithms.
3. Shortlist of mature libraries with versions, maintenance, license/redistribution constraints, feature coverage, Windows x86-64/offline packaging, native binding/ABI and trust surface.
4. Research extensions with publication date/DOI or project commit, verified claim vs hypothesis, limitations and potential integration risks. Research survey recency recorded explicitly; no blanket claim of state-of-the-art.
5. Selected standard backend(s), experimental backend(s), adapter boundary and fallback policy. Every claimed capability gets its own tests and availability status; missing functions are not fabricated or silently emulated.
6. Clear completion states: prototype, functional reference, native integration tested, security gate passed, and benchmarked. These are not synonyms.

**C10 example:** Treat the bounded Boolean+integer-difference logic solver as a self-contained reference fragment, not general SMT. Review SMT-LIB, Z3, cvc5, and proof/certificate facilities before P2 backend selection. Never claim UNSAT on a timeout or from an unverified solver string.  
**C11 example:** Assess OR-Tools, HiGHS, and domain-specific CP-SAT, MIP, LP/QP, routing, and scheduling algorithms instead of naively reimplementing each one.

## 3. Stable Protobuf capability and backend interfaces

One canonical versioned Protobuf vocabulary per capability, independent of backend implementation. Required logical elements:

- `CapabilityDescriptor`: identifier, contract/schema version, supported operations/theories, determinism class, maturity (`reference`, `stable`, `experimental`), backend ID/version, limits, known restrictions, provenance and build digest.
- `CapabilityRequest`: host-bound request ID, caller/task/scope identity **supplied by the trusted host**, typed payload, resource budget, fixed seed when applicable, cancellation handle, and independent audit/trace correlation ID. Caller-supplied identity does not authorize any operation.
- `CapabilityOutcome`: explicit result class (success/unsupported/unknown/timeout/cancelled/denied/error), typed output, elapsed/resource counters, warnings, source/proof references and versioned backend provenance. `UNKNOWN` must never be silently turned into success or proof.
- `BackendSelector`: explicit pinned backend selection; defaults to a known mature backend only after that backend is integrated and qualified. Research backend default disabled. Never silently compare different semantic capabilities or numerical precision as if equal.
- `VerificationReceipt`: the separately verified model/property/certificate status and exact input/output/build digests, including independent verifier ID/version and reason when a proof could not be checked.

These names describe **future logical contracts**, not already generated `.proto` symbols. Implement them by evolving existing contracts rather than duplicating C03 or Lu envelopes; retain ABI/version migrations and negative-test vectors.

## 4. Auditability and provenance by design

- For each operation record a bounded audit envelope: correlation/task ID; component and exact backend; source/module/library versions; model/solver build digest; schema version; host-policy decision reference; input/dataset digest (not raw private content); output digest; seed and numeric precision; environment and OS/CPU/GPU characteristics where relevant; start/end times; phase, resource quotas, cancellations, timeouts and error category.
- Support trace spans for dispatch, admission, preprocess, backend execution, independent verification and publication; record counters and named state-change events. Prefer conventions structurally compatible with OpenTelemetry, but do not mandate installing a collector or exporting telemetry.
- Store logs **locally, opt-in, bounded and redacted**, with explicit deletion/retention controls. Do not log full user prompts, proprietary files, personal medical records, secrets, model private context, or unrestricted paths by default. Hashes are identifiers, not confidentiality guarantees; use policy and scoped access controls.
- Audit records should be integrity-checkable (hashes, sequence and sealed manifests) and reproducible where deterministic. Explain that a hash chain alone is not tamper-proof against an adversary who can rewrite all local files; stronger attestation/signatures require trusted keys and host enforcement.
- Record all security denials and anomalous state transitions without returning sensitive material. Components must not manufacture audit success receipts or self-authorize.
- Experimental/research backends must have unambiguous opt-in and rollback; a host-controlled kill switch revokes new invocations and cooperates with cancellation. Any forced termination and cleanup must be implemented in Lu's supervisor, not entrusted to the component itself.

## 5. Reusable evaluation / benchmark hooks: add now, benchmark later

- Reuse the existing C03 reproducible benchmark configuration and result-capture concepts and Lu's separate benchmark/configuration work **after reviewing exact schemas**. Do **not** declare compatibility until a real wire/schema interoperability test passes.
- Include a versioned `RunManifest`, fixture/dataset checksum, backend+model selection, fixed seed, resource budget, hardware fingerprint, provenance chain, metrics collection, per-case result and error/abort status.
- Provide **headless offline invocation**, deterministically replayable fixture input where feasible, typed Protobuf export at the native boundary, optional JSON/CSV summaries for external tools, and an adapter bridge for Lu's benchmark runner. No direct network telemetry required.
- Provide hooks at request admission, preprocessing, backend runtime, verification and output publication. Preserve separate wall-clock timing, computation-only timing, resident memory, VRAM and energy (only if actually measured), and counts of actual work/unknown/timeouts/failures. Never invent missing hardware metrics.
- Baseline and research branches must accept equivalent datasets, problem formulations, resource budgets and precision restrictions. Compare quality/correctness and latency/resource cost separately; an experimental backend must not exploit baseline-specific shortcuts.
- Evaluate independently when the program is ready: golden/counterexample suites, adversarial and real-world tests, feature-equivalent baselines, repeated runs, confidence intervals when appropriate, failure profiles and security/abort behavior. Report uncertainty and explicit kill/retirement criteria by component before releasing novel technology.
- The final benchmark campaign may borrow reproducibility/audit principles from MLCommons/MLPerf, domain-specific corpora (e.g. SMT-LIB for SMT), and compatible tracing semantics from OpenTelemetry, without claiming MLPerf certification or cross-domain applicability.

## 6. Implementation policy for C10 P2 onward

1. **Library and standards audit first**, then choose bounded integration adapters; enumerate native dependencies and license obligations.
2. Keep the existing C10 reference solver as a limited fallback/independent cross-check, not the default universal theorem prover.
3. Implement backend discovery and strict theory/operation support checks. Unknown theories are unsupported, not "false" or "proven".
4. Integrate `VerificationReceipt`, audit envelopes, cancellation, backend provenance and benchmark hook interfaces as lightweight shared services; reuse existing Cognitum/Lu design rather than clone their telemetry loops.
5. Continue focused mathematical and functional smoke tests (including corrupted output and incomplete proof cases), not large comparative runs.
6. Defer benchmark scoreboards, major tuning, real-model evaluations and performance claims until the broader component implementation phase is complete.
7. Maintain a signed-off integration checklist showing uncompiled Rust, unauthenticated host adapters and unexecuted Windows tests honestly as pending.

## References consulted (public standards; not endorsements)

- SMT-LIB benchmark library: https://smt-lib.org/benchmarks.shtml
- OpenTelemetry semantic conventions and trace/metric/log architecture: https://opentelemetry.io/docs/specs/semconv/ and https://github.com/open-telemetry/opentelemetry-specification/blob/main/specification/overview.md
- MLCommons benchmark and reproducibility principles: https://mlcommons.org/benchmarks/ and https://github.com/mlcommons/inference_policies/blob/master/inference_rules.adoc

**Current state:** Architecture standard recorded for future engineering. This document itself does not alter or re-test code and does not prove Lu benchmark integration.