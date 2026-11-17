"""Strict patch preflight: exact blob and SHA-256, byte spans, no partial mutation."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import re
import unittest
from hashlib import sha1,sha256
from tools.c15_trackeval_pinned_compat import patch_pinned

class PinnedCompatibilityTests(unittest.TestCase):
    def test_reviewed_exact_transforms_and_preflight(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            fixture={"loader.py":(b"x=np.array([], np.int)\n",b"x=np.array([], np.int64)\n"),
                     "metric.py":(b"x=np.zeros(1,dtype=np.float)\n",b"x=np.zeros(1,dtype=np.float64)\n")}
            spec={name:(sha1(b"blob "+str(len(old)).encode()+b"\0"+old).hexdigest(),
                        sha256(old).hexdigest(),tuple((m.start(),m[1]) for m in re.finditer(rb"np\.(float|int)\b",old)))
                  for name,(old,new) in fixture.items()}
            for n,(old,_) in fixture.items():(root/n).write_bytes(old)
            with patch("tools.c15_trackeval_pinned_compat.FILES",spec):
                (root/"metric.py").write_bytes(b"unreviewed")
                with self.assertRaises(ValueError):patch_pinned(root)
                self.assertEqual((root/"loader.py").read_bytes(),fixture["loader.py"][0])
                (root/"metric.py").write_bytes(fixture["metric.py"][0])
                audit=patch_pinned(root)
                self.assertEqual(audit["replacements"],2)
                self.assertFalse(audit["metric_algorithms_modified"])
                for n,(_,new) in fixture.items():self.assertEqual((root/n).read_bytes(),new)
                with self.assertRaises(ValueError):patch_pinned(root)

    def test_source_hash_correct_but_wrong_or_omitted_spans_rejected(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);file=root/"loader.py"
            old=b"x=np.array([], np.int)\ny=np.float\n"
            spec=(sha1(b"blob "+str(len(old)).encode()+b"\0"+old).hexdigest(),sha256(old).hexdigest())
            file.write_bytes(old)
            for spans in (((0,b"int"),),((old.index(b"np.int"),b"int"),)):
                with patch("tools.c15_trackeval_pinned_compat.FILES",{"loader.py":(*spec,spans)}):
                    with self.assertRaises(ValueError):patch_pinned(root)
                    self.assertEqual(file.read_bytes(),old)
