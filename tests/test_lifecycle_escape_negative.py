"""Native Linux P49 negative and baseline control: group kill is not a sandbox."""
import sys
import unittest
from pathlib import Path
from cognitum.lifecycle_escape_negative import run_negative_control, SCHEMA


@unittest.skipUnless(sys.platform.startswith('linux') and Path('/proc').exists(), 'Linux /proc only')
class BreakawayNegativeControls(unittest.TestCase):
    def test_breakaway_survives_process_group_cancel_but_is_cleaned(self):
        receipt = run_negative_control(breakaway=True)
        self.assertEqual(receipt['schema'], SCHEMA)
        self.assertTrue(receipt['observed'], receipt)
        self.assertFalse(receipt['child_group_matches_supervisor'])
        self.assertTrue(receipt['child_survived_group_kill'])
        self.assertTrue(receipt['boundary_gap_observed'])
        self.assertTrue(receipt['explicit_cleanup_reaped_child'])

    def test_regular_child_is_terminated_by_group_cancel_and_reaped(self):
        receipt = run_negative_control(breakaway=False)
        self.assertTrue(receipt['observed'], receipt)
        self.assertTrue(receipt['child_group_matches_supervisor'])
        self.assertFalse(receipt['child_survived_group_kill'])
        self.assertFalse(receipt['boundary_gap_observed'])
        self.assertTrue(receipt['explicit_cleanup_reaped_child'])


if __name__ == '__main__':
    unittest.main()
