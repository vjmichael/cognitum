# COG-ORCH-01A — First typed deterministic Orc Graph candidate

**Status: SOURCE CANDIDATE / FOUR-PLATFORM NATIVE ACCEPTANCE PENDING.** Owner-adopted design; not production eligibility, Lu integration or a new scheduler.

## Reconciled first-party infrastructure

| Existing module | Preserved function | Orc Graph boundary |
| --- | --- | --- |
| cognitum/contracts.py, registry.py, runtime.py, policy.py, worker.py | Closed requests, authorized installed routes, process worker dispatch and receipts | No new registry, authorization, worker or independent runtime |
| cognitum/cooperative.py and cooperative_cpu.py | 13 existing reviewed deterministic and statistical operations, four reviewed data bridges, exact/source-bound DAG, host admission, cancellation and verified publication | Orc Graph compiles directly into its existing Plan, Step and Dependency records |
| cognitum/mel/admission.py, mel/cooperation.py and verified_graph.py | Independently authorized HDC/KAN/MEL research execution, graph transformations and checker | Preserved; not silently enabled from COG-06 |
| cognitum/research/hdc_*, kan_*, ssm_* and timeaware | Research-grade mathematical engines and observed scientific comparisons | Catalogued as source-backed research candidates but explicitly NOT YET WIRED to this proposed CPU route |
| cognitum/capability_route_proposal.py | Earlier inert model-facing suggestions | Preserved, not interpreted as host permission |

## Actual bounded implementation

The new cognitum/orc_graph.py exposes immutable reviewable catalog entries for 13 existing COG-06 operations and four unwired HDC/KAN/SSM/ridge families, along with exactly the four existing reviewed bridge kinds. Their declared units and clock are NOT known by this descriptor profile. Only two trusted-host typed goal names are compiled: exact_linear (one step) and verified_integer_linear (two steps with the reviewed linear_integer_candidate bridge). Inputs are original canonical Protobuf frames bound to per-frame source hashes. Unknown research tools, non-exhaustive integer assurance and mismatched frames are refused.

The output is an **inert Proposal wrapping cognitum.cooperative.Plan**, with its original plan_digest. It does NOT grant authority or execute anything. The real CPU execution, independent verified result, admission on plan/compute/verify/publish, scope/build pin, source freshness, cancellation and all-or-nothing publication remain exclusively in the original cooperative.execute and Runtime. Independent HDC/KAN/SSM mathematical routing, end-to-end streaming data pipelines, learned selection and demonstrated increased scientific accuracy are NOT implemented in ORCH-01A.

## Acceptance requirements

- Four same-SHA native targets: Linux/Windows, Python 3.11/3.13.
- Dedicated new tests plus inherited tests/test_cooperative.py and tests/test_cooperative_compositions.py, all actual cases run without skips or failures.
- Native JUnit and seven unchanged source/test Git blob and SHA-256 identities, independently reconciled before scope closes.
- Negative cases for unknown/research operation, malformed frame, invalid route/bridge, cyclic DAG, invalid host scope/build/source, disabled registry, withheld admission, cancellation, and non-exhaustive proof.
- No stacked CI or claims of certified cross-site physical forecasting; accepted R4 physical source SHA cf78900c4fcec3981b93c842144c53b15cc0d411, 72 PARTIAL groups and all adverse outcomes remain untouched.

**Next after scoped qualification:** ORCH-01B units, clock, provenance, train-only scientific transformations; independent R4-R1 checkpoint/source data and untouched-site validation work remains open.

## ORCH-01A-R1 inherited dependency repair

Initial native run [44854337433](https://github.com/vjmichael/cognitum/actions/runs/44854337433) reached all four OS/Python cells but failed the **same three inherited planning/scheduling acceptance tests** per cell (60/63 tests passed in the first Linux 3.13 report). The new Orc Graph tests passed. Root cause: the new workflow installed the scientific extra but omitted the pre-existing optional C12 planning dependency, NetworkX. The original C12 planner correctly yields UNSUPPORTED without it; inherited tests require the real NetworkX graph path and accept only independently validated plan witnesses. **Repair:** add the existing planning-graph extra and pin networkx==3.5 to the native workflow; do NOT remove/skip/change planning tests or weaken verifier expectations. The first matrix was fully terminal before triggering a corrected candidate. Original first-run source SHA preserved for evidence, not accepted. R1 native result pending.
