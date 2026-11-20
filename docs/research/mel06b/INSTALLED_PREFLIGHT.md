# MEL-06B — installed Lu-to-Cognitum acceptance preflight

Date: 2026-11-19 (Arizona local). Status: **BLOCKED before installed execution**. Owner authorized MEL-06B qualification. No new mathematical capability, host runtime edit or release admission is claimed.

## Reviewed exact source and evidence

- Cognitum tested baseline: [9aa69507d5f8fd99db0ba2f3db56a0d7d4b948e4](https://github.com/vjmichael/cognitum/commit/9aa69507d5f8fd99db0ba2f3db56a0d7d4b948e4). Four corrective workflows are terminal green (20/20 jobs): [Python](https://github.com/vjmichael/cognitum/actions/runs/44655592022), [C13](https://github.com/vjmichael/cognitum/actions/runs/44655588514), [wheelhouse](https://github.com/vjmichael/cognitum/actions/runs/44655588315), [integration](https://github.com/vjmichael/cognitum/actions/runs/44655588368). Previous failed runs remain in the ledger.
- COG-04M/N [18/18 reference acceptance](https://github.com/vjmichael/cognitum/actions/runs/44643948757) at ab4c91d9d728ad1f6e8f50fa0e8c18754d39da0d; both step results checked on each of four OS/Python cells. [MEL-06A/R1](../mel06ar1/REPORT.md) previously demonstrated real reference GGUF generations and native worker replay, not installed Lu or fresh final hardened-host inference.
- Lu read-only baseline: [97ef98546c1fd05d7d133729b5d356f36b08a584](https://github.com/vjmichael/Lu-AI-GUI/commit/97ef98546c1fd05d7d133729b5d356f36b08a584). Review current main, not the former jan_alt CE branch. Files searched and source inspected at that SHA; no claim about unreviewed branches or installed end-user machine. No installed Lu executable on PATH in the current Linux environment; no release assets returned by Lu's releases endpoint; inspected Lu Library folders and shared runtime/model locations, no confirmed MEL-capable installed candidate. This is not proof that no Lu installer exists anywhere.

## Native scientific evidence reconciliation

All four downloaded evidence ZIPs match GitHub SHA-256 digests and pass ZIP CRC. Independently hash every locally uploaded wheel and compare **exact filename and SHA-256** with each hosted receipt. The source archive digest is 4b07b8608fc65d00ccc232deac36d3bf55bb2049d0eaf4882219dda9c4ed940c. All receipts bind the tested source 9aa69507d5f8fd99db0ba2f3db56a0d7d4b948e4.

| Target | Wheels | Profiles | Focused tests | Artifact ID | ZIP SHA-256 |
|---|---:|---:|---:|---|---|
| Windows x64 / 3.11 | 26 | 1 | 28 | 14592668760 | 85c9dc16616f8e817b4126c59d04a510787a72e9dd750d10263c45e4ffc568dd |
| Linux x64 / 3.11 | 26 | 1 | 28 | 14592643641 | 2918cf38d3e55b772329c5b2144c490602610aa57e6110c3fa98ce23abb035fd |
| Windows x64 / 3.13 | 19 | 2 | 56 | 14592474040 | d295ac7e6fafe1545ef4d50a8390334587fd2cd3c66301bda4e54b8180904ecd |
| Linux x64 / 3.13 | 19 | 2 | 56 | 14592773618 | 74613bb358ab701c7146078a84f8f909f693600e34691cd40d8961d1691be40f |

90 target-wheel entries, six successful profiles, 168 focused test executions, zero failures/errors/skips in these scripts. Receipt and probe status checked, 5 compatibility + 23 diagnostic tests per profile, pip check and actual engine probes pass. Legacy ArviZ emits an informational migration warning before its JSON probe; modern 3.13 profiles report no loaded plotting modules. Hosted staging fetches exact wheel bytes from PyPI, verifies hashes, then installs via --no-index with --require-hashes. This does not establish OS-denied network access or physical Windows execution on the user's PC.

## Host gap audit

| Boundary | Reviewed source | Disposition |
|---|---|---|
| Native extension contract | [contracts.rs](https://github.com/vjmichael/Lu-AI-GUI/blob/97ef98546c1fd05d7d133729b5d356f36b08a584/src-tauri/lu-core/src/contracts.rs) | ToolEffect exhaustive list lacks pure computation. No fake ReadWorkspace or broad ExecuteCode grant. Decide explicit versioned, accurately scoped pure computation effect/admission and all persisted/wire compatibility handling with Lu. |
| Extension lifecycle | [core_extension.rs](https://github.com/vjmichael/Lu-AI-GUI/blob/97ef98546c1fd05d7d133729b5d356f36b08a584/src-tauri/lu-core/src/core_extension.rs), [ce_permissions.rs](https://github.com/vjmichael/Lu-AI-GUI/blob/97ef98546c1fd05d7d133729b5d356f36b08a584/src-tauri/lu-core/src/ce_permissions.rs) | Existing trusted registration, host authorization and draining; these are not verified installation or protected child custody. Reuse existing host worker supervisor, policy, cancellation and durable recovery. No model-created grants. |
| Model path | [model.rs](https://github.com/vjmichael/Lu-AI-GUI/blob/97ef98546c1fd05d7d133729b5d356f36b08a584/src-tauri/lu-core/src/model.rs), [phase 1 contract](https://github.com/vjmichael/Lu-AI-GUI/blob/97ef98546c1fd05d7d133729b5d356f36b08a584/docs/LU_PHASE1_MODEL_TOOL_INTERFACE_20261109.md) | Existing live catalog, closed JSON, typed codec, model journal and reviewed authorization; bind actual registered MEL tools to these rather than a second chat agent. |
| Cognitum mathematical boundary | [native.py](https://github.com/vjmichael/cognitum/blob/9aa69507d5f8fd99db0ba2f3db56a0d7d4b948e4/cognitum/mel/native.py), [model_reference.py](https://github.com/vjmichael/cognitum/blob/9aa69507d5f8fd99db0ba2f3db56a0d7d4b948e4/cognitum/mel/model_reference.py), [intent_reference.py](https://github.com/vjmichael/cognitum/blob/9aa69507d5f8fd99db0ba2f3db56a0d7d4b948e4/cognitum/mel/intent_reference.py) | Reuse reviewed descriptors, closed wire validation, exact typed intent and independent verification. Reference only and trusted caller supplies intent; no installed authority or authentication by digest. Adapt existing protobuf requests/results without accepting arbitrary object or executable path. |
| Existing Cognitum connection | [ansf_cognitum_bridge.rs](https://github.com/vjmichael/Lu-AI-GUI/blob/97ef98546c1fd05d7d133729b5d356f36b08a584/src-tauri/lu-core/src/ansf_cognitum_bridge.rs) | Scoped ANSF memory evidence path; mathematical execution not established by this bridge. |
| Model and packaging | Shared Development Toolchain / AI Test Models and AI Runtime | Qwen GGUF reference inputs and pinned llama.cpp source available by listing. No additional model request. Restore/verify exact installed package and active model on an appropriate native host. |

## Proposed grouped next task: MEL-06B-A

Coordinate on the current Lu engineering track. Re-audit the exact selected integration head before changes (the heads above are review baselines, not a merge authorization). Integrate one default-off MEL extension into Lu's existing trusted CE installation/admission, reviewed native Protobuf codecs, model catalog and protected execution path. First scope: certified VFA evaluate/gradient and one independently verified HDC/KAN or cooperative mathematical path using existing MEL primitives; expand only after a verified installed vertical slice. Keep unrelated research disabled. Require explicit host/user approved intent for each bounded request, no autonomous capability promotion. Keep Lu ANSF and journal canonical, no second registry, permission system, orchestrator or model. All host effects and wire/persisted types must be reviewed, no permissive substitute just to achieve a green test. Host-side implementation and source approval are coordinated separately; this preflight makes no Lu source mutation.

## MEL-06B-B installed gate matrix (all NOT RUN)

| Gate | Necessary observed evidence |
|---|---|
| B01 provenance and install | Installed exact Lu candidate, package and Cognitum digests, tool and engine identity, verified active local GGUF, real GUI/session, no cloud or hidden model substitution; default-off before human enable. |
| B02 live discovery | Installed registry and eligible per-turn model catalog, exact native type URLs and host intent, denied/disabled routes not advertised. |
| B03 real positive | Unscripted model-generated JSON call from current local GGUF; exact typed Protobuf encoding accepted by existing host policy; authenticated supervised worker receipt, actual VFA and scoped HDC/KAN or cooperative results, independent numerical replay, final model response / labelled trusted fallback. Preserve model refusal as a real outcome; never inject a call or fabricate feedback. |
| B04 independent matched trials | Same model and held-out mathematical questions, ordinary model and conventional/single-specialist/cooperative arms where supported; record all attempts/refusals, answer accuracy, typed-call validity, elapsed time/CPU/RAM, model and fallback publication separately. No general efficacy claim from tiny fixture. |
| B05 negatives | Denied authority, stale descriptor/checkpoint, wrong intent/units/types, malformed output, tampered receipt, disabled extension, scope mismatch, forged model grant; zero unauthorized dispatch and no unverified numerical publication. |
| B06 lifecycle | Active cancellation, revocation mid-execution, worker interruption, durable journal/restart and exact receipt recovery, unload/drain, no stale late publication or effect replay. Qualify existing native custody on Windows/Linux; no reference-only mock substituted. |
| B07 consolidation | Reconcile exact installed candidate, model/engine/build identifiers, independent witness checks, host receipt provenance and raw acceptance archives; batch unchanged-source acceptance. Physical machine acceptance distinguished from hosted tests. No automatic production promotion or full release claim. |

The **missing native integration**, not another GGUF or solver package, blocks this gate. The existing research replay is not a replacement. No new CI was requested by this documentation-only preflight; no new inference or installed test was executed.
