# Cognitum C15 T4 — P0 baseline selection and P1 conditional material/function audit

**Date:** 2026-10-29. **Status:** P0 research design + P1 portable prototype implemented; T4 P2 adversarial validation and P3 held-out genuine benchmark remain open. Research-only, read-only, Protobuf-native. No Lu changes and no physical-actuation authority.

## Why this track exists

T2 can report claimed part–whole relations; T3 can report occupancy/free/unknown evidence. Neither establishes that a geometrically plausible connection actually fits, an articulated joint can reach a proposed configuration, or a stated load remains within a claimed stress or deflection limit. In particular, visual plausibility, a material name, class priors, and a simulated result are not physical certification.

## P0: competent numerical and engineering baselines

Use explicit dimensioned quantities, conservative interval validation and finite numeric checks before researching automated material priors, CAD/robotics import, or uncertainty propagation.

| Concern | Mature reference | Cognitum P1 slice | What is still excluded |
|---|---|---|---|
| Units and dimensions | SI (NIST); established unit-aware kernels (e.g. Pint) | typed enum for m/mm, N/kN, Pa/MPa, N/m and N/mm, rad/deg, m²/mm² | comprehensive units, temperature, uncertainty covariance |
| Dimensional fit | toleranced contact/clearance checks, mechanical design literature | circular bore minus shaft with explicit min/max claimed clearance | coaxiality, temperature, geometric tolerancing, elastic interference/contact |
| Joint kinematics | ROS URDF fixed/revolute/prismatic joint semantics; geometric constraint solvers | conditional scalar range checks; fixed displacement must be zero | axis/frames, linkage loops, forces/torques, collisions |
| Static material adequacy | elementary stress = force/area with explicit factor; scientific solver baselines | one uniaxial claimed stress allowance check | buckling, fatigue, shear, temperature, yield/fracture modes |
| Stiffness | linear spring F=kx | a supplied linear-stiffness/deflection check | material-derived stiffness, bending/torsion, nonlinear models |
| Compound systems | SciPy optimize, SymPy, C05/C10/C11 | intentionally not implemented in P1 | full constraint solving and model feasibility certificates |

SciPy's HiGHS linear-programming interface is the mature reference for *future* bounded linear feasibility; it is **not** exercised by this prototype. Mature ROS URDF describes a limited joint-type taxonomy, not an assessment of material fitness. No claim of broad SI compliance or standard-specific engineering certification is made.

References: NIST SI (https://physics.nist.gov/cuu/Units/); SciPy `linprog` (https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linprog.html); URDF joint documentation (https://mirror.umd.edu/roswiki/urdf%282f%29XML%282f%29joint.html).

## P1 implementation and hard boundaries

- `proto/cognitum/spatial/v1/functional_material.proto` is a new **v1 Protobuf** contract; `cognitum/proto/spatial_functional_material_pb2.py` is compiler-derived and checked by `tools/check_proto_descriptors.py`.
- `cognitum/spatial_functional_material.py` is a pure deterministic, host-called, read-only checker. It does not mutate P1/T2 scene state or consume T3 volumes, launch workers, or request external tools.
- Input scope requires graph/conversation identifiers, `research_only=true`, `grants_authority=false`, known protobuf fields only, bounded part/check counts and message byte limit. Unknown objects, self-connections, duplicate checks, unknown units, inconsistent dimensions, infinite/NaN values and malformed quantities are rejected.
- Each engineering number carries its unit, evidence classification and source reference; source references are **not cryptographic authentication**. Measured/datasheet classifications mean only *claimed by the caller*.
- Each finding is **consistent with claims**, **contradicts claims**, or **undetermined**. Missing bounds or inferred/hypothetical inputs cannot produce a positive consistency result. Contradictions involving hypotheses mean *the stated assumptions disagree*; they do not certify a physical defect. Numeric equality or near-boundary comparisons are marked undetermined to avoid false numerical certainty.
- A 32-byte SHA-256 request digest supports deterministic *identity* of the supplied request, **not** source authenticity, authorization, data provenance or tamper-proof durability.
- `physical_validity_verified` and `grants_authority` always remain false. Absence of findings is not a pass. **Never route these findings into real-world physical action, medical diagnosis, or safety decisions.**

## Focused fixtures

1. Bore/shaft in mixed metres and millimetres: 10.2 mm - 10.0 mm = 0.2 mm, between 0.1 and 0.3 mm => conditionally consistent.
2. Oversized shaft: conditional fit contradiction. Missing tolerance: undetermined.
3. Joint angle 45° between -90° and +90° => conditional consistency. 180° => contradiction. Prismatic joint given angle units => rejected.
4. Claimed 1000 N on 100 mm² => 10 MPa versus 100 MPa / safety factor 2 = 50 MPa: conditional consistency. Higher force => contradiction. This simplistic uniaxial equation is *not* an engineering safety check.
5. 10 N / 10 N/mm = 1 mm deflection within 2 mm claimed limit. Hypothetical stiffness => undetermined.

## Gates and next implementation

| Gate | State |
|---|---|
| T4-P0 scientific baseline and explicit scope | DOCUMENTED |
| T4-P1 typed contract and 4 read-only check families | IMPLEMENTED |
| T4-P1 unit, negative, missing, unknown-field, resource, provisional tests | PORTABLE PASS (see evidence JSON) |
| T4-P2 adversarial uncertainty, tolerance interval arithmetic, mixed joint graph / solver parity | OPEN |
| T4-P3 independent held-out engineering data and material-model falsification | DEFERRED |
| Lu integration, authorized physical controls, Windows/VM acceptance | NOT IMPLEMENTED |

T3 VM-dependent gates are **deferred**, not green, after intermittent VirtualBox black-screen restarts. Preserve existing Windows process-level acceptance reports and any user-owned safe reboot evidence without silently converting those into production storage/snapshot/power-loss certification. The independent outside-VM monotonic witness remains mandatory before anti-rollback acceptance.
