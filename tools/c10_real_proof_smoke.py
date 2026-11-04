"""Real native C10 proof acceptance, not mocks.

Set C10_CVC5_BINARY and C10_CARCARA_BINARY to trusted, absolute,
pre-installed executable paths. Run only in OS-isolated CI/dev environment.
Exit nonzero if cvc5+Carcara do not genuinely certify UNSAT.
"""
import os
import sys
import subprocess
from tempfile import TemporaryDirectory
from pathlib import Path

from cognitum.formal_smt import IntVar, LinearAtom, SMTProblem
from cognitum.formal_proofs import certify_unsat


def main():
    cvc5=os.environ.get("C10_CVC5_BINARY","")
    carcara=os.environ.get("C10_CARCARA_BINARY","")
    if not all(Path(x).is_absolute() and Path(x).is_file()
               for x in (cvc5,carcara)):
        raise SystemExit("C10 native proof binaries MUST be provided explicitly")
    variable=(IntVar("x",-5,5),)
    unsat=SMTProblem(variable,(LinearAtom((("x",1),),"eq",1),
                               LinearAtom((("x",1),),"eq",2)))
    sat=SMTProblem(variable,(LinearAtom((("x",1),),"eq",1),))
    certificate=certify_unsat(unsat,cvc5_binary=cvc5,carcara_binary=carcara)
    if certificate.status != "CERTIFIED_UNSAT":
        # Strict CI-only diagnostic: no fallback acceptance, no shell, tiny fixed
        # synthetic SMT input and bounded output. Never run this on user secrets.
        from cognitum.formal_proofs import smtlib_for_problem
        with TemporaryDirectory(prefix="c10-diagnostic-") as folder:
            problem_file=Path(folder)/"problem.smt2"
            proof_file=Path(folder)/"proof.alethe"
            problem_file.write_bytes(smtlib_for_problem(unsat))
            produced=subprocess.run(
                [cvc5, "--dump-proofs", "--proof-format-mode=alethe", str(problem_file)],
                cwd=folder, input=b"", stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=15, check=False,
            )
            print("C10 producer exit:", produced.returncode,
                  "stdout-prefix:", repr(produced.stdout[:200]),
                  "stderr-prefix:", repr(produced.stderr[:600]), flush=True)
            if produced.returncode == 0 and produced.stdout.startswith(b"unsat\n"):
                proof_file.write_bytes(produced.stdout.split(b"\n",1)[1])
                checked=subprocess.run(
                    [carcara, "check", str(proof_file), str(problem_file)],
                    cwd=folder, input=b"", stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=15, check=False,
                )
                print("C10 checker exit:", checked.returncode,
                      "stdout-prefix:", repr(checked.stdout[:300]),
                      "stderr-prefix:", repr(checked.stderr[:1000]), flush=True)
    if (certificate.status!="CERTIFIED_UNSAT"
            or not certificate.problem_sha256 or not certificate.proof_sha256):
        raise SystemExit("C10 independent native UNSAT proof acceptance FAILED: "
                         +certificate.status+" / "+certificate.limitation)
    control=certify_unsat(sat,cvc5_binary=cvc5,carcara_binary=carcara)
    if control.status=="CERTIFIED_UNSAT":
        raise SystemExit("C10 native checker incorrectly certified SAT control")
    print("C10 native Alethe proof accepted by independent Carcara checker")
    print("SAT negative control did not certify")
    return 0


if __name__=="__main__":
    sys.exit(main())
