"""P8 native-gate orchestrator regression; fake Cargo is NEVER a Rust pass."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import json

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'integrations/lu/p8/native_gate.py'
spec = importlib.util.spec_from_file_location('p8_native_gate', TARGET)
ng = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ng)
installer_path = ROOT / 'integrations/lu/apply_overlay.py'
spec2 = importlib.util.spec_from_file_location('lu_overlay', installer_path)
installer = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(installer)


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True,
                                   stderr=subprocess.DEVNULL).strip()


class NativeTestGate(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name) / 'isolated-lu'
        crate = self.root / ng.CORE
        (crate / 'src').mkdir(parents=True)
        (crate / 'src/lib.rs').write_text('pub mod ansf;\npub mod ownership_store;\n')
        (crate / 'build.rs').write_text('fn main() {\n  prost_build::Config::new()\n'
            '    .compile_protos(&["proto/lu/v1/core.proto"], &["proto"])\n    .unwrap();\n}\n')
        (crate / 'Cargo.toml').write_text('[package]\nname = "lu-core"\n'
            '[dependencies]\nrusqlite="0.32"\nsha2="0.10"\nprost="0.14"\n'
            '[build-dependencies]\nprost-build="0.14"\n')
        git(self.root, 'init')
        git(self.root, 'add', '.')
        subprocess.check_call(['git', '-C', str(self.root), '-c', 'user.name=P8',
            '-c', 'user.email=p8@example.invalid', 'commit', '-m', 'fixture'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.pin = git(self.root, 'rev-parse', 'HEAD')
        patcher = patch.object(ng, 'PIN', self.pin)
        patcher.start()
        self.addCleanup(patcher.stop)
        with patch.object(installer, 'PINNED_LU_COMMIT', self.pin):
            changes = installer.prepare(self.root, installer_path.parent)
        for path, contents in changes.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents)

    def test_clean_pinned_overlay_preflight(self):
        r = ng.native_gate(self.root, mode='preflight')
        self.assertEqual(r['native_gate'], 'PREFLIGHT_ONLY')
        self.assertTrue(r['source']['five_overlay_files_verified'])
        self.assertFalse(r['rust_compiled'])
        self.assertEqual(len(r['source']['overlay_sha256']), 5)

    def test_gate_rejects_wrong_commit(self):
        with patch.object(ng, 'PIN', '0' * 40):
            r = ng.native_gate(self.root, mode='preflight')
        self.assertEqual(r['native_gate'], 'BLOCKED')
        self.assertIn('HEAD', r['error'])

    def test_gate_rejects_an_unrelated_lu_change(self):
        (self.root / 'UNRELATED.txt').write_text('do not overwrite')
        r = ng.native_gate(self.root, mode='preflight')
        self.assertEqual(r['native_gate'], 'BLOCKED')
        self.assertIn('five exact', r['error'])
        self.assertEqual((self.root / 'UNRELATED.txt').read_text(), 'do not overwrite')

    def test_gate_rejects_dirty_native_overlay(self):
        file = self.root / ng.CORE / 'src/ansf_memory_gate.rs'
        file.write_bytes(file.read_bytes() + b'\n// drifter\n')
        r = ng.native_gate(self.root, mode='preflight')
        self.assertEqual(r['native_gate'], 'BLOCKED')
        self.assertIn('source drift', r['error'])

    def test_gate_rejects_unexpected_lib_modification(self):
        file = self.root / ng.CORE / 'src/lib.rs'
        file.write_text(file.read_text() + 'pub mod webview_auth_bypass;\n')
        r = ng.native_gate(self.root, mode='preflight')
        self.assertEqual(r['native_gate'], 'BLOCKED')
        self.assertIn('lib.rs', r['error'])

    def test_gate_never_uses_fake_cargo_when_missing(self):
        with patch.object(ng.shutil, 'which', return_value=None):
            r = ng.native_gate(self.root, mode='all')
        self.assertEqual(r['native_gate'], 'BLOCKED')
        self.assertFalse(r['rust_compiled'])
        self.assertFalse(r['checks'])
        self.assertIn('cargo', r['error'])

    def test_simulated_success_only_asserts_runner_control_flow(self):
        seen = []
        original = ng.run_cmd
        def fake(args, *, cwd, timeout=60):
            if args[0] == 'cargo':
                seen.append(tuple(args))
                return subprocess.CompletedProcess(args, 0, 'test result: ok. 1 passed;\n', '')
            return original(args, cwd=cwd, timeout=timeout)
        with patch.object(ng.shutil, 'which', return_value='/mock/bin'), \
                patch.object(ng, 'run_cmd', side_effect=fake):
            r = ng.native_gate(self.root, mode='all')
        self.assertEqual(r['native_gate'], 'PASS')
        self.assertEqual(len(seen), 3)
        # This result came from mocks; the real environment remains uncompiled.

    def test_zero_matching_native_tests_is_blocked(self):
        original = ng.run_cmd
        def fake(args, *, cwd, timeout=60):
            if args[0] == 'cargo':
                return subprocess.CompletedProcess(args, 0, 'test result: ok. 0 passed; 0 failed;\n', '')
            return original(args, cwd=cwd, timeout=timeout)
        with patch.object(ng.shutil, 'which', return_value='/mock/bin'), \
                patch.object(ng, 'run_cmd', side_effect=fake):
            r = ng.native_gate(self.root, mode='all')
        self.assertEqual(r['native_gate'], 'BLOCKED')
        self.assertFalse(r['rust_compiled'])
        self.assertIn('zero matching', r['error'])

    def test_scoped_failure_never_claims_rust_pass(self):
        original = ng.run_cmd
        def fake(args, *, cwd, timeout=60):
            if args[0] == 'cargo':
                return subprocess.CompletedProcess(args, 101, '', 'error: could not compile')
            return original(args, cwd=cwd, timeout=timeout)
        with patch.object(ng.shutil, 'which', return_value='/mock/bin'), \
                patch.object(ng, 'run_cmd', side_effect=fake):
            r = ng.native_gate(self.root, mode='scoped')
        self.assertEqual(r['native_gate'], 'BLOCKED')
        self.assertFalse(r['rust_compiled'])
        self.assertEqual(r['checks'][0]['returncode'], 101)

    def test_external_machine_report_records_blockage_without_credentials(self):
        report = self.root.parent / 'p8.json'
        with patch.object(ng.shutil, 'which', return_value=None):
            r = ng.native_gate(self.root, mode='all', report_path=report)
        saved = json.loads(report.read_text())
        self.assertEqual(saved['native_gate'], 'BLOCKED')
        self.assertEqual(saved['pinned_lu_commit'], self.pin)
        self.assertFalse(saved['host_authentication_tested'])

    def test_report_cannot_write_into_lu_checkout(self):
        with self.assertRaises(ng.GateBlocked):
            ng.native_gate(self.root, mode='preflight', report_path=self.root / 'report.json')
        self.assertFalse((self.root / 'report.json').exists())


if __name__ == '__main__':
    unittest.main()
