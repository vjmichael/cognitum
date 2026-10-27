# C04 — Lu host collector signed receipt boundary (P0/P1/P2)

**Scope:** Cognitum-owned, optional Lu-native Core Extension integration preparation. Lu repo and desktop are **read-only** and have not been changed.  
**Status:** **Offline Protobuf receipt parser and Ed25519 *signature* verifier implemented and tested. No real Lu collector, OS worker, model run, trusted signing key, or benchmark execution is supplied.**  
**Related:** [C03 A/B/C/D plan and capture](../evaluation/P1-P2-host-benchmark-capture.md) · [C02 host conformance security gate](../security/P2-host-conformance-gate.md) · [Lu addendum register](../../lu-dlc-ce-addenda.md).

## Lu source confirmed read-only

Lu's [`lu/independent-branding-ce-foundation` reference branch](https://github.com/vjmichael/jan_alt/tree/lu/independent-branding-ce-foundation) at commit `ef44350cb0fe46efb1aa6c23d64732aea5b630f9` still has:

- A [model tool catalog](https://github.com/vjmichael/jan_alt/blob/lu/independent-branding-ce-foundation/src-tauri/lu-core/src/model.rs) that uses JSON **only externally** and typed Protobuf internally, with host-selected tool visibility (max 16 per model request).
- A [native `CoreExtensionHost`](https://github.com/vjmichael/jan_alt/blob/lu/independent-branding-ce-foundation/src-tauri/lu-core/src/core_extension.rs) that registers/unregisters **trusted** CEs, but does not implement secure third-party installer, OS-confined execution or cancellation of in-flight tool calls.
- [Lu Protobuf `ToolCall/ToolReply`](https://github.com/vjmichael/jan_alt/blob/lu/independent-branding-ce-foundation/src-tauri/lu-core/proto/lu/v1/core.proto), not a general purpose external telemetry channel.

**No running collector or authenticated benchmark endpoint was found in these inspected interfaces.** A read-only code inspection cannot prove one does not exist somewhere else in Lu. This project must not fabricate a Lu API, add a second MCP transport or edit Lu to implement the host features.

## New narrow Protobuf receipt

The [`cognitum.benchmark.v1` collector schema](../../../proto/cognitum/benchmark/v1/collector.proto) is distinct from the C03 `BenchmarkPlan`/`BenchmarkCapture`. Its `CollectorReceipt` binds:

- Exact canonical SHA-256 digests of the previously validated **plan bytes** and **capture bytes** (not untrusted free-text descriptions).
- An externally issued challenge nonce; Lu/model build SHA-256; runner/collector identity and build digest; run/capture ID and observation timestamp.
- Explicit count of reported observed trials, allowing `NOT_RUN` to remain truly unobserved.
- A bounded `SignedCollectorReceipt` containing canonical receipt bytes, a domain-separated **Ed25519 signature** and a signer key ID. The key ID is lookup metadata; the **caller must pin the actual public key independently**.

The [verifier](../../../cognitum/lu_collector_receipt.py) rejects unknown, oversized, malformed, noncanonical or shadowed Protobuf frames, invalid signer/nonce/host/model/capture/plan IDs, mismatched observed-trial counts, stale/future timestamps, digest substitution, raw data claims or attempts to declare `execution_security_verified=true`. There is no private key or signing RPC in Cognitum; tests use fresh, ephemeral test-only Ed25519 keys. Both runtime schemas and code are checked against the seventh `protoc` compiler-produced descriptor in CI.

**Important:** a valid signature authenticates that the holder of a *particular private key* produced the receipt; it does not establish that the public key belongs to a genuine Lu collector, that an authorized user granted access, that OS memory/energy counters are real, that the model used the tool, or that grading was independent. A valid report can contain malicious or fabricated observations signed by an attacker-controlled key. Thus the return type **unconditionally** includes:

```text
signature_matches_pinned_key = true           (if verification passes)
plan_and_capture_bound = true                (if verification passes)
collector_runtime_authenticated = false
metric_provenance_verified = false
paired_effect_verified = false
production_promotion_evidence = false
```

The verifier does not persist used nonces; **one-use challenge issuance, consumption and expiry** require a separate trusted Lu host. Caller-supplied trust inputs are only secure if Lu supplies them from a protected source, not from a model, worker, remote document or the receipt itself. The receipt has no grant, install, activation, sandbox or permission fields.

## What was tested

[Negative tests](../../../tests/test_lu_collector_receipt.py) cover native binary frames; pinned key/signature and incorrect key IDs; plan/capture swaps and substitution; nonce/host/model/collector mismatches; freshness; omitted or forged observations; unknown/duplicate tags; malformed input; fake sandbox claims and hard denial by C02's existing `start_isolated_worker`. A *synthetic fake-success row* is intentionally signed with a test key to demonstrate that even a plausible signed record **does not become model-efficacy evidence**.

The benchmark plan always retains strict C03 four-arm pairing, matched model/backend, deterministic run-order and failure/metric consistency checks. C02 security and C03 metric integrity remain necessary but not sufficient conditions.

## Actual future Lu integration (separate team only)

The LU-CE-010 host telemetry/benchmark team needs to:

1. Approve a local **read-only host benchmark export** and explicit run consent, including raw data retention/deletion and scope boundaries. Model/session/tool events must be captured by Lu authority.
2. Pin the collector public key and build identity in Lu's secure registry/trust store; protect signing keys; independently issue and consume random challenges, with replay-safe durable state.
3. Bind event provenance to a real session/workspace/model/tool catalog/benchmark plan and trusted clock, then collect *independently measured* monotonic latencies, peak RAM/VRAM, token costs and optional OS energy. Missing sensors must remain absent, not zero.
4. Run actual A/B/C/D trials against the selected loaded transformer, competent conventional comparator and fixed dataset/scorer. Record all denied/unavailable arms honestly; no made-up performance gains.
5. Verify C02's independent OS worker security gate before enabling untrusted/effectful CEs. Keep Lu as sole grant/dispatch authority, not Cognitum.
6. Only after independent trusted host instrumentation and grading exist should P3 claims, confidence intervals and promotion decisions become eligible.

This current C04 work is **P1/P2 offline interoperability metadata only**, not a Lu-native executable CE adapter, actual Lu task executor, or production security validation.
