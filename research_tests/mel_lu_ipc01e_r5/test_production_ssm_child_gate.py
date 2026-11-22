"""Source-stage production SSM entrypoint refusal tests.

These tests do NOT claim positive AppContainer launch/SCM authority; that
requires an installer-provisioned standard user, genuine kernel Job and
independently verified numerical output on the actual Windows system.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from cognitum.mel import ssm_r5_production_child as worker


class InstalledWorkerGate(unittest.TestCase):
    def test_no_insecure_nonwindows_fallback(self):
        if sys.platform != "win32":
            with self.assertRaisesRegex(
                worker.ProductionSSMRefused, "native Windows worker required"
            ):
                worker.require_genuine_appcontainer()

    def test_normal_process_cannot_read_or_create_original_frames(self):
        # The GitHub hosted Windows test process is not an AppContainer.
        # An actual provisioned AppContainer is deliberately tested separately.
        if sys.platform == "win32" and os.environ.get("GITHUB_ACTIONS") != "true":
            self.skipTest("Requires non-AppContainer hosted Windows runner")
        script = Path(worker.__file__).resolve()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bad_input = root / "input.frame"
            output = root / "output.frame"
            bad_input.write_bytes(b"unauthorized-data-must-not-be-parsed")
            child = subprocess.run(
                [sys.executable, "-I", "-B", str(script),
                 str(bad_input), str(output)],
                capture_output=True, timeout=15, check=False,
            )
            self.assertEqual(child.returncode, 4)
            self.assertFalse(output.exists())
            self.assertEqual(child.stdout, b"")
            self.assertEqual(child.stderr, b"")
            self.assertEqual(bad_input.read_bytes(),
                             b"unauthorized-data-must-not-be-parsed")

    def test_profile_name_is_not_overridable(self):
        self.assertEqual(worker.PROFILE, "CognitumSsmProductionV1")
        self.assertEqual(worker.main.__module__,
                         "cognitum.mel.ssm_r5_production_child")


if __name__ == "__main__":
    unittest.main()
