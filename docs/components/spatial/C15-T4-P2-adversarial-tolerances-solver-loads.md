# Cognitum C15 T4 P2 — interval tolerance, cross-joint numerical feasibility, and multi-mode load-case audit

**Date:** 2026-10-29. **Scope:** Research-only, caller-supplied claims, Protobuf-native, bounded read-only pure host call. **No Lu changes, no real actuation, no verified physical fitness or certified engineering safety.** C15 T3 VM restart/rollback/hard-off acceptance is postponed until the user's VirtualBox guest is reliable; no closed gates have been inferred from synthetic simulations.

## Architecture / compatibility

P2 is an **additive** independent Protobuf schema `proto/cognitum/spatial/v1/functional_material_p2.proto` importing the unchanged P1 contract. Its companion `cognitum/proto/spatial_functional_material_p2_pb2.py` is compiled from source. The new entry `cognitum/spatial_functional_material_p2.py` calls the P1 validator before processing any P2 object, preserving independent conversation/graph scope, unknown-field rejection, bounded object counts, immutable/conditional read-only semantics and absence of authorization. No P1 model, frozen R1 tracking state, P2Y/P2Z journal, VM fixture, or Lu runtime has been modified. The schema descriptor registry and README are updated for checkpoint visibility.

Findings can be `CONSISTENT_WITH_CLAIMS`, `CONTRADICTS_CLAIMS`, `UNDETERMINED`. A positive result means only **the explicitly simplified equations are compatible with caller-asserted bounds and scenario assumptions**; it does not imply authenticated evidence, calibrations, accuracy, material identity, action permission, structural strength, or a recommended design. A contradictory result means the conditional assumptions cannot all hold; it does not certify real hardware is defective. Both result `grants_authority` and `physical_validity_verified` remain false. `source_ref` strings identify claimed sources, **not cryptographic proof**.

## P2A — bounds and thermal tolerance

- Each numerical interval has a typed SI-compatible center and absolute radius, *both* with explicit unit, evidence status, and source reference. Unknown, missing, wrong dimensions, negative radii, nonfinite values, and unconstrained inversions cannot yield positive conclusions.
- A bore diameter interval `[B-,B+]` and shaft interval `[S-,S+]` yield conservative radial-independent diametral clearance `[B-−S+, B+−S-]`. The claimed minimum and maximum permissible clearance intervals are checked with universal containment for a robust positive result. Certain incompatibility is reported only when **all** allowed realizations violate an allowable bound; overlapping uncertainty is undetermined.
- A caller-declared thermal exposure requires separate bounds for bore/shaft expansion coefficients in `1/K` and a temperature change range in kelvins, each marked with evidence class and source. The first-order model `d(T) = d_ref (1 + alpha ΔT)` uses conservative interval products. Unspecified thermal exposure and thermal model domains are **not independently discovered**; if exposure is declared but its measurements are missing or imply nonpositive geometry, the result is undetermined. No thermal stress, contact deformation, nonlinear material laws, or correlation tracking is implemented.
- A scale-aware numerical band abstains near tolerance boundaries. These are conventional floating-point ranges with conservative analytic guards, **not** rigorously outward-rounded IEEE interval-arithmetic certificates; roundoff and correlated measurements require further validation.

## P2B — limited cross-joint feasibility via SciPy HiGHS

- Supports bounded sets of at most 12 joints and 32 additional linear constraints, referencing actual T4 P1 joint checks. Joint families must be dimensionally homogeneous (prismatic length or revolute angle); mixed translational/rotational sums without unit-aware transformation are rejected. `enforce_candidate_positions` optionally restricts the assembly to proposed positions as well as joint limits.
- An independently available SciPy HiGHS linear program checks feasibility of all joint ranges and linear couplings. Infeasibility is a **numerical conflict indication**, not a formal unsatisfiability proof or nonlinear linkage result. Positive results require a numerical interior-margin check. Solver missing, inconclusive, near-boundary, incomplete or provisional evidence produces `UNDETERMINED`. Feasibility under *some* uncertain coupling bound cannot prove feasibility under *every* allowed bound, and is also `UNDETERMINED`.
- This is not a URDF frame/axis transform, 3D kinematic loop closure, collision/contact test, torque or dynamics solver. No real-world joint motion is granted.

