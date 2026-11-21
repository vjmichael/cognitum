# COG-LU-IPC-01A — Lu Core ↔ Cognitum IPC contract alignment (November 21, 2026)

**Status: SOURCE-ONLY INERT CONTRACT CANDIDATE; no native IPC connection, signed DLC admission, model tool registration or installed execution qualified.** Owner reopened Lu Core integration on November 21. This supersedes the former owner deferral of MEL-06B-B for scheduling; it does not retroactively authorize any historical source or installed effect. No changes to Lu repository or its accepted IPC gate have been made.

## Reviewed exact Lu source

Lu repository: vjmichael/Lu-AI-GUI, reviewed development branch **lu/ipc01d-r2-r1-native-20261120**, exact inspected commit **9f43d078aa5e979de0ff72ca4c19e8c5829572af**.

Canonical owner schema: src-tauri/lu-core/proto/lu/workspace/v0/workspace.proto, original Git blob **4e01d921197fb1c58c99958479b1cede36e13c9a**. Lu package is lu.workspace.v0 with wire protocol major=1/minor=0, maximum typed body 64 KiB and frame 256 KiB. Rust codec: src-tauri/lu-core/src/workspace_ipc.rs; framed Windows named-pipe/Unix-domain stream: workspace_ipc_transport.rs. Lu Core-owned effect ingress: workspace_ipc_core_host.rs. Current Lu SDK/installed server may change after this inspected commit: **re-pin against Lu's latest accepted head before compiling a client or declaring compatibility.**

These are source identities and integration targets, not accepted signed Cognitum enrollment, connected native host endpoint, or direct authorization. The Lu v0 source comment about no listener is historical/draft; inspect actual transport and host sessions on the final coordinated Lu SHA.

## Exact API mapping

Cognitum's reviewed role is MODULE_ROLE_CORE_EXTENSION. Proposed module ID cognitum.mel. Lu Hello claims a module/role/package digest but is not OS peer proof. On an OS-attested host session only, a separately authorized RegisterWorkspace can announce capabilities with namespaced IDs, native registered Protobuf input/output type URLs and declared EffectClass.PURE_COMPUTE. No model sees automatic tool registrations.

Initial existing MEL-06B-A research routes (source-only):
- cognitum.vfa.evaluate and cognitum.vfa.gradient
- cognitum.hdc.bind and cognitum.hdc.query
- cognitum.kan.evaluate (requires existing approved checkpoint)

The new *inert* cognitum/mel/lu_workspace_contract.py validates the **actual existing MEL** descriptor and codec identities against the correct five compute-only routes. It produces only deterministic proposal metadata, not signed package SHA, a Protobuf wire frame, or access. The proposed manifest SHA-256 is a content identifier, NOT a signing or enrollment credential. Actual export/registration requires exact Lu-generated WorkspaceFrame/CapabilityDescriptor types, trusted Lu Core registration and installer-owned peer identity. Existing MEL envelopes remain authoritative for domain-side math; never rewrite mathematical types into arbitrary JSON.

For new R6 SSM, reserve a separately reviewed typed request/result contract named conceptually cognitum.ssm.fixed_duration.advance.v1. **Not yet a compiled or registered Protobuf operation.** The contract must include exact checkpoint/source cursor/revision, model identity, units/time, integrated observation increment or watermark, cancellation/uncertain outcome and bounded verified output; host owns all revocation and effective privileges. Register SSM only after native generated Protobuf codec, mathematical validation, explicit current Lu ToolEffect PURE bridge, and installed protected worker pass. Do not treat source-side HMAC/revision CAS as Lu grants.

## Required controls at each boundary

