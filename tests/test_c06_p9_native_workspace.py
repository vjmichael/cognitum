"""P9 tests are control-plane tests, NOT native Rust compile evidence."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("p9_local_workspace", ROOT / "integrations/lu/p9/native_test_workspace.py")
p9 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p9)


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args],
                                   text=True, stderr=subprocess.DEVNULL).strip()


class NativeWorkspaceTests(unittest.TestCase):
    def setUp(self):
        work = tempfile.TemporaryDirectory()
        self.addCleanup(work.cleanup)
        self.base = Path(work.name)
        self.source = self.base / "original-user-checkout"
        crate = self.source / "src-tauri/lu-core"
        (crate / "src").mkdir(parents=True)
        (crate / "src/lib.rs").write_text("pub mod ansf;\npub mod ownership_store;\n")
        (crate / "build.rs").write_text("fn main() {\n  prost_build::Config::new()\n"
            '    .compile_protos(&["proto/lu/v1/core.proto"], &["proto"])\n    .unwrap();\n}\n')
        (crate / "Cargo.toml").write_text('[package]\nname="lu-core"\n'
            '[dependencies]\nrusqlite="0.32"\nsha2="0.10"\nprost="0.14"\n'
            '[build-dependencies]\nprost-build="0.14"\n')
        git(self.source, "init")
        git(self.source, "add", ".")
        subprocess.check_call(["git", "-C", str(self.source), "-c", "user.name=P9",
                               "-c", "user.email=test@example.invalid", "commit", "-m", "fake-fixture"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.pin = git(self.source, "rev-parse", "HEAD")
        for module, key in ((p9, "PIN"), (p9.ng, "PIN"), (p9.installer, "PINNED_LU_COMMIT")):
            mock = patch.object(module, key, self.pin)
            mock.start()
            self.addCleanup(mock.stop)
        self.report = self.base / "native-gate-report.json"

    def test_disposable_sparse_checkout_preflight(self):
        before = git(self.source, "status", "--porcelain")
        r = p9.test_local_checkout(self.source, self.report, mode="preflight")
        self.assertEqual(r["native_gate"], "PREFLIGHT_ONLY", r.get("error"))
        self.assertTrue(r["source"]["five_overlay_files_verified"])
        self.assertTrue(r["disposable_checkout_removed"])
        self.assertFalse(r["rust_compiled"])
        self.assertEqual(git(self.source, "status", "--porcelain"), before)
        self.assertFalse((self.source / "src-tauri/lu-core/src/ansf_memory_gate.rs").exists())
        self.assertEqual(json.loads(self.report.read_text())["pinned_lu_commit"], self.pin)

    def test_dirty_original_checkout_is_not_modified_or_treated_as_overlay(self):
        (self.source / "user_private_change.txt").write_text("preserve exactly")
        previous = git(self.source, "status", "--porcelain")
        r = p9.test_local_checkout(self.source, self.report, mode="preflight")
        self.assertEqual(r["native_gate"], "PREFLIGHT_ONLY", r.get("error"))
        self.assertEqual(git(self.source, "status", "--porcelain"), previous)
        self.assertEqual((self.source / "user_private_change.txt").read_text(), "preserve exactly")

    def test_no_cargo_yields_evidence_of_blocked_native_gate(self):
        with patch.object(p9.ng.shutil, "which", return_value=None):
            r = p9.test_local_checkout(self.source, self.report, mode="all")
        self.assertEqual(r["native_gate"], "BLOCKED")
        self.assertFalse(r["rust_compiled"])
        self.assertIn("cargo", r["error"])
        self.assertTrue(r["disposable_checkout_removed"])
        self.assertEqual(json.loads(self.report.read_text())["native_gate"], "BLOCKED")

    def test_wrong_pin_fails_before_a_checkout_or_report_is_written(self):
        with patch.object(p9, "PIN", "0" * 40):
            with self.assertRaises(p9.WorkspaceBlocked):
                p9.test_local_checkout(self.source, self.report)
        self.assertFalse(self.report.exists())

    def test_report_may_not_be_inside_original_lu_checkout(self):
        with self.assertRaises(p9.WorkspaceBlocked):
            p9.test_local_checkout(self.source, self.source / "report.json")
        self.assertFalse((self.source / "report.json").exists())

    def test_offline_default_is_reset_after_gate(self):
        with patch.dict(os.environ, {"CARGO_NET_OFFLINE": "before"}):
            with patch.object(p9.ng.shutil, "which", return_value=None):
                r = p9.test_local_checkout(self.source, self.report)
            self.assertEqual(os.environ["CARGO_NET_OFFLINE"], "before")
        self.assertEqual(r["dependency_policy"], "offline only")

    def test_explicit_dependency_download_flag_is_not_assumed_approved(self):
        with patch.dict(os.environ, {"CARGO_NET_OFFLINE": "true"}):
            with patch.object(p9.ng.shutil, "which", return_value=None):
                r = p9.test_local_checkout(self.source, self.report, allow_cargo_network=True)
            self.assertEqual(os.environ["CARGO_NET_OFFLINE"], "true")
        self.assertEqual(r["dependency_policy"], "cargo network permitted")
        self.assertEqual(r["native_gate"], "BLOCKED")

    def test_overlay_preflight_failure_preserves_original_checkout(self):
        before = git(self.source, "status", "--porcelain")
        with patch.object(p9.installer, "prepare", side_effect=ValueError("audited Lu anchor missing")):
            result = p9.test_local_checkout(self.source, self.report, mode="all")
        self.assertEqual(result["native_gate"], "BLOCKED")
        self.assertFalse(result["rust_compiled"])
        self.assertTrue(result["disposable_checkout_removed"])
        self.assertIn("audited Lu anchor", result["error"])
        self.assertEqual(before, git(self.source, "status", "--porcelain"))

    def test_symlinked_report_into_source_is_rejected(self):
        destination = self.source / "report.json"
        link = self.base / "alias.json"
        try:
            link.symlink_to(destination)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable in test environment")
        with self.assertRaises(p9.WorkspaceBlocked):
            p9.test_local_checkout(self.source, link)
        self.assertFalse(destination.exists())

    def test_bad_checkout_source_does_not_autocreate_repository(self):
        not_git = self.base / "ordinary-files"
        not_git.mkdir()
        with self.assertRaises(p9.WorkspaceBlocked):
            p9.test_local_checkout(not_git, self.report)
        self.assertFalse((not_git / ".git").exists())


if __name__ == "__main__":
    unittest.main()
