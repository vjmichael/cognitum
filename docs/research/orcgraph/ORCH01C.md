# COG-ORCH-01C — Scientific data to existing authorized MEL/COG-06 workers

**Status: ACCEPTED BOUNDED FOUR-PLATFORM NATIVE HANDOFF at exact SHA `0246b693c19995af906173f420b4535a789b3ec7`.** Orc Graph reuses the original scoped mathematical Runtime, Registry, Admission, worker, MEL DAG, COG-06 DAG, and independent mathematical verifier. No parallel scheduler, extra grant issuer, source-access daemon or Lu integration is added.

## Exact source and qualified routes

| Method | Retained native execution | Input and limitations |
| --- | --- | --- |
| Classical temporal.kalman | Reviewed COG-06 cooperative CPU graph and independent C17 replay | Original SHA-qualified 01B train observations with relative UTC timestamps, masked missing/late rows, and a host-supplied bounded model. No model training. |
| VFA evaluation | Original MEL Seed-to-Vfa graph and verified_graph with host-issued Admission grant | 01B train-only standardized, availability-safe two-feature samples; host-selected typed function. No learned forecasting claim. |
| KAN evaluation | Original MEL Seed-to-Kan graph and verified_graph with host-approved exact checkpoint | Two-feature samples and exact 2-input/1-output checkpoint. Binary64-to-binary32 conversion refused by default; the trusted host can specify a finite max_binary32_error tolerance between 0 and 1e-4, bound to the source/plan identity and recorded as measured loss. Numerical witness covers represented inputs, not the pre-rounding source. |

The Handoff is immutable and inert. It reports source SHA-256, qualified source identity, chronological fold, exact cohort fingerprint, graph identity, and any explicit binary32 conversion loss. It does not contain host grant tokens. check_source_current independently reparses raw bytes and requires an exact trusted freshness predicate. The trusted host must run that check before execution AND before source-bound publication, driving the existing Cancellation and Admission revocation on midflight source changes. The MEL native runtime itself has no intrinsic source_current callback; this engineering stage does not claim autonomous polling or guaranteed in-flight source revocation. The original COG-06 CPU graph already rechecks source stamps before and after computation and at publication.

Declared quantities and units are not authenticated original physical sensor metadata. HDC, research SSM and ridge are not yet direct Orc Graph specialist handoffs. Neither VFA nor checkpoint-only KAN evaluation demonstrates a real-world forecasting improvement.

## First fully terminal native candidate

Run https://github.com/vjmichael/cognitum/actions/runs/44856813297 was terminal FAILURE in all four cells; Ubuntu/Python 3.11 reported 244/247 passing. Three new-test findings: KAN correctly refused implicit lossy float conversion, a changed-source identity fixture exceeded a valid declared domain, and the synthetic forgery test targeted a nonexistent verifier symbol. R1 is a single repair batch: keep MEL strict binary32 gate and add an explicit bounded conversion policy, use an in-domain changed source, and corrupt the real Runtime verification response to test refusal. No inherited tests or proof thresholds were removed or weakened.

## Native qualification contract

Require one unchanged candidate SHA: Windows/Linux Python 3.11/3.13. Run dedicated 01C cases, unchanged 01B/01A and CPU suites, plus prior MEL-04B and MEL-05B guarded execution suites without skips/errors/failures. Independently check the four artifact ZIP digests, CRC, per-case JUnit names, source/blob identities and native dependency versions. Preserve the distinct accepted 01A SHA 5345c998ddd84b22063a7a5b865ff586644b424a, 01B SHA 5dc8f99316619670297cdfbbe4aeef428f0e41eb, and R4 SHA cf78900c4fcec3981b93c842144c53b15cc0d411.

## Remaining holds

Original upstream sensor/units and physical sources are not cryptographically authenticated; model training, true ridge/SSM/HDC cross-site comparisons and learned routing are not yet part of this stage. No installed user-host revocation integration or physical Windows workstation acceptance is implied by CI. The later owner-requested [Orc-vs-ridge experiment](ORC_VS_RIDGE_BENCHMARK_PLAN.md) remains reserved and not executed.

## R1 native evidence and remaining source-publication gap

