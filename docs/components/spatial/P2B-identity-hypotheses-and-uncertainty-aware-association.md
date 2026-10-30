# C15 T1 / P2B — Identity hypothesis generation and bounded association

**Date:** 2026-10-28. **Status:** Offline research reference, not full multi-object tracking or host identity validation. **Scope:** Cognitum only; no Lu changes or application-specific code.

## Purpose and findings

P2A showed that the P1 scene reference will accept same-class position exchanges under an already host-assigned ID; its security checks cannot prove a physically correct ID. P2B introduces a **separate, read-only `AssociationHypothesisSet`** to propose multiple possible assignments from unlabeled observations without changing P1 scene state or interpreting an algorithmic score as authority.

The research conclusion is deliberately conservative: **the nearest or globally minimal position-based match can be physically wrong.** At an exact exchange of two visually indistinguishable objects, two geometrically consistent observations do not determine whether the objects crossed or stayed. A one-frame motion-gated matcher cannot resolve that missing evidence. The P2B prototype always marks multi-object matches of the same class and source `AMBIGUOUS` rather than certify identity from geometry alone. It still ranks candidates to guide future discriminative tests. This conservatism can over-abstain; evaluate that cost before deployment.

## Prior art and mathematical choice

This is an intentionally bounded **multiple-hypothesis global assignment baseline** using position-only association. Conventional assignment algorithms such as SciPy `scipy.optimize.linear_sum_assignment` solve the minimum-cost bipartite matching problem for an assignment cost matrix; a 30-seed test independently compares P2B's top-ranked full matching to SciPy. Reference: https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linear_sum_assignment.html . This is **not** a trained tracker, Kalman/JPDA posterior, appearance matching, differentiable pose prediction, or CAPS demonstration.

For observation `i`, track `j`, and 3D world-frame positions `z_i`, `p_j`, an admissible pair must satisfy category/source equality, a newer observation tick, and a motion gate:

`distance(z_i, p_j) <= v_max * (tick_i - last_seen_j) + 3 * sigma`.

Its reference *ranking cost* is `c_ij = distance(z_i, p_j)^2 / (2 sigma^2)`; unassigned observations have fixed nonzero penalty `c_unmatched`. Generate one-to-one complete hypotheses (including unmatched) and return the top K by total cost. `exp(-cost)` normalized **over returned top K only** is a relative ranking weight, **not a calibrated probability of identity** and not a signed provenance statement. A valid but expensive match can lose to an unmatched proposal. Motion ticks are synthetic order units, not seconds, so speed per tick is NOT a physical maximum velocity. No covariance, shape or appearance evidence is admitted in P2B.

The exact enumeration is capped to **6 observations and 6 active tracks** (8 returned hypotheses maximum). It is a small deterministic reference, not a scalable production assignment implementation. Resource caps and strict validation are intentional.

## Trust and state invariants

- **Internal wire:** `proto/cognitum/spatial/v1/identity.proto` with compiler-matched `cognitum/proto/spatial_identity_pb2.py`; original `scene.proto` unchanged.
- **Read-only inputs:** scene snapshot hash must match the supplied snapshot, and scene/conversation/task/trace/request identifiers are validated. The scene SHA guards against accidental mismatch, **not against a malicious caller who replaces both snapshot and hash**.
- **No canonical identity updates:** `propose(...)` is pure. A separate, authenticated Lu host decision would be required for changing scene state; no such host integration is supplied or implied.
- **Fail closed:** unknown frames, invalid numerical scales, stale matching timestamps, source/category mismatch, duplicate observation IDs and excessive inputs are rejected or marked unmatched.
- **No trust conversion:** labels, relative weights and hypotheses cannot create tool authority. The replay verifier checks the deterministic algorithm's output, **not** source identity, signature validity, or physical ground truth.
- **Conservative ambiguity:** near-tied alternatives and multiple same-category/same-source matched observations are marked ambiguous. A unique geometric best never proves physical identity.

## Experimental evidence (synthetic only)

`tools/run_c15_p2b_association_study.py` generates **120 seeded scenarios (6 families × 20 seeds)** with ground-truth identities available to the evaluator but hidden from the matcher. Full cases, hashes, and warnings: `P2B-synthetic-association-evidence.json`.

| Scenario | Top candidate correct | P2B decision (20 trials each) | Interpretation |
| --- | ---: | --- | --- |
| Stable same class | 40/40 identity pairs | AMBIGUOUS | Conservative over-abstention; location matched true identity, but was not proof |
| Exact physical position swap | 0/40 pairs | AMBIGUOUS | **Correctly refuses to certify a wrong geometric ID ranking** |
| Near-tied midpoint | 20/20 selected by deterministic tie-break | AMBIGUOUS | Ground truth is arbitrary and not recoverable from one midpoint observation |
| Distinct categories | 40/40 pairs | CANDIDATE_ONLY | Stronger disambiguation cue (category) but still no authority |
| Source mismatch | 0/40 pairs | NO_COMPATIBLE_MATCH | Cross-source ID transfer is blocked pending reviewed provenance |
| Long occlusion | 40/40 pairs | AMBIGUOUS | Historical pose is not current-location evidence |

These figures are from simple **synthetic construction**, not a benchmark against strong learned trackers or real object recognition; successful abstention alone is not tracking success. The correct improvement sought next is **discriminative evidence and temporal continuity**, with abstention measured alongside accuracy and recoverability.

## Validation

- **C15 tests:** 69/69 passing: 28 new core cases, two SciPy parity/performance cases, 14 P2A baseline cases, and 25 P1 scene reference cases.
- **Selected inherited regression:** 793 C13+C14 tests run, **754 passed and 39 optional skips**, zero failures.
- **Protobuf:** 51/51 source schemas independently compiled and matched checked-in descriptors (added `identity.proto`).
- **Synthetic study:** 120/120 completed, zero `grants_authority`.
- The unrestricted all-component historical suite has not been rerun here.

## Remaining research gates

**T1 P2C:** temporal multiple-hypothesis tracking with motion/appearance evidence, explicit confidence calibration and identity switches under collisions; stronger baselines (Kalman + Hungarian/ByteTrack-style matching and MOT metrics) with actual annotated sequences. Benchmarks must report IDSW, association precision/recall, abstention, recovery latency, CPU/RAM, and failure cases. **T2/T3** part–whole composition and occupied/free/unknown volumetric representations follow independently. CAPS remains an optional research challenger whose value must be measured against conventional methods. Lu/Windows confinement, real sensors, durable replay journaling, authenticated host, real LLM and real-world inference are still not tested. C14 G15 real-model benchmarking remains deliberately deferred.
