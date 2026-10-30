"""C06 P2 source checkpoint integrity and safe-whitelist coverage."""
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from tools.build_library_checkpoint import approved, pack, verify
from pathlib import PurePosixPath


class CheckpointTest(unittest.TestCase):
    def test_source_only_allowlist_blocks_secret_and_runtime_dirs(self):
        for path in (".env", "cognitum/.env", "cognitum/.env.local", "docs/secrets/key.txt",
                     "cognitum/__pycache__/memory.pyc", "tests/data.sqlite", "tools/private.key",
                     "bad/unknown.py", "README.md/other", "cognitum/output.zip"):
            self.assertFalse(approved(PurePosixPath(path)), path)
        self.assertTrue(approved(PurePosixPath("cognitum/memory_host_gate.py")))
        self.assertTrue(approved(PurePosixPath("proto/cognitum/memory/v1/evidence.proto")))

    def test_round_trip_and_mismatched_hash_or_member_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "source"
            (root / "cognitum").mkdir(parents=True)
            (root / "cognitum" / "safe.py").write_text("print(1)\n")
            (root / ".env").write_text("SECRET")
            target = Path(d) / "checkpoint.zip"
            meta = pack(root, target, base_snapshot="test-baseline",
                        validation={"unit_tests": 1})
            self.assertEqual(meta["source_file_count"], 1)
            self.assertEqual(verify(target)["source_file_count"], 1)
            with zipfile.ZipFile(target) as z:
                m = z.read("CHECKPOINT_INFO.json")
            bad = Path(d) / "bad.zip"
            with zipfile.ZipFile(bad, "w") as z:
                z.writestr("cognitum/safe.py", "changed source")
                z.writestr("CHECKPOINT_INFO.json", m)
            with self.assertRaisesRegex(ValueError, "integrity"):
                verify(bad)

    def test_traversal_entry_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "evil.zip"
            with zipfile.ZipFile(target, "w") as z:
                z.writestr("../steal.py", "evil")
                z.writestr("CHECKPOINT_INFO.json", json.dumps({"source_file_count": 0,
                                                                "source_sha256": {}}))
            with self.assertRaisesRegex(ValueError, "unsafe"):
                verify(target)


if __name__ == "__main__":
    unittest.main()
