"""Regression for the CH39 DLL lookup that blocked 112 Windows math tasks."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

SOURCE = Path(__file__).with_name('C14_MATH_BENCH.py')
spec = importlib.util.spec_from_file_location('c14math_bench_tested', SOURCE)
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)

class MpfrDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.kit = self.root/'Cognitum_C14_All_Past_Math_Benchmark_Windows_2026-11-03'
        self.kit.mkdir()
        self.old = self.root/'Cognitum_CH23_CH39_All_History_Windows_Regression_2026-11-03'
        self.old.mkdir()
        self.dll = self.old/'MPFR_Runtime'/'libmpfr-6.dll'
        self.dll.parent.mkdir()
        self.dll.write_bytes(b'test-placeholder, not a real DLL')
        self.patch = patch.object(bench, 'HERE', self.kit)
        self.patch.start(); self.addCleanup(self.patch.stop)

    def test_nearby_existing_regression_auto_detect(self):
        self.assertEqual(bench.mpfr_path(SimpleNamespace(mpfr_dll=None)), str(self.dll.resolve()))

    def test_nested_previous_kit_auto_detect(self):
        nested=self.old / self.old.name / 'MPFR_Runtime'
        nested.mkdir(parents=True)
        relocated=nested/'libmpfr-6.dll'
        relocated.write_bytes(b'test DLL')
        self.dll.unlink()
        self.assertEqual(bench.mpfr_path(SimpleNamespace(mpfr_dll=None)),str(relocated.resolve()))

    def test_case_duplicate_suffix(self):
        newer=self.root/(self.old.name+' (1)')/'MPFR_Runtime'
        newer.mkdir(parents=True)
        target=newer/'libmpfr-6.dll';target.write_bytes(b'test DLL')
        self.dll.unlink()
        self.assertEqual(bench.mpfr_path(SimpleNamespace(mpfr_dll=None)),str(target.resolve()))

    def test_explicit_dll_file(self):
        self.assertEqual(bench.mpfr_path(SimpleNamespace(mpfr_dll=str(self.dll))),str(self.dll.resolve()))

    def test_explicit_directory(self):
        self.assertEqual(bench.mpfr_path(SimpleNamespace(mpfr_dll=str(self.dll.parent))),str(self.dll.resolve()))

    def test_environment_override(self):
        with patch.dict(os.environ, {'C14_BENCH_MPFR_DLL':str(self.dll)}):
            self.assertEqual(bench.mpfr_path(SimpleNamespace(mpfr_dll=None)),str(self.dll.resolve()))

    def test_local_runtime_preferred(self):
        local=self.kit/'MPFR_Runtime'/'libmpfr-6.dll';local.parent.mkdir();local.write_bytes(b'test DLL')
        self.assertEqual(bench.mpfr_path(SimpleNamespace(mpfr_dll=None)),str(local.resolve()))

    def test_explicit_missing_refuses_without_fallback(self):
        with self.assertRaisesRegex(ValueError,'missing'):
            bench.mpfr_path(SimpleNamespace(mpfr_dll=str(self.root/'does-not-exist.dll')))

if __name__ == '__main__':unittest.main()
