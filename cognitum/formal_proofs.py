"""C10 optional Alethe UNSAT certification through cvc5 and Carcara.

Experimental trusted-host-only adapter. Never run model-selected binaries and
never enable in Lu without host-managed worker isolation/authorization. C10
uses existing maintained proof producer/checker; does NOT parse/check Alethe.
"""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess

from .formal_smt import SMTProblem, validate

MAX_PROOF_BYTES = 8 * 1024 * 1024
MAX_OUTPUT_BYTES = 9 * 1024 * 1024
MAX_SMTLIB_BYTES = 32768
MAX_WALL_SECONDS = 15


@dataclass(frozen=True)
class ProofVerdict:
    status: str  # CERTIFIED_UNSAT | NOT_UNSAT | UNSUPPORTED | UNVERIFIED
    checker: str = "carcara"
    proof_format: str = "alethe"
    problem_sha256: str = ""
    proof_sha256: str = ""
    limitation: str = "no_external_checker_acceptance"


def _int(value: int) -> str:
    # SMT-LIB negative integers use unary minus, never a '-3' numeral token.
    return str(value) if value >= 0 else "(- " + str(-value) + ")"


def _atom(name):
    # Explicit prefix prevents collisions with SMT-LIB words (including 'true').
    return "c10_" + name


def smtlib_for_problem(problem: SMTProblem) -> bytes:
    """Deterministically serialize the typed bounded QF_LIA fragment."""
    validate(problem)
    lines=["(set-logic QF_LIA)", "(set-option :produce-proofs true)"]
    for v in problem.integers:
        name=_atom(v.name)
        lines.extend(("(declare-const "+name+" Int)",
                      "(assert (>= "+name+" "+_int(v.lower)+"))",
                      "(assert (<= "+name+" "+_int(v.upper)+"))"))
    relation={"eq":"=","ne":"distinct","le":"<=","lt":"<",
              "ge":">=","gt":">"}
    for a in problem.atoms:
        if not a.terms:
            lhs="0"
        else:
            members=["(* "+_int(c)+" "+_atom(n)+")" for n,c in a.terms]
            lhs=members[0] if len(members)==1 else "(+ "+" ".join(members)+")"
        lines.append("(assert ("+relation[a.relation]+" "+lhs+" "+_int(a.rhs)+"))")
    lines.append("(check-sat)")
    data=("\n".join(lines)+"\n").encode("ascii")
    if len(data)>MAX_SMTLIB_BYTES:
        raise ValueError("formal proof input exceeds serialized bound")
    return data


def certify_unsat(
    problem: SMTProblem, *, cvc5_binary: str, carcara_binary: str,
    timeout_seconds: int = 10,
) -> ProofVerdict:
    """Use the real independent Alethe checker; NEVER certify by solver vote.

    Both executable paths MUST be installed and selected by trusted host
    configuration; this function is not a user/API entrypoint. The caller must
    confine these native processes in a separate OS-restricted worker before
    admitting untrusted problem data. Neither Python timeout nor tempdir
    substitutes for a Lu process containment boundary.
    """
    source=smtlib_for_problem(problem)
    problem_hash=sha256(source).hexdigest()
    empty=ProofVerdict("UNVERIFIED",problem_sha256=problem_hash)
    if (type(cvc5_binary) is not str or type(carcara_binary) is not str
            or not cvc5_binary or not carcara_binary
            or type(timeout_seconds) is not int
            or not 1<=timeout_seconds<=MAX_WALL_SECONDS):
        raise ValueError("trusted proof tool paths and time budget required")
    for binary in (cvc5_binary,carcara_binary):
        p=Path(binary)
        if not p.is_absolute() or not p.is_file():
            return ProofVerdict("UNSUPPORTED",problem_sha256=problem_hash,
                                limitation="trusted_checker_or_producer_missing")
    with TemporaryDirectory(prefix="c10-proof-") as work:
        path=Path(work)
        source_path=path/"problem.smt2"
        proof_path=path/"problem.smt2.alethe"
        source_path.write_bytes(source)
        try:
            # stdout is proof evidence; never pass through a shell.
            produced=subprocess.run(
                [cvc5_binary,"--dump-proofs","--proof-format-mode=alethe",
                 "--simplification=none","--dag-thresh=0",
                 "--proof-granularity=theory-rewrite",str(source_path)],cwd=work,stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                timeout=timeout_seconds,check=False,
            )
        except (OSError,subprocess.TimeoutExpired):
            return ProofVerdict("UNVERIFIED",problem_sha256=problem_hash,
                                limitation="producer_execution_or_timeout")
        if produced.returncode!=0:
            return ProofVerdict("UNVERIFIED",problem_sha256=problem_hash,
                                limitation="producer_nonzero_exit")
        out=produced.stdout
        if len(out)>MAX_OUTPUT_BYTES or not out.startswith(b"unsat\n"):
            return ProofVerdict("NOT_UNSAT",problem_sha256=problem_hash,
                                limitation="no_unsat_proof_produced")
        proof=out.split(b"\n",1)[1]
        if not 1<=len(proof)<=MAX_PROOF_BYTES:
            return ProofVerdict("UNVERIFIED",problem_sha256=problem_hash,
                                limitation="producer_empty_or_oversized_proof")
        proof_path.write_bytes(proof)
        try:
            checked=subprocess.run(
                [carcara_binary,"check",str(proof_path),str(source_path)],
                cwd=work,stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                timeout=timeout_seconds,check=False,
            )
        except (OSError,subprocess.TimeoutExpired):
            return ProofVerdict("UNVERIFIED",problem_sha256=problem_hash,
                                limitation="checker_execution_or_timeout")
        # 'holey', 'invalid', and any unrecognized result are NOT certified.
        if (checked.returncode==0 and len(checked.stdout)<=4096
                and checked.stdout.strip().lower()==b"valid"):
            return ProofVerdict("CERTIFIED_UNSAT",problem_sha256=problem_hash,
                                proof_sha256=sha256(proof).hexdigest(),
                                limitation="trusted_host_proof_checker_only")
        return ProofVerdict("UNVERIFIED",problem_sha256=problem_hash,
                            limitation="checker_failed_or_not_valid")