[Run 44857126789](https://github.com/vjmichael/cognitum/actions/runs/44857126789) completed native SUCCESS at unchanged source `f7b19cb4703327e63019126772ab770ced7eb0a3`, 250/250 on all four Ubuntu/Windows Python 3.11/3.13 targets, 1000 native testcase executions, zero skips/errors/failures. All four ZIPs independently downloaded and SHA-256/CRC/JUnit/source-blob verified (same 250 test identities and 19 Git source/test blobs). This qualifies actual VFA, host-approved KAN with explicit bounded binary32 rounding, and CPU Kalman via original worker interfaces. It does NOT by itself guarantee that MEL's caller rechecks source freshness after completing the worker.

## R2 hardened host-owned publication gate — native acceptance pending

`execute_bound_mel` requires the original MEL `Admission` host and the exact Handoff, verifies the raw qualified source and a trusted freshness predicate *before* invoking the original `verified_graph.execute_verified`, and then rechecks immediately *after* verified mathematical execution. A stale/replaced source returns only a `stale_source` status, no graph outcome or numerical witness; original metered work stays charged. Revocation, cancellation, checkpoint pinning, numerical verification, and resource bounds remain the original MEL's responsibilities. Added native negative tests for source invalid before execution, source expiration after worker but before publication, tampered Handoff, wrong graph, cancellation, revocation, and successful source-bound KAN and VFA. This is a **publication guard**, not a second mathematical executor, background source watcher, OS security sandbox, arbitrary script capability, or license/authenticity attestor. In-flight cancellation remains host initiated using existing handles. R2 **PASSED** the unchanged original eight-suite combined acceptance scope on all four platforms, 257/257 each; details below.

## Final R2 verified acceptance and precise limitations

[Native workflow run #44857436422](https://github.com/vjmichael/cognitum/actions/runs/44857436422) is terminal **SUCCESS**, exact SHA `0246b693c19995af906173f420b4535a789b3ec7`, with four native OS/Python cells (Ubuntu and Windows, Python 3.11 and 3.13), **257/257** tests each and no failures/errors/skips. Source identity remained locked throughout all 1,028 case executions. Original archived ZIP bytes were independently downloaded, SHA-256 checked and ZIP CRC verified; JUnit tests and nine? **nineteen** source/test canonical Git blob identities were reconciled across all four native environments. See [ORCH01C_NATIVE_ARTIFACTS.json](ORCH01C_NATIVE_ARTIFACTS.json) for exact SHA-256, artifact IDs, test-case identity digest, dependencies, source pins and OS-specific limitations.

Testcase composition per platform: 41 dedicated ORCH-01C, 70 inherited ORCH-01B, 31 inherited ORCH-01A, 32 inherited COG-06, 60 MEL-04B, 4 MEL-05B graph acceptance and 19 MEL-05B inline refusal cases. This is **257 unique tests repeated on four targets**, not 1,028 independent scientific experiments. Eleven raw working-tree Python file SHA-256 digests differ Linux vs Windows despite identical Git object identities; no bitwise working-tree agreement is asserted.

**Accepted engineering boundary:** legitimate host-granted MEL VFA and exact host-approved KAN evaluation, as well as original COG-06 Kalman numeric replay, run on source-qualified scientific inputs; original numerical verification, cancellation and revocation remain in place. Host-owned `execute_bound_mel` ensures source checks before and after verified computation, refusing stale-source results and witness on publication while retaining charged work. Explicit opt-in and bounded binary32 conversion is recorded; verification covers the numeric representation actually supplied to the KAN checkpoint, not the unrounded research measurements.

**Not accepted:** continuous in-flight source monitoring, protected native OS worker custody on a physical installed computer, original publisher instrument authentication, any automatically trained/selected HDC/KAN/SSM forecasting systems, real independent time-aware multi-engine composition, accuracy over ridge, calibrated forecast interval coverage, KAN bitwise checkpoint determinism, or production Lu integration. Physical R4 source lock `cf78900c4fcec3981b93c842144c53b15cc0d411` and all 72 PARTIAL SSM DS groups are preserved. The next independent engineering phase is **COG-ORCH-01D**. The owner-requested post-Orc ridge falsification test [ORCH-01E-BENCH-01](ORC_VS_RIDGE_BENCHMARK_PLAN.md) remains reserved, not executed.
