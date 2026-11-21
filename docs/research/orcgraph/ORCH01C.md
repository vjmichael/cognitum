# COG-ORCH-01C — Scientific data to existing authorized MEL/COG-06 workers

**Status: active bounded source candidate; native four-platform R1 qualification pending.** Orc Graph reuses the original scoped mathematical Runtime, Registry, Admission, worker, MEL DAG, COG-06 DAG, and independent mathematical verifier. No parallel scheduler, extra grant issuer, source-access daemon or Lu integration is added.

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

`execute_bound_mel` requires the original MEL `Admission` host and the exact Handoff, verifies the raw qualified source and a trusted freshness predicate *before* invoking the original `verified_graph.execute_verified`, and then rechecks immediately *after* verified mathematical execution. A stale/replaced source returns only a `stale_source` status, no graph outcome or numerical witness; original metered work stays charged. Revocation, cancellation, checkpoint pinning, numerical verification, and resource bounds remain the original MEL's responsibilities. Added native negative tests for source invalid before execution, source expiration after worker but before publication, tampered Handoff, wrong graph, cancellation, revocation, and successful source-bound KAN and VFA. This is a **publication guard**, not a second mathematical executor, background source watcher, OS security sandbox, arbitrary script capability, or license/authenticity attestor. In-flight cancellation remains host initiated using existing handles. R2 must pass the exact original combined 8-suite native regression scope plus new tests on the four platforms before ORCH-01C closes.