## P2C — conservative multi-scenario load ratios

- Each envelope supplies bounded axial area, shear area, section modulus, asserted allowable normal and shear stresses and an explicit factor `>= 1`. Each of up to 16 load cases includes signed axial force, signed shear force, signed bending moment (SI N·m), optional compression buckling limit and optional cyclic-life claims.
- Simplified conservative normal stress is `|F_axial|/A + |M|/Z`; scalar shear is `|V|/A_shear`. The worst ratio of their claimed allowances, the claimed compression/buckling force ratio when axial force may be negative, and the claimed cycle count ratio is compared with `1` across all scenarios. A positive result requires *every* modeled bound and case strictly within its limit. Certain overload is a conditional contradiction.
- Missing declared load evidence, a compression case with no buckling claim, a cyclic case without a fatigue limit, zero-crossing denominators or provisional inferred inputs produce `UNDETERMINED`, unless there is already a certain contradiction. Positive results cannot imply safe buckling or fatigue life: the cycle ratio is **only a caller-asserted count consistency check**, not an S–N curve, Palmgren–Miner damage model, fatigue design code, shear/bending tensor criterion, shear buckling, contact, or finite-element analysis. Temperature, torsion, multidirectional vectors, boundary conditions and safety-critical stress concentrations remain outside this prototype.

## Validation and falsifiability

- Independent symbolic endpoint oracle via SymPy for 70 seeded interval fixtures; independent SciPy `linprog` feasibility oracle for 65 seeded assembly fixtures. Direct symbolic arithmetic fixture covers a 1000 N / 100 mm² + 5 N·m / 1000 mm³ normal stress example (`15 MPa`), without claiming strength approval. Comparisons exercise independently constructed *calculations*; they do not authenticate input measurements.
- New negative tests cover near-equality numeric failures, thermal expansion, missing/corrupt evidence, unsupported dimensional sums, uncertain coupling, multiple load cases, buckling/fatigue absence, inferred claims, NaN/Inf, and size limits. Sources and protobuf descriptors are compiled/matched independently, including all predecessor schemas.
- The unit suite uses `python -m pytest -q tests/test_c15_t4_p2_intervals_solver_loads.py` and `python /tmp/verify_cognitum_t4_p2.py` in the development environment; the latter is a local audit script, not bundled as a production application component. Tests require the available SciPy/SymPy research dependencies; normal P1 validation does not.

## Acceptance boundaries and next gate

| Gate | Status after P2 portable suite |
|---|---|
| P2 contract, scope and fail-closed path | Implemented / portable checked |
| Interval fit + first-order thermal case | Implemented / independently tested as algebra |
| Same-dimension linear joint coupling and HiGHS checks | Implemented / independent solver parity, not formal proof |
| Signed axial/shear/bending cases and claimed fatigue/buckling limits | Implemented / simplified conditional audit only |
| Authentic independent measurement sources, calibrated T2/T3 provenance | **OPEN** |
| Robust floating-point interval certification and correlation model | **OPEN** |
| Validated 3D kinematics, FEA and real engineering materials | **OPEN** |
| P3 real held-out measurements and domain-expert falsification | **DEFERRED** |
| Windows VM reboot/snapshot rollback/hard-off T3 gates | **DEFERRED; not passed** |
| Lu trusted native extension and physical authorization | **NOT IN SCOPE** |

Prior immutable/CI evidence is preserved as predecessor documentation; this work does not reclassify a physical gate or promise safe action.

Mature reference families: NIST SI https://physics.nist.gov/cuu/Units/ ; SciPy optimization / HiGHS https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linprog.html ; SymPy symbolic analysis https://docs.sympy.org/latest/modules/solvers/solvers.html .
