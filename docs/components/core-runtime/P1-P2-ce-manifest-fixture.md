# C01 / P1–P2 — Offline Lu DLC CE Compatibility Manifest Fixture

**Recorded:** 2026-10-26 (user-local); validation run timestamp 2026-10-27 UTC  
**Implementation branch:** `cognitum/c01-ce-manifest-fixture` (Cognitum repo only)  
**Status:** **P1 standalone fixture implemented, P2 core regression passed**; neither Lu ABI compatibility nor a production host adapter has been certified.  
**No Lu modifications:** verified Lu `jan_alt` on `lu/core-contracts-native-registry` **read-only**, pinned commit `11b2e7e8c5370d512a8f8815d5aaaf9e682e04df`. Lu change requests are maintained as proposals in [the DLC CE register](../../lu-dlc-ce-addenda.md).

## 1. Artifact and exact scope

- [`cognitum/ce_manifest.py`](../../../cognitum/ce_manifest.py) adds immutable `ProposedToolBinding` and `compatibility_fixture(Manifest, ce_id, bindings)`. **There is no Lu import/IPC, protobuf compiler, remote model call, installer, filesystem permission, tool registration or worker launch.** Python stdlib only.
- [`tests/fixtures/ce_calc_v0.json`](../../../tests/fixtures/ce_calc_v0.json) freezes the proposed C05 reference calculator binding, independent of current Lu execution. It explicitly advertises:
  - `host_contract_status="unbound_proposal_not_host_approved"`
  - `module_kind_proposed="optional_core_extension"`
  - `default_enabled=false`, `model_advertised=false`, `installable=false`
  - Proposed native identifier `cognitum.calc.rational`, model-facing name `cognitum_calc_rational`, and **unimplemented proposal** protobuf type URLs `cognitum.v1.CalculateRationalRequest`/`Result`.
  - Existing source manifest and input/output JSON Schema SHA-256 checksums, exact arithmetic assurance and absence of effects.
- [`tests/test_ce_manifest.py`](../../../tests/test_ce_manifest.py) checks the above frozen reference, strict identifiers, type URL syntax, unique mappings, complete operation coverage, safe namespace ownership, metadata stability, and **rejection of any effectful operation** until Lu resolves effect-set vs single-descriptor semantics.
- [`.github/workflows/python-tests.yml`](../../../.github/workflows/python-tests.yml) executes the **entire actual Cognitum test checkout** on `ubuntu-latest` and `windows-latest`, Python 3.11/3.13. Also runs the existing `evals/smoke.json` through the CLI and compiles Python source. No new third-party runtime requirements.

### Why this is necessary

Lu's experimental Rust `NativeToolRegistry` and `ModelToolCatalog` support native tools and JSON→Protobuf validation, but its `ModuleKind` currently has only `Core` and `Workspace`. A DLC **Core Extension** must be optional and cannot be misrepresented as permanent core or a full specialized workspace. Lu's `ToolDescriptor.effect` is a single effect; Cognitum `Operation.effects` can be an effect set with scoped identities. **An effectful operation cannot be exported through this provisional inert-only fixture**, avoiding silent permission downgrades. The Python manifest is a **proposal snapshot**, not Lu's official SDK or a signed installable DLC.

## 2. CI evidence (complete repository, 2026-10-27 UTC)

[**GitHub Actions run 40444530509**](https://github.com/vjmichael/cognitum/actions/runs/40444530509) executed against commit `c37b023bf29e25dff562738e9c279feb91b4fee2`.

| Platform | Python | Unit tests | Synthetic replay | Compile check | Job |
|---|---|---:|---:|---|---|
| Ubuntu latest | 3.11 | **42/42** | **12/12** | Pass | Success |
| Ubuntu latest | 3.13 | **42/42** | **12/12** | Pass | Success |
| Windows latest | 3.11 | **42/42** | **12/12** | Pass | Success |
| Windows latest | 3.13 | **42/42** | **12/12** | Pass | Success |

**42 = 31 inherited repository tests + 11 new CE-manifest tests.** Per-job `unittest discover` logs show 42 tests, `OK`; existing replay logs show 12/12. These are GitHub-hosted runners, not the user's actual AMD workstation or a loaded transformer. The P3 Lu+model performance test has not been performed.

An independent parallel branch, [`cognitum/c01-tracing-guard`](https://github.com/vjmichael/cognitum/tree/cognitum/c01-tracing-guard), has a separate completed [four-platform regression run](https://github.com/vjmichael/cognitum/actions/runs/40444297105) for metadata-only tracing hardening. **Both changes have since merged into Cognitum `main`**. The [combined main CI](https://github.com/vjmichael/cognitum/actions/runs/40444933715) passed **51/51 unit tests and 12/12 replay cases** per Linux/Windows Python configuration.

## 3. Acceptance boundary and remaining work

**Passed:** stable deterministic fixture generation, default-off/noninstallable assertion, syntactic Lu-native ID/tool name/type URL checks, source schema hash linkage, duplicate and missing mapping rejection, fail-closed effectful operation rejection, whole-repository CPU regression on Windows/Linux, Python source compile and synthetic replay.

**Not yet provided:** Lu core contract/CE module lifecycle acceptance (LU-CE-001), Lu effects mapping (LU-CE-002), actual generated Protobuf message types (LU-CE-003), trusted Lu catalog/enablement (LU-CE-004), authenticated host identity and secure worker (LU-CE-005/006), loaded-model tool-call and latency measurements (LU-CE-010). The fixture cannot install, advertise, authorize or execute any Lu tool.

**Next safe activities inside Cognitum:** with both changes merged and the combined regression passing, add immutable typed *result evidence and failure* fixtures for approximate/exact operations; expand C03 offline evaluation task rubrics; design C06/C07 canonical state without duplicating Lu-owned ANSF memory. **All potential Lu changes remain in the proposal register only.**
