# COG-06C — Bounded cooperative CPU execution architecture

Status: implementation candidate, not yet accepted. Builds on [COG-06B exact-SHA acceptance](https://github.com/vjmichael/cognitum/actions/runs/44033095744) at `9558beadb449706dd19d5d541e92a6c385b25b06`. No Lu source or main change, no new agent, scheduler, host authority or canonical memory store.

## Execution and identity

The existing `Registry`, `Runtime.call`, `HostContext`, policy, disposable worker and metadata-only trace remain the sole reference execution mechanism. `cooperative_cpu.CooperativeCpu` implements the existing plugin interface and is never installed/enabled/nominated automatically. Host-owned code must perform all three actions; worker compute and verify operations are internal, not model-visible. The immutable reviewed ROUTES map is a typed compatibility catalog, not an alternate registry or policy. Each route identifies exact input/output Protobuf descriptor names, descriptor hashes, reviewed version and allowed verification levels. The restored historical P25 proposal module remains advisory; its four relevance hints cannot execute or grant permissions; missing reviewed C05 entries now fail closed.

`cooperative.Plan`, `Step`, `Dependency`, `SourceStamp` and `Admission` are typed **internal Python contracts** containing canonical domain Protobuf bytes (no new executable wire format or arbitrary dynamic message loader). Host supplies the expected build SHA, scope context, admission, source-current and cancellation callbacks. Plan digest binds source IDs, revisions, exact template hashes, route/type identities, scope, build, deadlines and all declared dependencies. The host authenticates the source/build and owns authorization; a digest or caller's claimed source is not authentication. There is no production code loader or arbitrary model-provided callback dispatch. Validate graph shape, route identities, canonical typed frames, dependencies and cycles before any worker. Deterministic topological ordering uses sorted ready IDs.

All routes use two separate actual worker calls through the existing Runtime: compute, then verify. Verification admission binds the returned candidate hash as well as the materialized request hash; verify response binds the route identity, exact request, exact output and narrow assurance. Recheck installed nominated factory/manifest under existing registry lock. Host approval is required for plan, each materialized compute and verify request, and final publication. Freshness and cancellation are checked at every phase and before publication. Revocation between calls prevents subsequent admission. On any invalid graph, missing operation, denial, staleness, cancellation, deadline, unsupported/unverified result or bridge failure, return only bounded diagnostic status and failed step; no returned partial output. Existing runtime traces supply diagnostic metadata. Final publication is in-memory return only, not a durable atomic write to Lu.

## Initial route admission and assurances

| Component | Operations | Assurance |
|---|---|---|
| C05 | math.linear | Exact rational matrix product, permutation determinant, unique linear solution witness via separately implemented Fraction arithmetic |
| C10 | formal.integer; formal.finite | SAT witness replay, bounded integer exhaustion, finite UNSAT exhaustive certificate only |
| C11 | optimization.schedule; optimization.allocation | Independent feasibility/witness and objective consistency, not global optimality proof |
| C12 | planning.graph | Separate plan simulation; no independent search-optimality claim |
| C13 | probability.bayes; probability.beta | Numerical recomputation against typed inputs, not causal or empirical calibration proof |
| C16 | physics.ode | Existing numerical replay and diagnostic check, not general physical truth |
| C17 | temporal.kalman; temporal.hmm | Existing numerical replay, not independently validated sensor provenance |

Non-finite result fields are rejected recursively. Numeric recomputation is a separate verification invocation, not an independent algorithm when the underlying checker reuses the same numeric library. UNSAT solver assertions, unknown/unsupported results, infeasible schedules without independently verified evidence, unverified plan absence, learned SSM, HDC, KAN, experimental C14, external Fast Downward/pgmpy/PyMC/Carcara workers and C15 real data are not admitted. C06/C07 canonical memory operations are excluded from graph execution until host-side source/authority requirements are established; SourceStamp is not a parallel memory database. COG-06D expands only defensible domain adapters and independent oracles; COG-06E/F and later model/host acceptance remain separate.

## Dependency semantics

- `linear_integer_candidate`: exact solved integer vector in C05 row order -> C10 ordered variables, append equality constraints to independently supplied formal problem. Noninteger vectors, wrong dimension and out-of-bound representations fail closed. This verifies a candidate against additional constraints, not global solution-set completeness. A verified contradictory result may be a completed computation with UNSAT_EXHAUSTIVE verdict, not a valid candidate; callers must interpret that verdict. 
- `plan_schedule_precedence`: independently verified C12 action sequence -> matching C11 job names, add explicit predecessor edges. Requires one-to-one unique identity; does not invent job durations, units or resources. Existing scheduling validator rejects incompatible original constraints.
- `requires_verified`: control edge only, no data conversion. Never counted as a compositional data handoff.
- At most one reviewed data transformation per step; no generic string interpolation, field-path selector, unit coercion, code execution or mutation. Receipt includes original template source plus materialized request hash, result hash, predecessor receipt hashes, route and verification digest. All raw result frames stay in returned complete graph; host must securely persist if desired. Correlation hashes are not signed receipts.

## Resource and safety limits

8 steps, 16 edges, 8 KiB per canonical native input or output frame, 32 KiB aggregate materialized inputs and outputs each; base64 within existing Runtime's 16 KiB JSON result cap. 30 s plan and 10 s step deadlines; compute and verify share remaining step budget, with remaining budget sent to existing disposable worker. CPU libraries and their native algorithm limits remain in force. No parallel execution. Existing worker cleanup and trusted host callbacks may exceed a wall deadline; late results are discarded, not claimed hard preemption. OS Job/cgroup memory caps, process-tree custody, in-flight cancellation, durable execution/recovery, privacy-safe source attestation and Lu integration remain host obligations (COG-11), not new functionality here. Registry revocation applies to next admission; the existing lock pins the selected factory through a single worker call.

## Acceptance scope

Restored 17 historical advisory tests plus graph suite: actual C05->C10 and C12->C11 worker compositions, direct remaining CPU domain calls, finite certificate, dependency cycle/missing/wrong type, stale source, scope/build, research refusal, disabled registry, forged route/worker output, unverified result, nonintegral handoff, certified contradiction, revocation, shared budget, cancellation and publication denial. Original COG-06B source guard, focused tests, compiler parity, benchmarks and full regression are reused in one grouped four-way matrix. The existing workflow is renamed for COG-06C to avoid redundant triggers; historical run remains immutable. Actual native execution and terminal logs are required before marking accepted. COG-06D still owns independent composition completeness and comparative task fixtures (including probability/physical uncertainty); no model-level efficacy or production claims.
