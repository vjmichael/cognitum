"""Ensure Lu P7 overlay installer is opt-in, pinned, and collision-safe."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[1] / 'integrations' / 'lu' / 'apply_overlay.py'
spec = importlib.util.spec_from_file_location('c06_apply_overlay', SRC)
overlay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(overlay)


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.DEVNULL).decode().strip()


class LocalOverlayInstallTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        crate = self.root / 'src-tauri' / 'lu-core'
        (crate / 'src').mkdir(parents=True)
        (crate / 'src' / 'lib.rs').write_text('pub mod ansf;\npub mod ownership_store;\n')
        (crate / 'Cargo.toml').write_text(
            '[dependencies]\nrusqlite = "0.32"\nsha2 = "0.10"\nprost = "0.14"\n'
            '[build-dependencies]\nprost-build = "0.14"\n')
        (crate / 'build.rs').write_text(
            'fn main() { prost_build::Config::new()\n'
            '  .compile_protos(&["proto/lu/v1/core.proto"], &["proto"])\n'
            '  .expect("compile"); }\n')
        git(self.root, 'init')
        git(self.root, 'add', '.')
        subprocess.check_output(['git', '-C', str(self.root), '-c', 'user.name=Test',
                                 '-c', 'user.email=test@example.com', 'commit', '-m', 'local test'],
                                stderr=subprocess.DEVNULL)
        self.sha = git(self.root, 'rev-parse', 'HEAD')

    def _run(self, *args):
        with patch.object(overlay, 'PINNED_LU_COMMIT', self.sha), \
                patch.object(sys, 'argv', ['apply_overlay.py', '--lu-root', str(self.root), *args]):
            return overlay.main()

    def test_default_dry_run_never_modifies_checkout(self):
        self.assertEqual(self._run(), 0)
        self.assertEqual(git(self.root, 'status', '--porcelain'), '')
        self.assertFalse((self.root / 'src-tauri/lu-core/src/ansf_memory_gate.rs').exists())

    def test_explicit_apply_adds_only_five_approved_changes(self):
        self.assertEqual(self._run('--apply'), 0)
        crate = self.root / 'src-tauri/lu-core'
        lib = (crate / 'src/lib.rs').read_text()
        for module in overlay.MODULES:
            self.assertIn(f'pub mod {module};', lib)
        self.assertIn('proto/cognitum/memory/v1/evidence.proto', (crate / 'build.rs').read_text())
        names = git(self.root, 'status', '--porcelain')
        self.assertEqual(len(names.splitlines()), 5)
        self.assertTrue((crate / 'src/ansf_memory_gate.rs').exists())
        self.assertTrue((crate / 'src/ansf_memory_proto.rs').exists())
        self.assertEqual((crate / 'proto/cognitum/memory/v1/evidence.proto').read_bytes(),
                         (SRC.parent / 'src-tauri/lu-core/proto/cognitum/memory/v1/evidence.proto').read_bytes())

    def test_dirty_checkout_refused_without_modification(self):
        lib = self.root / 'src-tauri/lu-core/src/lib.rs'
        lib.write_text('custom work')
        with self.assertRaises(SystemExit): self._run('--apply')
        self.assertEqual(lib.read_text(), 'custom work')
        self.assertFalse((self.root / 'src-tauri/lu-core/src/ansf_memory_gate.rs').exists())

    def test_wrong_lu_commit_refused(self):
        with patch.object(overlay, 'PINNED_LU_COMMIT', '0' * 40), \
                patch.object(sys, 'argv', ['apply_overlay.py', '--lu-root', str(self.root), '--apply']):
            with self.assertRaises(SystemExit): overlay.main()
        self.assertEqual(git(self.root, 'status', '--porcelain'), '')

    def test_existing_destination_refused(self):
        target = self.root / 'src-tauri/lu-core/src/ansf_memory_proto.rs'
        target.write_text('concurrent change')
        # Stage this tracked collision on the test branch to simulate a clean but
        # incompatible newer Lu tree; do not overwrite a file already present.
        git(self.root, 'add', '.')
        subprocess.check_output(['git', '-C', str(self.root), '-c', 'user.name=Test',
                                 '-c', 'user.email=test@example.com', 'commit', '-m', 'collision'],
                                stderr=subprocess.DEVNULL)
        with patch.object(overlay, 'PINNED_LU_COMMIT', git(self.root, 'rev-parse', 'HEAD')), \
                patch.object(sys, 'argv', ['apply_overlay.py', '--lu-root', str(self.root), '--apply']):
            with self.assertRaises(SystemExit): overlay.main()
        self.assertEqual(target.read_text(), 'concurrent change')

    def test_changed_protobuf_build_anchor_refused(self):
        build = self.root / 'src-tauri/lu-core/build.rs'
        build.write_text('fn main() {}')
        git(self.root, 'add', '.')
        subprocess.check_output(['git', '-C', str(self.root), '-c', 'user.name=Test',
                                 '-c', 'user.email=test@example.com', 'commit', '-m', 'changed build'],
                                stderr=subprocess.DEVNULL)
        with patch.object(overlay, 'PINNED_LU_COMMIT', git(self.root, 'rev-parse', 'HEAD')), \
                patch.object(sys, 'argv', ['apply_overlay.py', '--lu-root', str(self.root), '--apply']):
            with self.assertRaises(SystemExit): overlay.main()
        self.assertEqual(build.read_text(), 'fn main() {}')

if __name__ == '__main__': unittest.main()
