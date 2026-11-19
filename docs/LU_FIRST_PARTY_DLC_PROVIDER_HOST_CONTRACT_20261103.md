# Cognitum → Lu first-party DLC Core Extension contract

**Date:** 2026-11-03  
**Status:** Proposed consumer/provider alignment, **not** a production-integrated Lu Core Extension.  
**Lu platform owner:** [LU-DLC-API-00 RFC in Lu](https://github.com/vjmichael/Lu-AI-GUI/blob/lu/dlc-api-first-party-host-contract-20261103/docs/LU_FIRST_PARTY_DLC_HOST_API_RFC_20261103.md)  
**Implementation tracking:** [Lu issue #8](https://github.com/vjmichael/Lu-AI-GUI/issues/8)

## What Cognitum already established

Cognitum is an **optional first-party native Lu Core Extension (CE)**, not a mandatory Lu runtime feature, an MCP server, or a replacement for Lu's model loop. It supplies typed analytical/computational operations; Lu owns model sessions, host permissions, model-facing schema publication, process launch, durable effect journals, results and UI. The independent Cognitum repository remains the domain implementation source of truth. Cognitum may also run its own benchmarks and standalone tests.

Previously reviewed paths:

- \`cognitum/lu_ce_handoff.py\` and \`cognitum/lu_ce_protobuf.py\`: deterministic **inert** discovery of Cognitum \`calc.rational\` with canonical binary Protobuf \`cognitum.v1.CoreExtensionHandoff\`. The proposal alone does **not** install, enable, register or authorize the CE.
- \`proto/cognitum/v1/capability.proto\` and generated domain bindings: operation-specific typed payloads and evidence/assurance metadata. Lu validates domain inputs/results, not generic JSON claims.
- \`docs/lu-dlc-ce-addenda.md\`: historical Lu host gap register, including genuine **effect-free/pure-compute** declaration, CE version negotiation, session binding, OS worker containment, ANSF ownership and approved tools.
- Experimental \`jan_alt\` AF_UNIX Protobuf carrier on a separate branch: native transport results do not prove production Lu Core integration, valid external model control, caller authentication or installed Windows alpha inclusion.

The older Cognitum-side rule that Lu was **read-only from Cognitum work** is retained as a *workstream separation rule*: Cognitum code changes must not silently modify Lu. The user has separately authorized documentation in all three repositories and a Lu-tracked platform issue. Do not interpret the older rule as meaning Lu's future DLC *runtime interface* should be read-only.

## New cross-project decision: first-party platform API supports both roles

A first-party package can be a **capability provider**, a **host-service consumer**, or both in explicitly authorized contexts:

| Interaction | Direction | Example | Authorization |
| --- | --- | --- | --- |
| Cognitum native CE execution | Lu → Cognitum | \`calc.rational\` → typed evidence-bearing result | Lu-selected route, exact capability/type, saved USER turn or trusted UI task, declared effects |
| Advanced Cognitum analysis | Lu → Cognitum | bounded C14 cause/uncertainty operation | Host resource ticket, operation-specific constraints, strict result verifier |
| CE asks for scoped host service | Cognitum → Lu (optional future) | approved resource status, permitted artifact/reference access | Separate host-issued grant; CE signature alone does not grant memory/files |
| Film Workspace uses Lu inference | NVP → Lu | request model lease, stream screenplay/shot-planning generation | Trusted project creator approval, model admission and Lu-owned session |
| Workspace uses a CE via Lu | NVP/IDE → Lu → Cognitum | invoke reviewed numeric/causal tool and consume verified result | Two distinct bounded authorizations, no transitive permission escalation |

**Cognitum does not need a model-control interface just to evaluate \`calc.rational\`.** The platform nevertheless must provide streaming inference/model services to first-party Workspaces, not force those clients into the tiny read-only observation subset created for NVP B5.

## Core Extension registration and execution contract

1. Cognitum provides a pinned identity and \`CoreExtensionHandoff\` for reviewed exact tools (operation ID, domain Protobuf input/output URLs, result assurance, declared effects, limits and verified package source). No runtime manifest content self-installs or grants authority. Cognitum component versions (C01–C19), Lu host-ABI version and Protobuf wire version are distinct.
2. Lu verifies publisher/package/build integrity, installation and enablement; it matches the proposed CE to actual registered native implementation and Lu's \`ModelToolCatalog\` (when used in a model turn). Only supported, permitted tools are exposed to an eligible conversation; do not automatically advertise every Cognitum library component.
3. Lu constructs the invocation and policy context from a **trusted saved human turn** or verified first-party Workspace project task, never from a model-generated assertion of permission. Host checks exact tool/schema version, inputs, effects, resource caps, project/profile and revocation at dispatch.
4. Cognitum runs the selected deterministic operation through its supervised execution environment; typed result carries assurance (\`exact\`, \`estimated\`, \`unsupported\`, \`failed\` as appropriate), provenance, limitations and independently verifiable evidence. Lu independently validates the result and journals the outcome.
5. Workspaces can call a Cognitum operation only **through Lu's registry/orchestrator**, not by acquiring a Cognitum worker socket or inheriting Lu's permission to filesystem, network, ANSF or model engines.

### Effect classification matters

- \`calc.rational\` is **pure/effect-free**. Do not assign fake workspace-read permission merely because Lu's older single \`ToolEffect\` enum lacks a \`Pure\` case.
- HDC/ANSF retrieval requires an approved, project-scoped read service and provenance. A retrieved candidate is data, not an authority token; index invalidation/retract/forget semantics remain Lu-owned.
- Artifact mutation, network export, GPU resource reservation and external service calls require explicit, separately vetted, type-checked host effects; no blind inherited OS rights.
- Default capabilities remain **off** until installed, enabled, healthy, reviewed and authorized.

## Transport mapping

The **logical Lu host service API** is canonical across first-party deployment modes:

- In-process, vetted first-party CE/Workspace: call the Rust host facade; the same permission checks, request IDs, cancellation and journal apply.
- Independently running CE/Workspace: Lu-owned authenticated local IPC (AF_UNIX if security verified on both Linux/Windows, Windows named pipes fallback if needed), bounded versioned **Protobuf**, with protected transport credentials and verified caller/peer identity. OS socket access is not tool authorization.
- Existing \`lu.v1.ToolCall/ToolReply\` and \`cognitum.v1.CoreExtensionHandoff\` are **adapted**, not silently replaced. Cognitum keeps domain-specific schema authority; Lu controls registry and transport.
- JSON schemas are only compiled/transformed at the external model/provider boundary; they are not internal permission records or substitutes for canonical typed Protobuf.

NVP's read-only authenticated status socket tests are useful for wire-security regression but **must not become the entire first-party DLC API**. The accepted Lu alpha did not ship that socket service; all real Lu host integration is separately gated.

## Cognitum acceptance fixtures for DLC-API-00..07

1. A known \`calc.rational\` fixture is registered by the real Lu host with **no fictional filesystem effect**; an unapproved user/model/Workspace gets no execution.
2. A proper Lu Core invocation transports actual typed Protobuf to Cognitum; Cognitum output and evidence are independently checked by Lu, and the exact host task/route/result are durable across restart.
3. A disabled/revoked Cognitum CE disappears from model-visible capabilities immediately. Revocation/draining/cancellation cannot unload NVP's model or erase unrelated Workspace state.
4. Effects must be individually approved: pure computation works with zero workspace file rights; ANSF query must be scoped and provenance-bearing; artifact writing requires an explicit brokered transaction.
5. A hostile/incorrect IPC peer, duplicate/expired call, incorrect type URL, corrupt numeric evidence, unsupported operation or worker death yields denied/uncertain, never silently accepted result.
6. Native Windows and Linux real Lu host acceptance (not only Python/Cognitum subprocess fixtures) precedes a production DLC claim. Keep model benchmarks with/without Cognitum and standard-library controls.

**Important separation:** Cross-repository documentation does **not** install Cognitum into Lu, promote prior experiments, or change \`0.1.0-alpha.2\`. Lu's checked-in Windows build has an independent missing Job containment API bug ([Lu #7](https://github.com/vjmichael/Lu-AI-GUI/issues/7)), which needs a safe Windows fix before promotion of native real-model acceptance.

## Handoffs and next work

- Lu owns the new canonical first-party host ABI and actual native approval/IPC/worker implementation ([Lu #8](https://github.com/vjmichael/Lu-AI-GUI/issues/8)).
- Cognitum owns precise capabilities, evidence schemas, replay/verification fixtures, security requirements and compatibility adapters. No Cognitum-specific design assumptions in Lu Core.
- NVP owns Film project/take and Blender pipelines, and consumes Lu sessions through the same approved platform service with creator/project authority ([NVP contract](https://github.com/vjmichael/nvp_offline_film/blob/nvp/first-party-dlc-interface-rfc-20261103/docs/NVP_FIRST_PARTY_LU_DLC_WORKSPACE_CONTRACT_20261103.md)).
