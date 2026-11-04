"""Real native C10 proof acceptance, not mocks.

Set C10_CVC5_BINARY and C10_CARCARA_BINARY to trusted, absolute,
pre-installed executable paths. Run only in OS-isolated CI/dev environment.
Exit nonzero if cvc5+Carcara do not genuinely certify UNSAT.
"""
import os
import sys
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
