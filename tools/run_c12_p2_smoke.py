"""Five *adapter* smoke scenarios with synthetic drivers, NOT real planner runtimes."""
import unittest
from tests.test_c12_p2_engines import EngineTests

NAMES = ('test_fast_downward_shim_checkable_plan',
         'test_up_shim_checkable_plan',
         'test_suboptimal_reported_as_feasible',
         'test_deadline_terminates_worker',
         'test_digest_changes_denied')

if __name__ == '__main__':
    suite=unittest.TestSuite(EngineTests(name) for name in NAMES)
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful(): raise SystemExit(1)
    print(f'C12 P2 PASS: {result.testsRun} adapter smoke checks (synthetic drivers only)')
