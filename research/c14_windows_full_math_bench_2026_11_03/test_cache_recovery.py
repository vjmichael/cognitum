"""Regression for the CH23 audit.json Windows restart failure.

Run from the benchmark kit: python -m unittest test_cache_recovery.py -v
No original archive source or user benchmark result is modified.
"""
import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name('C14_MATH_BENCH.py')
spec = importlib.util.spec_from_file_location('c14_math_bench_under_test', MODULE_PATH)
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


class SealedScratchRecovery(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='c14_recovery_test_')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'scratch'
        self.archive = MODULE_PATH.with_name(bench.ARCHIVE)
        self.assertEqual(bench.digest(self.archive), bench.PIN)
        self.assertEqual(len(bench.extract_exact(self.archive, self.root)), 1100)

    def test_modified_generated_audit_is_restored(self):
        f = self.root / 'CH_C14_23' / 'audit.json'
        original_hash = bench.digest(f)
        f.write_text('modified report from previous test\n', encoding='utf8')
        changed = bench.extract_exact(self.archive, self.root)
        self.assertEqual(changed, ['CH_C14_23/audit.json'])
        self.assertEqual(bench.digest(f), original_hash)
        self.assertEqual(bench.extract_exact(self.archive, self.root), [])

    def test_deleted_mathematical_source_is_restored(self):
        f = self.root / 'CH_C14_24' / 'mpfr_interval.py'
        original_hash = bench.digest(f)
        f.unlink()
        self.assertEqual(bench.extract_exact(self.archive, self.root), ['CH_C14_24/mpfr_interval.py'])
        self.assertEqual(bench.digest(f), original_hash)

    def test_wrong_cache_provenance_fails_closed(self):
        original = self.root / 'CH_C14_23' / 'audit.json'
        original_hash = bench.digest(original)
        (self.root / '.BENCH_ORIGINAL_SHA256').write_text('untrusted', encoding='utf8')
        with self.assertRaisesRegex(ValueError, 'provenance'):
            bench.extract_exact(self.archive, self.root)
        self.assertEqual(bench.digest(original), original_hash)

    def test_results_are_not_inside_scratch_and_original_zip_is_unchanged(self):
        f = self.root / 'CH_C14_23' / 'audit.json'
        f.write_bytes(b'corrupted')
        self.assertTrue(bench.extract_exact(self.archive, self.root))
        self.assertEqual(bench.digest(self.archive), bench.PIN)


if __name__ == '__main__':
    unittest.main()
