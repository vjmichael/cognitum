# C19 real topology CI repair: duplicate-point H0 zero intervals

2026-11-04 — PR #75, branch `c19-topology-practical-20261104`

## Observed native acceptance

At head `b8cb6345c34e3df8f423884be233794b1a9dfb69`, C19's dedicated
real Ripser/GUDHI/SciPy test matrix **passed Windows** Python 3.11/3.13,
but **failed Linux** Python 3.11/3.13 with exactly one TDA case:
`test_duplicate_and_degenerate_points` raised
`independent SciPy H0 merge count differs`. Other C19 shape, independent
GUDHI, persistence sensitivity, and held-out benchmark cases passed.

The previous generic Python regression passed on Linux but failed on
Windows in unrelated Linux-only host-recovery tests.

## Numerical root cause and resolution

For identical coordinates, the Vietoris-Rips H0 filtration has
zero-length merges among duplicate observations. A persistence engine
may suppress ephemeral (birth=death) intervals from its returned
diagram. A SciPy sparse MST also treats literal zero edge weights
as absent, which is why C19 already constructs an MST on **unique**
coordinates and independently counts `N - unique_count` zero mergers.

The prior cross-check compared all returned finite H0 bars directly
against that complete independent list and rejected a valid collapse
of zero-duration bars. The fix:
1. Counts returned exact-zero H0 intervals and rejects any count
   exceeding the number justified by exact duplicate samples.
2. Restores only those **mathematically determined zero-duration** H0
   intervals omitted by Ripser.
3. **Does not synthesize any positive-persistence intervals**: all
   positive H0 merge lengths still must match SciPy's unique-point MST
   within the existing numerical tolerance.
4. Adds controls for duplicate groups that remain disconnected at a
   low filtration threshold. Essential classes remain distinct.

The original inputs, metric, filtration thresholds, Ripser/GUDHI
libraries, result limits and independent verifier remain unchanged.

## Acceptance boundary

This is a source/test repair, **not a claim that the latest matrix
passed**. The latest exact PR head must pass genuine native Windows
and Linux Python 3.11/3.13 C19 acceptance before merge. The C19
held-out geometry/spectral/topology comparison remains synthetic and
does not prove practical transformer augmentation or real-world
generalization. No extra topology research sprint is justified.
