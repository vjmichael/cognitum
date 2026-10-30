# Cognitum C14 P2B — Optional DoWhy 0.14 Worker Candidate

**Date:** 2026-10-27 (checkpoint naming convention; executed in this session).  
**Status:** Typed subprocess adapter + negative/contract tests **implemented**; actual DoWhy runtime/Windows confinement **NOT validated**. P2B runtime integration remains an **open gate**. P2A and P1 source contracts remain compatible.

## 1. Actual code

- `proto/cognitum/causal/v1/dowhy.proto`: independent `DoWhyRequest`, `DoWhyResult`, `DoWhyReceipt`, `DoWhyAudit` and typed method/refutation/status enums; compiler-derived binding `cognitum/proto/causal_dowhy_pb2.py`.
- `cognitum/causal_dowhy_backend.py`: closed-schema Python host dispatcher, immutable host-side policy, executable/worker/dispatcher SHA-256 checks, version pin, bounded input/output, disabled-by-default admission, separate trace and hashes, process group timeout kill on Linux and best-effort `proc.kill` on Windows; independent empirical effect crosscheck after worker return. Child scripts cannot be picked by model input.
- `cognitum/causal_dowhy_worker.py`: Python `-I` isolated-mode entrypoint accepting a single canonical Protobuf frame. Worker *calls the public DoWhy 0.14 CausalModel API* when installed, using a generated static-index GML graph; attempts actual `identify_effect`, explicit `backdoor.linear_regression`, and optional `placebo_treatment_refuter` with a caller-fixed seed. Unknown API/dependency errors return non-success rather than fabricated results. The published code path has **not yet run against an installed DoWhy package**.
- `tests/test_c14_dowhy_adapter.py`: worker subprocess unavailability, denial, tampering, malformed frames, host policy, timeouts, missing overlap/backdoor, unsupported method, model-result forgery, replay, redaction, and optional actual DoWhy positive runtime case (skipped absent library).
- `pyproject.toml` adds a **non-default** `causal-dowhy` dependency group pinned to DoWhy==0.14. Exact transitive pins/wheel hashes, licensing and Windows ABI/packaging review remain incomplete.

## 2. Bounded semantics

The only enabled method slot is `DOWHY_BACKDOOR_LINEAR_REGRESSION`, with optional deterministic placebo-permutation refutation. `DOWHY_FRONTDOOR_RESERVED` and `DOWHY_INSTRUMENTAL_VARIABLE_RESERVED` always return `DOWHY_UNSUPPORTED` and cannot be mistaken for backdoor estimation. P2B retains the existing P2A fully observed, finite/binary treatment and outcome sample frequency model, plus a stricter expansion cap of 10,000 individual rows and 5,000 ms timeout. No stochastic subsampling is performed.

1. Treat the input DAG, structural equations and exogenous roots as **supplied assumptions**. Check backdoor sufficiency twice using the P1 routines. Block invalid adjustment and overlapping-cell failures before launching DoWhy.
2. Build graph with observed endogenous variables and unobserved exogenous root labels, never model-supplied arbitrary identifiers. Construct a DataFrame exclusively from typed frequency observations; no files, arbitrary Python functions, user expressions or URLs are accepted.
3. Require DoWhy's selected backdoor covariates to exactly match the caller-specified, separately checked adjustment set; do not silently substitute an estimand. Run backdoor linear regression only. As a conservative first slice, **fail inconclusive** when its numeric ATE differs by >1e-5 from the exact P2A standardized empirical risk difference. A valid linear-regression estimate on heterogeneous effects can legitimately differ, so this is a *narrow verifier policy*, **not a general DoWhy error**.
4. Optionally compute a placebo-permutation diagnostic (10 simulations, fixed seed), never promoted to causal proof. If the placebo API fails, the whole operation is inconclusive rather than returning a selectively successful refutation.
5. Independently verify typed result's request digest, trace, backend ID/version, method, exact reference empirical statistic, reported difference, and diagnostic shape. Receipt's `numeric_verified=true` means **the reported effect is consistent with a bounded empirical statistic**; it does not prove DoWhy actually ran, that source data are genuine, or that causal assumptions hold. `causal_assumptions_proven` always remains false.

## 3. Security, ABI and supply chain gate

- Current `host_authorized`, `enabled`, and `host_isolation_attested` are **Python test/development arguments**, not cryptographic attestation or authenticated Lu admission. A malicious caller in the same Python process can set them; **do not expose this dispatcher to model calls as an authorization boundary**.
- A production Lu supervisor must supply a separate sandboxed interpreter and enforce filesystem confinement, network restrictions, read-only code, environment isolation, policy-bound data, **Windows Job Object** process-tree containment, CPU/RAM caps, timeout and cancellation. The current `proc.kill` on Windows does NOT establish descendant containment. Do not enable the adapter for untrusted payloads before the C02 gate.
- Current integrity checks cover interpreter, worker and dispatcher SHA-256. A production installer must also pin and verify every DoWhy and transitive dependency wheel, runtime search path and binary package against a reviewed offline lock manifest, along with licenses. A worker returning `0.14` alone is not adequate supply-chain evidence.
- Default output is metadata-only `DoWhyAudit`, never raw observations or source graph; hashes are not confidentiality guarantees. Response data remain subject to host permissions/retention controls.
- Worker process call may produce subprocess telemetry outside the sealed audit. No security audit attestation or production sandbox certification is claimed.

## 4. Verification checklist

- Compile all `.proto` files independently; compare wire-normalized descriptors against checked-in generated bindings.
- Run new adapter cases, P2A/P1/C13 tests, C14 smoke and P2A smoke with actual exit code 0; separately record skipped positive DoWhy runtime test.
- Additional **required** integration gate: in a host-provided offline DoWhy==0.14 environment, run the positive runtime test and placebo test with independent golden synthetic data. Validate method API and fixed seeds; verify dependence versions and bounded memory/CPU.
- Additional **required** OS gate: Windows x86-64 sandbox, Job Objects process-tree termination, network/FS denial, sealed dependency lock and verified Lu host identity; then C02/C03 wire interoperability and comparative model benchmarks in later program phase.
- Identification of front-door and IV estimands, valid statistical effect estimation/refutation, partial identification, continuous/temporal/neural and Bayesian causal models belong to further milestones and need method-specific fixtures.

## Reference sources

- DoWhy 0.14 release and Python compatibility: https://pypi.org/project/dowhy/0.14/
- DoWhy CausalModel identification, effect estimation, and refutation API: https://www.pywhy.org/dowhy/v0.14/dowhy.html
- DoWhy 0.14 placebo refuter method: https://www.pywhy.org/dowhy/v0.14/dowhy.causal_refuters.html

**No production recommendation or real causal finding follows from these tests.**