1. Lu owns signed/attested DLC package enrollment, OS account/peer identity and session secret; Cognitum never trusts Hello claim or a bare digest.
2. Lu owns original human workspace/conversation/user-turn/task/operation authority and typed input verification, NativeToolRegistry, explicit PURE_COMPUTE effect bridge, secure resource reference resolution and result publication. Current source reserves pure-compute effect on wire, but existing Lu native ToolEffect bridge does **not** yet authorize it.
3. Cognitum owns independent domain admission, HDC/KAN/SSM numerical scope, state/journal and refusal semantics. It verifies accepted typed requests and authenticates durable domain receipts without becoming a second agent or model manager.
4. Use Lu's OS-local Protobuf framing over **Windows named pipes / Linux Unix-domain sockets** with original peer/session checks, not TCP/gRPC/cloud listeners. Do not create a second framing protocol. No credentials, model weights or persisted ANSF assets in in-band frames.
5. Lu OperationEvent terminal state includes APPLIED, REFUSED, FAILED, CANCELLED, UNCERTAIN. CancelAcknowledged means signal recorded, not worker exited or effect undone. Host/client/domain must reconcile original operation_ref using Lu's durable journal and Cognitum's input/outbox receipt before any replay.
6. Lu model selection, GGUF runtime and canonical ANSF memory remain centralized. Mathematical objects or datasets use approved ObjectRef locators under fresh scope and ownership, not filesystem paths or bearer grants.
7. Limit typed input, stream credit, outstanding operations and memory. A disconnected, stale or revoked client cannot retain authority or continue publishing a result.

## Ledger work packages (inserted in canonical MASTER_TASK_LEDGER.md on this development branch)

| Task | State | Deliverable and acceptance |
| --- | --- | --- |
| COG-LU-IPC-01A | **ACTIVE, source alignment candidate** | Pin actual Lu schema/branch/Protobuf and existing five-route MEL mapping. Native compile and source-drift/unsupported PURE refusal tests; review SSM new typed contract. |
| COG-LU-IPC-01B | QUEUED | Implement Cognitum-side bounded Rust/Python Protobuf client adapter over Lu-owned named pipe/UDS, using native OS peer and enrolled credential handshake. Negative forgery, replay, downgrade and disconnect tests. No duplicate server. |
| COG-LU-IPC-01C | QUEUED/BLOCKED | Review and compile HDC/KAN/VFA plus R6 SSM request/result Protobuf, exact descriptor/codec IDs; wire PURE_COMPUTE to Lu Core's native tool effect without mislabeling. Host grant and domain admission tests. |
| COG-LU-IPC-01D | QUEUED | Real per-turn authorization, bounded streaming/events/credits, Lu-owned dispatch, Cognitum MEL mathematical verification and source/receipt custody. No model-origin grant. |
| COG-LU-IPC-01E | QUEUED | Authenticated cancellation, revocation, concurrent connection isolation, host-supervised shutdown, uncertain outcomes, idempotent journal/outbox reconciliation, and exact protected restart. |
| COG-LU-IPC-01F | BLOCKED on host installer | Signed and installed Cognitum DLC on physical Windows first; Linux packaged service/keyring/UDS when available; installer/upgrade/uninstall, audited credential delivery, provenance, native end-to-end actual GGUF/ANSF and performance tests. |

Dependencies: finish COG-05-SSM-04-R6-INT-03 protected installed custody, actual independent revision authority, Lu's signed DLC enrollment and native pure-effect bridge. The current tested R6-INT-02 scope is Windows current-user DPAPI/local CAS + research disposable process; Linux keyring was unavailable on hosted runners. **Neither equals installed native user/worker custody**.

## Batched engineering policy

Continue IPC source work and local compilation without waiting on unrelated GitHub CI; only run one consolidated native batch for the completed 01A/01B group when native adapter/fixture is review-ready. Preserve exact original Windows/Linux source SHA and artifacts. No duplicate CI, force push, silent Lu mainline merge or premature release. Mainline convergence COG-01, cross-dependency stabilization COG-02, matched end-to-end COG-10, and final add-on release COG-11 follow; retain historical negative scientific results and open HDC/KAN/SSM research scopes.

**Next code task: COG-LU-IPC-01A-R1 — compile a vendored exact Lu v0 protobuf schema under an independently checked pin, complete type/effect mapping and refusal tests, then begin bounded read-only Cognitum client handshake without performing any mathematical tool call until Lu's trusted pure-compute grant is ready.**
