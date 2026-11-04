"""C10 optional external Alethe certificate tests.

Simulated tool output exercises fail-closed integration only. It is NOT
evidence that a real cvc5 proof passed real Carcara. Native acceptance remains
a separate installed-binaries smoke gate.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import subprocess
import unittest

from cognitum.formal_smt import IntVar, LinearAtom, SMTProblem
from cognitum.formal_proofs import smtlib_for_problem, certify_unsat


def contradiction():
    return SMTProblem((IntVar("true",-2,3),),
                      (LinearAtom((("true",-1),),"ge",2),
                       LinearAtom((("true",1),),"ge",2)))


class C10ProofTests(unittest.TestCase):
    def test_smtlib_safe_grammar_and_negative_literals(self):
        source=smtlib_for_problem(contradiction()).decode("ascii")
        self.assertIn("(declare-const c10_true Int)",source)
        self.assertIn("(assert (>= c10_true (- 2)))",source)
        self.assertIn("(* (- 1) c10_true)",source)
        self.assertIn("(set-logic QF_LIA)",source)
        self.assertNotIn(" -2",source)
        self.assertNotIn(" -1",source)

    def test_missing_checker_does_not_certify(self):
        result=certify_unsat(contradiction(),
                            cvc5_binary="/unavailable/cvc5",
                            carcara_binary="/unavailable/carcara")
        self.assertEqual(result.status,"UNSUPPORTED")
        self.assertFalse(result.proof_sha256)

    def test_invalid_or_holey_checker_never_certifies(self):
        with TemporaryDirectory() as tmp:
            producer=Path(tmp)/"cvc5"
            checker=Path(tmp)/"carcara"
            producer.write_text("stub")
            checker.write_text("stub")
            for message,code in ((b"holey\n",0),(b"invalid\n",1),
                                 (b"valid with holes\n",0),(b"valid\n",1)):
                with self.subTest(message=message,code=code):
                    with patch("cognitum.formal_proofs.subprocess.run",
                        side_effect=[subprocess.CompletedProcess([],0,b"unsat\n(step proof)",b""),
                                     subprocess.CompletedProcess([],code,message,b"")]):
                        verdict=certify_unsat(contradiction(),
                                               cvc5_binary=str(producer),
                                               carcara_binary=str(checker))
                        self.assertNotEqual(verdict.status,"CERTIFIED_UNSAT")
            with patch("cognitum.formal_proofs.subprocess.run",
                return_value=subprocess.CompletedProcess([],0,b"sat\n",b"")):
                verdict=certify_unsat(contradiction(),
                                       cvc5_binary=str(producer),
                                       carcara_binary=str(checker))
                self.assertEqual(verdict.status,"NOT_UNSAT")

    def test_simulated_valid_result_only_tests_adapter_condition(self):
        # This is a mock acceptance-contract test, NOT genuine proof checking.
        with TemporaryDirectory() as tmp:
            producer=Path(tmp)/"cvc5"
            checker=Path(tmp)/"carcara"
            producer.write_text("stub")
            checker.write_text("stub")
            with patch("cognitum.formal_proofs.subprocess.run",
                side_effect=[subprocess.CompletedProcess([],0,b"unsat\n(step proof)",b""),
                             subprocess.CompletedProcess([],0,b"valid\n",b"")]) as run:
                verdict=certify_unsat(contradiction(),
                                       cvc5_binary=str(producer),
                                       carcara_binary=str(checker))
                self.assertEqual(verdict.status,"CERTIFIED_UNSAT")
                self.assertTrue(verdict.problem_sha256)
                self.assertTrue(verdict.proof_sha256)
                self.assertEqual(run.call_count,2)
                commands=[call.args[0] for call in run.call_args_list]
                self.assertEqual(commands[0][0],str(producer))
                self.assertEqual(commands[1][0],str(checker))
                self.assertEqual(commands[1][1],"check")

    def test_timeouts_and_misconfigured_executables_fail_closed(self):
        with TemporaryDirectory() as tmp:
            producer=Path(tmp)/"cvc5"
            checker=Path(tmp)/"carcara"
            producer.write_text("stub")
            checker.write_text("stub")
            with patch("cognitum.formal_proofs.subprocess.run",
                side_effect=subprocess.TimeoutExpired(["cvc5"],1)):
                self.assertEqual(certify_unsat(contradiction(),
                    cvc5_binary=str(producer),carcara_binary=str(checker)).status,"UNVERIFIED")
        with self.assertRaises(ValueError):
            certify_unsat(contradiction(),cvc5_binary="cvc5",
                          carcara_binary="carcara",timeout_seconds=0)
