# CH40-L.2 — independently recomputed child upper bounds and selective continuation (2026-11-03)

**Engineering gate: PASS_FINITE_ROOT_RATIONAL_CHILD_BOUND_RECOMPUTATION. Scientific release: NO_GO.**

From the frozen original CH23/CH40J trace for quasi_separated_n160_i00, two highest-cap terminal-box splits were generated using exact rational midpoint partitions and newly computed *rational interval direct upper bounds* (95-digit libmpdec exp/log widened outward). Child effective caps were independently recomputed by a separate read-only program and inherited the proven parent cap via min(new local direct upper, parent effective upper). This is NOT a new 224-bit MPFR producer witness; the auditor shares the existing rational mathematical kernel, so it is separate invocation rather than independently implemented transcendental math. Original 127-node signed evidence was not modified.

Selective results: 2 new splits, frontier 64 -> 66, global upper ceiling -0.8515533432822371435391240974218277532423720980568602970 -> -0.9594304398558831651674650567095693837162901263109427645. Verified upper reduction >= 0.107877096573646. Combining with CH40-L's previously certified unchanged feasible incumbent yields finite-root gap <= 7.054594372356903, previously <= 7.162471468930549; target 0.05 remains unmet.

Breadth-first control, 3 splits and 67 frontier leaves, had unchanged global ceiling. Measured CPU: selective ~2.365s, baseline ~2.126s summed over resumed run, a near-equal (11.2% difference) CPU budget; **not an exactly equal-CPU benchmark**. Both used the frozen original case, not synthetic data. The selective journal survived an explicit resume with the same verified terminal state.

Journal: append/fdatasync-equivalent Python flush+fsync with chained content hashes, exact child partition, inherited-cap constraints, frozen trace SHA-256 pin, and independent read-only recalculation. 7/7 focused tests passed, including hostile altered bounds, altered digest, truncated tail, changed source identity. Hash chaining detects corruption but is not an authenticated/off-host trust anchor; final-record tear recovery and SIGKILL at each append stage are still open. Refusal rather than silent acceptance for torn tails.

Reproducible source, accepted local journals, tests and manifest packaged outside the repository as Cognitum_CH40L2_Verified_Selective_Continuation_2026-11-03.zip (SHA-256 80ea51826539d63cd703d0d96b890ece45dfc745768390dbf09a2c46b1ea3d7d; 12,437 bytes). Depends on prior immutable CH40J/CH40K/CH40L artifacts; this GitHub note does not commit the Python sources.

Next: native MPFR source-traced child proofs and distinct-kernel checker, journal crash-stage tests and authenticated anchoring, and near-equal/exact equal-CPU multi-dataset continuation. **No unrestricted global optimum, 0.05 finite-root closure, or C14 scientific release is certified.**
