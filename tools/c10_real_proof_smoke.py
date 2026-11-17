"""Real native C10 proof acceptance, not mocks.

Set C10_CVC5_BINARY and C10_CARCARA_BINARY to trusted, absolute,
pre-installed executable paths. Run only in OS-isolated CI/dev environment.
Exit nonzero if cvc5+Carcara do not genuinely certify UNSAT.
"""
import os
import sys
import json
from dataclasses import asdict
from hashlib import sha256
import subprocess
from tempfile import TemporaryDirectory
from pathlib import Path

from cognitum.formal_smt import IntVar, LinearAtom, SMTProblem
from cognitum.formal_proofs import (certify_unsat,smtlib_for_problem,_reviewed_rules,
    _producer_args,_proof_body,_checker_args,MAX_PROOF_BYTES,MAX_OUTPUT_BYTES)


def main():
    cvc5=os.environ.get("C10_CVC5_BINARY","")
    carcara=os.environ.get("C10_CARCARA_BINARY","")
    if not all(Path(x).is_absolute() and Path(x).is_file()
               for x in (cvc5,carcara)):
        raise SystemExit("C10 native proof binaries MUST be provided explicitly")
    rare=os.environ.get("C10_RARE_RULES")
    if rare is not None:
        return paired_acceptance(cvc5,carcara,rare)
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
                [cvc5, "--dump-proofs", "--proof-format-mode=alethe",
                 "--simplification=none","--dag-thresh=0",
                 "--proof-granularity=theory-rewrite",str(problem_file)],
                cwd=folder, input=b"", stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=15, check=False,
            )
            print("C10 producer exit:", produced.returncode,
                  "stdout-prefix:", repr(produced.stdout[:200]),
                  "stderr-prefix:", repr(produced.stderr[:600]), flush=True)
            if produced.returncode == 0 and produced.stdout.startswith(b"unsat\n"):
                proof_file.write_bytes(produced.stdout.split(b"\n",1)[1])
                checked=subprocess.run(
                    [carcara, "check", "--allow-int-real-subtyping",
                     "--expand-let-bindings", str(proof_file), str(problem_file)],
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



def paired_acceptance(cvc5,carcara,rare):
    """Strict real native gate for the fixed upstream-paired toolchain.

    Preserve native proof/transcript evidence even on failure. All SMT inputs
    are synthetic fixtures, never arbitrary external data or model code.
    """
    rules=_reviewed_rules(rare)
    output=Path(os.environ.get("C10_CERT_EVIDENCE","c10-proof-evidence")).resolve()
    output.mkdir(exist_ok=False)
    rules_path=output/"rewrites.eo"
    rules_path.write_bytes(rules)
    variable=(IntVar("x",-5,5),)
    unsat=SMTProblem(variable,(LinearAtom((("x",1),),"eq",1),
                               LinearAtom((("x",1),),"eq",2)))
    sat=SMTProblem(variable,(LinearAtom((("x",1),),"eq",1),))
    # General QF_LIA case outside the 4096-case finite verifier limit.
    wide=SMTProblem(tuple(IntVar(n,0,32) for n in ("a","b","c")),
        (LinearAtom((("a",1),("b",1),("c",1)),"le",10),
         LinearAtom((("a",1),("b",1),("c",1)),"ge",11)))
    report={"schema":"cognitum.cog06e.native-proof.v1",
            "source_sha":os.environ.get("COG06B_EXPECTED_SHA",""),
            "upstream_cvc5":"cvc5-1.4.2",
            "upstream_carcara":"394edbb15ba95c47893f1d821fddde7e016af178",
            "binary_sha256":{"producer":sha256(Path(cvc5).read_bytes()).hexdigest(),
                             "checker":sha256(Path(carcara).read_bytes()).hexdigest()},
            "rewrite_sha256":sha256(rules).hexdigest(),"cases":{}}
    def save():
        (output/"result.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    def invoke(command,stem):
        p=subprocess.run(command,cwd=output,stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15,check=False)
        if len(p.stdout)>MAX_OUTPUT_BYTES or len(p.stderr)>MAX_OUTPUT_BYTES:
            raise RuntimeError("bounded native evidence exceeded")
        (output/(stem+".stdout")).write_bytes(p.stdout)
        (output/(stem+".stderr")).write_bytes(p.stderr)
        return p
    def valid(p):return p.returncode==0 and p.stdout.strip().lower()==b"valid"
    def cert(problem,label):
        verdict=certify_unsat(problem,cvc5_binary=cvc5,carcara_binary=carcara,
                              rare_file=rare,timeout_seconds=15)
        source=output/(label+".smt2");source.write_bytes(smtlib_for_problem(problem))
        producer=invoke(_producer_args(cvc5,source,True),label+"-producer")
        body=_proof_body(producer.stdout,True)
        record={"adapter":asdict(verdict),"producer_exit":producer.returncode,
                "source_sha256":sha256(source.read_bytes()).hexdigest()}
        report["cases"][label]=record;save()
        if producer.returncode!=0 or body is None or not 1<=len(body)<=MAX_PROOF_BYTES:
            return False,None
        proof=output/(label+".alethe");proof.write_bytes(body)
        checked=invoke(_checker_args(carcara,proof,source,rules_path),label+"-checker")
        record.update(checker_exit=checked.returncode,
                      checker_verdict=checked.stdout[:100].decode("utf-8","replace"),
                      proof_sha256=sha256(body).hexdigest())
        save()
        accepted=(verdict.status=="CERTIFIED_UNSAT" and verdict.problem_sha256==record["source_sha256"]
                  and bool(verdict.proof_sha256) and valid(checked))
        return accepted,proof
    simple,proof=cert(unsat,"contradiction")
    global_ok,_=cert(wide,"wide_contradiction")
    control=certify_unsat(sat,cvc5_binary=cvc5,carcara_binary=carcara,
                          rare_file=rare,timeout_seconds=15)
    sat_source=output/"sat.smt2";sat_source.write_bytes(smtlib_for_problem(sat))
    sat_native=invoke(_producer_args(cvc5,sat_source,True),"sat-producer")
    report["sat_control"]=asdict(control)
    report["sat_producer_exit"]=sat_native.returncode
    report["sat_confirmed"]=sat_native.returncode==0 and sat_native.stdout.startswith(b"sat\n")
    rejections={}
    if proof is not None:
        reject=invoke(_checker_args(carcara,proof,sat_source,rules_path),"wrong-problem")
        rejections["wrong_problem"]=not valid(reject)
    malformed=output/"malformed.alethe";malformed.write_bytes(b"(step t0 (cl) :rule definitely_unknown_rule)\n")
    hole=output/"hole.alethe";hole.write_bytes(b"(step t0 (cl) :rule hole)\n")
    for label,path in (("unsupported_rule",malformed),("explicit_hole",hole)):
        rejections[label]=not valid(invoke(_checker_args(carcara,path,sat_source,rules_path),label))
    report["negative_controls"]=rejections
    report["passed"]=(simple and global_ok and control.status=="NOT_UNSAT"
                      and report["sat_confirmed"] and len(rejections)==3 and all(rejections.values()))
    save()
    print(json.dumps(report,indent=2),flush=True)
    if not report["passed"]:
        raise SystemExit("C10 native independent certificate gate FAILED; no unchecked proof accepted")
    return 0


if __name__=="__main__":
    sys.exit(main())
