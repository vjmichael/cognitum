"""Portable contract checks only. Real P13 gate requires Windows execution."""
import unittest
from unittest.mock import patch
from pathlib import Path
import tempfile
from tools.run_c15_t4_p13_windows_gate import (
    PINNED, GATE_NAMES, platform_eligible, execute, runtime_preflight,
)

class P13RunnerTests(unittest.TestCase):
    def test_windows_only_architecture(self):
        self.assertTrue(platform_eligible('Windows','AMD64'))
        self.assertTrue(platform_eligible('Windows','x86_64'))
        for system,machine in [('Linux','x86_64'),('Darwin','arm64'),('Windows','x86'),('Windows','arm64')]:
            self.assertFalse(platform_eligible(system,machine))

    def test_linux_cannot_certify_windows(self):
        with patch('tools.run_c15_t4_p13_windows_gate.runtime_preflight',return_value={
            'windows_x86_64_eligible':False}):
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaisesRegex(RuntimeError,'P13_WINDOWS_ONLY'):
                    execute(output_directory=Path(d)/'result')

    def test_dependency_pins_and_modules_declared(self):
        self.assertTrue({'pytest','cryptography','protobuf','asn1crypto'} <= set(PINNED))
        self.assertTrue(any('p11_p12' in name for name in GATE_NAMES))
        self.assertTrue(all(name.startswith('tests/') for name in GATE_NAMES))

    def test_preflight_does_not_certify_os(self):
        p=runtime_preflight()
        self.assertEqual(p['windows_x86_64_eligible'],
                         platform_eligible(p['platform'], p['machine']))
        self.assertNotIn('windows_os_sandbox_verified', p)
        self.assertTrue(p['test_modules_present'])

if __name__=='__main__':unittest.main()
