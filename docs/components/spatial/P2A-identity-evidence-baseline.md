# C15 T1 / P2A — Identity and evidence adversarial baseline

**Date:** 2026-10-28 · **Status:** BEGINNING OF P2 RESEARCH TESTING ONLY, not full object association, not volumetric reasoning, not a tracker.

The existing P1 typed scene reference and its `scene.proto` were preserved byte-for-byte. A new adversarial test module uses only native `cognitum.spatial.v1` messages and the existing deterministic host-admission seam.

**Tests (14):** duplicate display names remain distinct; renaming and aliases maintain identity; occlusion withholds current visible relations; cross-sensor re-observation is denied; category changes denied; deletion tombstone not resurrected; scope mismatch denied; nonmonotonic observations denied; failed mixed batch atomic; host denial enforced; untrusted labels inert; unknown visibility retains last historical position; invalid frame quaternion denied; and one intentionally documented **same-class identity-swap detection gap**.

**Critical negative finding:** with valid host-provided IDs, same category/source, and fresh ticks, two objects swapping coordinates is accepted by P1. **This does not certify the IDs as correct** and is not solved by these tests. Position history without actual time units, appearance evidence, or cross-sensor covariance cannot independently establish identity. Similarly, stored occluded poses are historical positions, not claims of currently known location.

**Next:** propose typed `IdentityHypothesisSet` with explicit evidence, association likelihoods, multiple hypotheses and an `AMBIGUOUS` outcome; require host decision before changes to canonical IDs. Compare gating and assignment baselines with ground-truth swaps/occlusions. Never use an algorithm's self-reported confidence as a provenance signature. Do not admit learned trackers before separate benchmark.

**Out-of-scope still open:** per-object confidence decay, uncertainty covariance, cross-sensor legitimate match, autonomous camera collection, persistent journal/revocation, Windows security, authenticated Lu host, trained CAPS, and real-model testing (deferred). **No release-level guarantee** is implied by 14 passing baseline probes.
