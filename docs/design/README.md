# Cognitum complete AI technology design — Revision 1.5 index

This is the **full design set** for Cognitum as an optional, native Protobuf Lu DLC Core Extension. It preserves Revision 1.4's recovered original 12-technology research vision, makes the 19-component order operational and records current host/security/research constraints.

| Document | Read this for |
|---|---|
| [**Comprehensive AI Architecture (R1.5)**](../Cognitum_Comprehensive_AI_Architecture_R1_5.md) | Normative host/Cognitum/Workspace responsibilities; existing vs proposed evidence; Protobuf/security; memory ownership; provenance; component lifecycle; hardware/permission/deletion policies |
| [**Technology Portfolio C01–C19**](technology-portfolio-C01-C19.md) | All 19 components: question, typed interface design, incumbent libraries, build/test/benchmark gates, CPU/GPU/FPGA options, major failure modes and status |
| [**Research, Validation and Delivery**](research-validation-and-delivery.md) | Eight concrete cross-technology research hypotheses, factorial ablations, end-to-end A/B/C/D methods, benchmark tiers, metrics, risks, P0–P3 checklist, priority/dependency milestones and unresolved ADRs |
| [Historical Source-Informed 1.4](../sources/Cognitum_Source_Informed_Revision_1_4.md) | User-original design lineage, 12-module map, static-code corrections, recovered K4-related hypotheses and background references |
| [Living development roadmap](../roadmap.md) | Current execution-stage tracker; not equivalent to completing the R1.5 design |
| [Dependency build order](../build-order.md) | C01–C19 build and research priority |
| [Lu native host addenda (Proposed)](../lu-dlc-ce-addenda.md) | Compatibility issues for the **separate** Lu team, including C02/C04 and Cognitum CE capability onboarding |
| [HDC/KAN original archive reuse audit](../components/hdc-kan/P0-archive-reuse-audit.md) | Verified source hash and K4 41-unit/20-selftest archival provenance without claiming production integration |

## Status ledger — design versus implementation

| Component span | Design | Implementation/evidence |
|---|---|---|
| C01–C05 | R1.5 cards and technical scope defined | Some Cognitum P1/P2 code/tests merged (see existing technical reports); C02 production launch and C04 host integration **still blocked** |
| C06–C07 | Canonical memory/revision design defined | **Design-only**, pending single Lu-authorized source-of-truth decision |
| C08–C09 | HDC/KAN research integration design defined | Original K4 archive recovered/tested; Cognitum integration and P3 superiority **unproven** |
| C10–C19 | Technical design, baselines, risks, hardware and tests defined | **Design-only**, no P1/P2/P3 completion claims |
| R01–R08 compositions | Falsifiable hypotheses and experimental controls defined | **Proposed research**, no measured composite gain claimed |

**Important:** "All AI technologies designed" does **not** mean 19 production-ready plugins. A sound implementation still needs actual scoped domain Protobuf, Lu-owned security/consent, tests and genuine held-out comparisons.

## How to maintain it

1. Add a versioned ADR for any material contract, trust, canonical memory, user-consent, retention, representation-conversion or promotion change.
2. Record specific P0 research files and source/license surveys before developing individual remaining components; R1.5 is a comprehensive **architectural design**, not proof every component's own literature review has been performed.
3. Implement one bounded capability at a time in Cognitum; preserve the existing Lu repo as **read-only**. Host changes remain Proposed in the addenda until separately accepted by the Lu team.
4. Run P2 cross-platform tests and independently measured P3 Lu+same-model comparisons against a strong conventional baseline. Archive negative outcomes instead of rewriting hypotheses after the result.
5. Do not move a component to enabled/model-advertised/production-approved by changing a self-reported catalog field. Lu grants that authority.

**Documentation provenance:** Rev 1.5 prepared against Cognitum main 7776a423bd9b94bf2848af53b502fda76d601f83 (C05 scientific math PR #14) and read-only Lu CE development 2437c76174f6a67009bb0c9a795773d7663739a0 (draft PR #9). The CI evidence references in the master design are branch/build-specific; recheck head before release work.
