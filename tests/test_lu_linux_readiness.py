"""Lu host readiness cannot become a simulated integration pass."""
import os
from pathlib import Path
import socket
import tempfile
import unittest
from cognitum.lu_linux_readiness import inspect, main

class LuReadiness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.sock = self.root / 'host.sock'

    def test_missing_source_and_socket_block(self):
        r = inspect(self.root, self.sock)
        self.assertEqual(r['status'], 'BLOCKED_SOURCE_OR_SOCKET')
        self.assertFalse(r['authenticated_lu_roundtrip_observed'])
        self.assertFalse(r['production_authorized'])

    def test_unregistered_feature_blocks(self):
        cargo = self.root/'src-tauri'/'Cargo.toml';cargo.parent.mkdir(parents=True)
        cargo.write_text('[features]\ndefault = []\n')
        result=inspect(self.root,self.sock)
        self.assertIn('LU_FEATURE_NOT_REGISTERED',result['missing'])

    def test_even_plausible_sources_and_socket_are_unverified(self):
        cargo = self.root/'src-tauri'/'Cargo.toml';cargo.parent.mkdir(parents=True)
        cargo.write_text('[features]\nlu-native-test-host = []\n')
        module = self.root/'src-tauri'/'src'/'core'/'lu_native_test_host.rs'
        module.parent.mkdir(parents=True)
        module.write_text('// experimental placeholder\n')
        s=socket.socket(socket.AF_UNIX)
        try:
            s.bind(str(self.sock));os.chmod(self.sock,0o600)
            result=inspect(self.root,self.sock)
            self.assertEqual(result['status'],'SOURCE_SOCKET_PRESENT_UNVERIFIED')
            self.assertFalse(result['cognitum_worker_dispatched_by_lu'])
            self.assertFalse(result['authenticated_lu_roundtrip_observed'])
        finally:s.close()

    def test_unsafe_socket_mode_denied(self):
        s=socket.socket(socket.AF_UNIX)
        try:
            s.bind(str(self.sock));os.chmod(self.sock,0o666)
            r=inspect(self.root,self.sock)
            self.assertIn('LU_SOCKET_UNTRUSTED',r['missing'])
        finally:s.close()

    def test_cli_has_no_success_exit_without_real_roundtrip(self):
        self.assertEqual(main(['--source-root',str(self.root),'--socket',str(self.sock)]),2)

if __name__=='__main__':unittest.main()
