"""Strict patch preflight: exact blob identities, bounded contexts, no partial mutation."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest
from hashlib import sha1,sha256
from tools.c15_trackeval_pinned_compat import patch_pinned

class PinnedCompatibilityTests(unittest.TestCase):
    def test_reviewed_exact_transforms_and_preflight(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            fixture={"loader.py":(b"x=np.array([], np.int)\n",b"x=np.array([], np.int64)\n",0,1),
                     "metric.py":(b"x=np.zeros(1,dtype=np.float)\n",b"x=np.zeros(1,dtype=np.float64)\n",1,0)}
            spec={name:(sha1(b"blob "+str(len(old)).encode()+b"\0"+old).hexdigest(),nf,ni,
                        sha256(new).hexdigest()) for name,(old,new,nf,ni) in fixture.items()}
            for n,(old,*_) in fixture.items():(root/n).write_bytes(old)
            with patch("tools.c15_trackeval_pinned_compat.FILES",spec):
                (root/"metric.py").write_bytes(b"unreviewed")
                with self.assertRaises(ValueError):patch_pinned(root)
                self.assertEqual((root/"loader.py").read_bytes(),fixture["loader.py"][0])
                (root/"metric.py").write_bytes(fixture["metric.py"][0])
                audit=patch_pinned(root)
                self.assertEqual(audit["replacements"],2)
                self.assertFalse(audit["metric_algorithms_modified"])
                for n,(_,new,*_) in fixture.items():self.assertEqual((root/n).read_bytes(),new)
                with self.assertRaises(ValueError):patch_pinned(root)
