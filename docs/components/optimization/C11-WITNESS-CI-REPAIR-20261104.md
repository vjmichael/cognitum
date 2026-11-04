# C11 Windows/Linux native acceptance repair — 2026-11-04

## Root cause

The prior C11 matrix at head `3e375b39ab4482f5b02390a4499a38c5e8efea2c`
failed on Windows and Linux Python 3.11 and 3.13 because
`tests/test_c11_wire.py::test_untrusted_modified_witness_fails` expected
`decode_result` to reject `values=(2,4), objective=12` for the fixture
`0 <= a <= 2, 0 <= b <= 4, a + b >= 3`, costs `(4,1)`.

Those values **satisfy all hard bounds and the resource constraint**, and
their exact objective is **4*2+1*4=12**. The independent decoder therefore
correctly accepted this witness as feasible, even though its objective is not
minimum. The test was incorrect. It was not a HiGHS or OR-Tools runtime
failure, and changing the verifier to reject otherwise feasible solutions
merely to satisfy this assertion would have been unsound.

## Fix

- Replace the alleged invalid allocation witness with `(0,0)`, objective 0:
  this **violates** `a+b>=3` and must be rejected regardless of solver.
- Add a tampered objective test: `(2,4)` with alleged objective 11 must be
  rejected because its independently recalculated objective is 12.
- Add a *feasible but suboptimal* `(2,4)` test that must be accepted as a
  valid `FEASIBLE` witness. This makes the separation of feasibility from
  optimality explicit.

## Assurance boundary

`decode_result` independently validates all hard constraints and the
objective *value*. It does **not** independently prove a solver-produced
`OPTIMAL` status. That distinction is documented in the existing
`optimization_wire.py` and result limitations; the native HiGHS and
OR-Tools solver statuses remain solver claims. No authorization is inferred.

## Acceptance

The correction is committed to the C11 branch and native CI must establish
the new head's Windows/Linux Python 3.11/3.13 results before merge. The
prior 17 native tests included 16 passing, one faulty assertion; the full
Python regression of 485 likewise failed only on that same test (50 skips)
in the inspected Linux 3.11 log. Cross-platform claims for the new head
require new CI evidence, not inherited success.
