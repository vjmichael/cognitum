"""Synthetic harness test only; not an official MOT17 result."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.c15_trackeval_numpy_compat import patch, TARGET


class C15TrackEvalNumPyCompatibility(unittest.TestCase):
    def test_exact_legacy_type_alias_only_and_fail_on_repeat(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            path=root/TARGET
            path.parent.mkdir(parents=True)
            path.write_bytes(b"x=np.asarray([1], dtype=np.float)\ny=np.asarray([1], dtype=np.int)\nz=np.float64(2)\n")
            record=patch(root)
            self.assertEqual(record["replacements"],2)
            self.assertIn(b"dtype=np.float64",path.read_bytes())
            self.assertIn(b"dtype=np.int64",path.read_bytes())
            self.assertIn(b"np.float64(2)",path.read_bytes())
            with self.assertRaises(ValueError):
                patch(root)

    def test_modern_pinned_loader_is_accepted_without_mutation(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            path=root/TARGET
            path.parent.mkdir(parents=True)
            source=(b"class MotChallenge2DBox:\\n"
                    b"    def load(self):\\n"
                    b"        return np.asarray([1], dtype=np.float64)\\n")
            path.write_bytes(source)
            record=patch(root)
            self.assertEqual(record["replacements"],0)
            self.assertEqual(path.read_bytes(),source)
            self.assertFalse(record["metric_logic_modified"])

    def test_reject_unexpected_checkout_variant(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            path=root/TARGET
            path.parent.mkdir(parents=True)
            path.write_text("x = np.float(3)\n")
            with self.assertRaises(ValueError):
                patch(root)


if __name__=="__main__":
    unittest.main()
