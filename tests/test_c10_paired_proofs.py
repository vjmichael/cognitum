"""Regression safety controls for the reviewed paired proof configuration."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import subprocess
import unittest
from hashlib import sha1
from cognitum.formal_proofs import (_proof_body,_producer_args,_checker_args,
    certify_unsat,_reviewed_rules)
from tests.test_c10_proofs import contradiction

class PairedProofTests(unittest.TestCase):
    def test_only_outer_envelope_removed(self):
        self.assertEqual(_proof_body(b"unsat\n(\n(step t0 (cl) :rule hole)\n)\n",True),
                         b"(step t0 (cl) :rule hole)\n")
        self.assertIsNone(_proof_body(b"unknown\n",True))
        self.assertEqual(_proof_body(b"unsat\n(step t0 (cl))",False),b"(step t0 (cl))")
    def test_no_rule_waivers_and_digest_bound_rules(self):
        self.assertNotIn("--ignore-unknown-rules",_checker_args("checker","proof","source","rules"))
        self.assertNotIn("--allowed-rules",_checker_args("checker","proof","source","rules"))
        with TemporaryDirectory() as t:
            p=Path(t)
            for n in ("producer","checker","rules"): (p/n).write_bytes(b"test")
            with self.assertRaises(ValueError):_reviewed_rules(str(p/"rules"))
            with patch("cognitum.formal_proofs.subprocess.run") as run:
                result=certify_unsat(contradiction(),cvc5_binary=str(p/"producer"),
                    carcara_binary=str(p/"checker"),rare_file=str(p/"rules"))
                self.assertEqual(result.status,"UNVERIFIED")
                run.assert_not_called()
            blob=sha1(b"blob 4\0test").hexdigest()
            with patch("cognitum.formal_proofs.RARE_RULES_BLOB",blob):
                with patch("cognitum.formal_proofs.subprocess.run",side_effect=[
                    subprocess.CompletedProcess([],0,b"unsat\n(\n(step proof)\n)\n",b""),
                    subprocess.CompletedProcess([],0,b"holey\n",b"")]) as run:
                    result=certify_unsat(contradiction(),cvc5_binary=str(p/"producer"),
                        carcara_binary=str(p/"checker"),rare_file=str(p/"rules"))
                    self.assertEqual(result.status,"UNVERIFIED")
                    self.assertFalse(result.proof_sha256)
                    self.assertIn("--rare-file",run.call_args.args[0])
                    self.assertNotIn("--proof-granularity=theory-rewrite",run.call_args_list[0].args[0])
