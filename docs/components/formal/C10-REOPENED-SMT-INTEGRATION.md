# C10 reopened — established SMT backend implementation status

**2026-11-04.** The user's "close it out" instruction means implementing as much of
the original design as practical using existing mature libraries rather than
entering indefinite research/optimization. The earlier bounded-only closure
is superseded; C10 remains actively under development.

## Adopt, don't reinvent

- **Primary solvers:** Z3 and cvc5, optional Python packages. Both have
  native algorithms for SMT and theory reasoning; do not write a new SAT/SMT
  engine as the production path.
- **Cognitum-owned glue:** strict typed mathematical schema, bounded model
  building (never execute raw model-authored SMT-LIB), canonical Protobuf,
  local SAT witness verification, honest UNSAT evidence classification,
  versioned limits, normalized status and safe failure.
- **Small independent reference:** `formal_boolean.py` is retained only to
  check tiny Boolean CNF formulas and distinguish exhaustive UNSAT from
  inconclusive search. It is not an incumbent replacement.

## Implemented this branch

- `formal_smt.py`: restricted QF_LIA linear integer variables and atoms,
  optional Z3 and cvc5 adapters, up to eight named bounded integer
  variables, each range width <=32, 64 constraints, 128 terms and 10s solver
  logical timeout. SAT witnesses are checked in plain Python with exact
  integers. Domain searches <=4096 combinations are independently
  enumerated before UNSAT can be marked `UNSAT_EXHAUSTIVE`.
- `proto/cognitum/formal/v1/formal.proto` and
  `cognitum/proto/formal_pb2.py`: native typed mathematical wire schema.
- `formal_wire.py`: strict canonical Protobuf validation and response
  correlation hash (not a signed receipt), independent SAT and finite-domain
  UNSAT verification, no untyped executable payload.
- `tests/test_c10_smt.py`, `tests/test_c10_boolean.py`,
  `tests/test_c10_formal_wire.py`: finite exhaustive witnesses,
  unsupported/budget states, malformed types and transport, dishonest
  status/assignments, genuine backend test cases when packages installed.
- `.github/workflows/c10-smt-backends.yml`: CI jobs to install each real
  optional solver on Windows/Linux Python 3.11/3.13.
- `pyproject.toml`: separate `formal-z3` and `formal-cvc5` extras so
  they do not become mandatory for all Cognitum installations.

## Strict distinction between results

- `SAT`: valid bounded assignment, independently re-evaluated against
  all original input atoms.
- `UNSAT_EXHAUSTIVE`: all finite integer assignments independently
  enumerated, not a Z3/cvc5 proof certificate.
- `UNSAT_UNVERIFIED`: backend reported UNSAT where independent finite
  enumeration was too large; **not** called certified.
- `UNKNOWN`: a solver did not establish either conclusion, or a bounded
  reference budget expired.
- `UNSUPPORTED`: missing backend or unsupported operation.

The Protobuf hash correlates request bytes with results but is not
authentication of a host, OS isolation, a trusted proof or worker identity.

## Remaining production gates — actionable engineering, not research

1. Check Python API and package compatibility against **actual** Z3/cvc5
   execution on Windows/Linux; no CI passing claim until jobs complete.
2. Add theorem-appropriate independently checkable UNSAT proof certificate
   support where available; reject unsupported proof formats rather than
   falsely certifying solver-reported UNSAT.
3. Widen the typed theory support deliberately (BitVec/arrays/reals) only
   through established solver APIs and supported verifier rules.
4. C02/C04: native Lu host permission, OS worker isolation and process
   cancellation; C03: real Lu model/formalization A/B benchmarks.
5. License/version/dependency lock, resource consumption, adversarial
   model reconstruction and delivery validation.

No first-party generalized SMT solver implementation is planned.
This status is **C10 reopened, implementation underway**, not closed.
