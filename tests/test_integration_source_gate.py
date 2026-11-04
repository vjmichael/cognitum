"""Portable source-gate tests: never substitute file existence for acceptance."""
import tempfile
import unittest
from pathlib import Path

from tools.cognitum_integration_source_gate import REQUIRED, inspect, main


class IntegrationSourceGateTests(unittest.TestCase):
    def test_incomplete_tree_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            result=inspect(root)
            self.assertEqual(result["tracked_components"],19)
            self.assertEqual(result["missing"],sorted(REQUIRED))
            self.assertFalse(result["release_ready"])
            self.assertFalse(result["lu_installed_host_roundtrip_verified"])
            self.assertEqual(main(["--root",str(root),"--require-sources"]),2)

    def test_full_mock_tree_is_only_source_complete_not_release_ready(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for path in REQUIRED.values():
                file=root/path
                file.parent.mkdir(parents=True,exist_ok=True)
                file.write_text("# fake file, not actual functional proof\n")
            result=inspect(root)
            self.assertEqual(result["status"],"SOURCE_INVENTORY_COMPLETE_ONLY")
            self.assertEqual(result["missing"],[])
            self.assertFalse(result["release_ready"])
            self.assertFalse(result["lu_installed_host_roundtrip_verified"])
            self.assertEqual(main(["--root",str(root),"--require-sources"]),0)

    def test_symlink_cannot_satisfy_source_requirement(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            target=root/"standin.py"
            target.write_text("# source outside component path\n")
            link=root/REQUIRED["C01"]
            link.parent.mkdir(parents=True,exist_ok=True)
            try:
                link.symlink_to(target)
            except (OSError,NotImplementedError):
                self.skipTest("symlink creation unavailable")
            self.assertIn("C01", inspect(root)["missing"])


if __name__ == "__main__":
    unittest.main()
