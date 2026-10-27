# C01 / P1–P2 — Protobuf-Native Result Contracts for Lu DLC CE

**Date:** 2026-10-26  
**Status:** P1 implementation committed in `cognitum/c01-protobuf-native-messages`; P2 must be verified by branch + PR + merged-main CI.  
**Scope:** Only `vjmichael/cognitum`. `vjmichael/jan_alt` branch `lu/core-contracts-native-registry` commit `11b2e7e8c5370d512a8f8815d5aaaf9e682e04df` inspected **read-only**.  
**Decision:** **Use Protobuf as Cognitum's native domain wire format for Lu internal tool calls.** Existing Cognitum Python dataclasses and strict JSON schemas remain legitimate at API/model/debug/test boundaries only; they are not the Lu wire format.

## Why this corrects the initial C01 contract

The prior [C01 typed result implementation](P1-P2-typed-results.md) produced `dict`/JSON and an opt-in Python adapter; **it alone cannot plug into Lu's internal native tool transport**. Lu's [`lu.v1.ToolCall` / `ToolReply`](https://github.com/vjmichael/jan_alt/blob/lu/core-contracts-native-registry/src-tauri/lu-core/proto/lu/v1/core.proto) sends an operation's **generated Protobuf message as bytes** plus the declared type URL. `ToolReply.oneof outcome` separates `output` from `failure`. Lu's [`ModelToolCodec`](https://github.com/vjmichael/jan_alt/blob/lu/core-contracts-native-registry/src-tauri/lu-core/src/model.rs) is the proper JSON↔Protobuf edge **owned by Lu**.

Therefore Cognitum must own *domain messages* and validation, but must **not** replace `lu.v1.ToolCall`, `lu.v1.ToolReply`, the native registry, trust/permission decisions, model loop, or session binding. `LegacyJsonArguments` is transitional and **not** the Cognitum CE design.

## Deliverables (Cognitum code only)

| File | Responsibility |
|---|---|
| [`proto/cognitum/v1/capability.proto`](../../../proto/cognitum/v1/capability.proto) | Real proto3 source: `EvidenceRef`, `CalculateRationalRequest`, `CalculateRationalResult`, `NumericalEstimateResult`, `RetrievedReferencesResult`, `CapabilityFailure`. |
| [`cognitum/proto/capability_pb2.py`](../../../cognitum/proto/capability_pb2.py) | Checked-in descriptor-backed **real `google.protobuf` Python message classes**. This is not JSON with a Protobuf label. Exact message/field/optional shapes are compared with separately compiled source in CI. |
| [`cognitum/protobuf_codec.py`](../../../cognitum/protobuf_codec.py) | Bounded binary encode/decode, exact `type.googleapis.com/cognitum.v1.*` URLs, strict semantic validation, and conversion to Lu-compatible **success-byte or failure-category proposals**. Does not construct/modify Lu host messages itself. |
| [`tests/test_protobuf_codec.py`](../../../tests/test_protobuf_codec.py) | Wire-level binary roundtrips, malformed frames, wrong type URLs, stale retrieval, numeric field presence and zero, failure is not success, unknown fields, legacy exact calculator compatibility. |
| [`tools/check_proto_descriptors.py`](../../../tools/check_proto_descriptors.py) | Compares bundled Python message descriptors with actual `.proto` compiled by `grpc_tools.protoc`: package, message identities, field numbers, wire types, oneofs and optional presence. |
| `pyproject.toml` and `.github/workflows/python-tests.yml` | **Optional** `[proto]` dependency (`protobuf>=6.31,<8`) preserves stdlib-only base; CI installs protobuf, compiles schema, and runs all old/new unit and synthetic replay tests on Windows/Linux Python 3.11/3.13. |

No standalone Protobuf network/MCP server, installer, native CE autoload, Tauri command, hidden model selection, or unconfined Python worker is introduced.

## Lu-aligned message routing

```text
  Selected transformer
          |
  [Lu ModelToolCodec]   JSON boundary; Lu validates + owns auth
          |
  Lu NativeToolRegistry::dispatch
          |
  lu.v1.ToolCall  { call_id, tool_id, input_type_url, input: bytes }
          |
          v
  Cognitum CE adapter (FUTURE / Lu-approved only)
      validates exact Protobuf type URL and domain fields
      calculates bounded approved operation (e.g. exact Fraction)
          |
          +-- success --> cognitum.v1.CalculateRationalResult
          |               SerializeToString() real Protobuf bytes
          |               Lu ToolReply.output
          |
          +-- denied/error/timeout --> sanitized ToolFailure fields
                                      Lu ToolReply.failure
          |
          v
  [Lu ModelToolCodec]   validates declared output message
          |
  Same selected transformer synthesizes with limitations
```

**Current implementation stops at Cognitum's encoder/decoder.** `NativeProtoOutput(type_url,payload)` is a Python-native proposal mirroring Lu's declared `ProtoPayload` concept, *not* a compiled Lu `ToolOutput` adapter. A `NativeFailureProposal` is **not** sent as successful bytes; only Lu can map it to `ToolReply.failure`. The `CapabilityFailure` protobuf message is only for bounded *internal Cognitum worker interchange proposals*, not a substitute for `lu.v1.ToolError` inside Lu's envelope. `validated` without execution is represented as a non-success `not_executed` proposal, not as computed output.

## Precise schema and version semantics

The *stable domain* message package is `cognitum.v1` (Cognitum own schema). `proto3 optional string lower`/`upper` preserves **absent vs present zero/empty** via `HasField`. The domain decoder enforces both bounds are present together, finite canonical decimal values, evidence/limitations, and appropriate status/claim semantics. Protobuf wire data does **not** certify truth, input intent, provenance trust, or memory access permissions.

Known native tool mapping proposal:

| Capability | Request type URL | Success output type URL | Actual host state |
|---|---|---|---|
| Exact arithmetic `calc.rational` | `type.googleapis.com/cognitum.v1.CalculateRationalRequest` | `type.googleapis.com/cognitum.v1.CalculateRationalResult` | Inert local Python worker/test harness only; Lu native CE not installed |
| Numerical estimator `kan.predict` | **Not defined yet** (requires C09 P0 input/model contract) | `type.googleapis.com/cognitum.v1.NumericalEstimateResult` | Output shape fixture, **not a runnable KAN native tool** |
| HDC retrieval `hdc.retrieve` | **Not defined yet** (depends on C06/C07 canonical state) | `type.googleapis.com/cognitum.v1.RetrievedReferencesResult` | Output shape fixture, **not a runnable HDC native tool** |

`lu.v1` host **contract version 1** is distinct from `cognitum.v1` protobuf domain package, `RESULT_SCHEMA_VERSION=1.0.0` of Cognitum's compatibility dataclasses, and `CONTRACT_VERSION=1.3.0` of existing Python runtime. Never equate or automatically migrate them.

The `[proto]` extra adds Google Protobuf Python runtime **only to the Cognitum native integration distribution**; default pure-Python Cognitum remains dependency-free. No unexpected GPU/FPGA/Docker/WSL2 requirement is added.

## Remaining host addenda, safety gates and P2 tests

- **LU-CE-001:** Lu must approve optional/removable Core Extension packaging/lifecycle; existing module kinds are Core/Workspace.
- **LU-CE-002:** prevent silent permission downgrades when Cognitum's multiple effects meet Lu's current one-effect descriptor.
- **LU-CE-003:** approve protobuf type URL declarations, generated Rust bindings (Lu or shared build artifact), versioning and schema-breaking check.
- **LU-CE-004 / 007:** Lu owns model schema allow-list, JSON→Protobuf codec and failure/result mapping; no editing Lu from this project.
- **C02:** OS-enforced confinement and native authority/identity required before untrusted/effectful Python components. Typed Protobuf transport does **not** replace sandboxing.
- **P2:** execute source compilation/descriptor match plus complete baseline+C01 tests in GitHub Actions on Windows/Linux, Python 3.11/3.13; verify Protobuf optional presence, exact bytes, malformed/unknown type URLs, effectful isolation, version mismatches, no invented success, and no change to legacy calculator.
- **P3:** no claim of task quality, hardware improvement, or actual loaded-model performance until Lu team's official CE interface and benchmark capture exist.

**Research references:** [Protobuf Python generated code](https://protobuf.dev/reference/python/python-generated/) and [proto3 field presence](https://protobuf.dev/programming-guides/field_presence/).
