"""C10 optional Alethe UNSAT certification through cvc5 and Carcara.

Experimental trusted-host-only adapter. Never run model-selected binaries and
never enable in Lu without host-managed worker isolation/authorization. C10
uses existing maintained proof producer/checker; does NOT parse/check Alethe.
"""
from dataclasses import dataclass
from hashlib import sha256, sha1
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
from time import monotonic

from .formal_smt import SMTProblem, validate

MAX_PROOF_BYTES = 8 * 1024 * 1024
MAX_OUTPUT_BYTES = 9 * 1024 * 1024
MAX_SMTLIB_BYTES = 32768
MAX_WALL_SECONDS = 15
RARE_RULES_BLOB = "752a737f289c62c665f850fe2ab05328295ce8bb"
MAX_REWRITE_BYTES = 128 * 1024


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
            members=[(_atom(n) if c == 1 else "(* "+_int(c)+" "+_atom(n)+")") for n,c in a.terms]
            lhs=members[0] if len(members)==1 else "(+ "+" ".join(members)+")"
        lines.append("(assert ("+relation[a.relation]+" "+lhs+" "+_int(a.rhs)+"))")
    lines.append("(check-sat)")
    data=("\n".join(lines)+"\n").encode("ascii")
    if len(data)>MAX_SMTLIB_BYTES:
        raise ValueError("formal proof input exceeds serialized bound")
    return data


def _reviewed_rules(rare_file):
    if rare_file is None:
        return None
    if type(rare_file) is not str:
        raise ValueError("trusted rewrite rules path required")
    path=Path(rare_file)
    if (not path.is_absolute() or path.is_symlink() or not path.is_file()
            or not 1<=path.stat().st_size<=MAX_REWRITE_BYTES):
        raise ValueError("reviewed rewrite database unavailable")
    raw=path.read_bytes()
    if sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()!=RARE_RULES_BLOB:
        raise ValueError("unreviewed rewrite database")
    return raw


def _producer_args(binary, source_path, paired):
    flags=["--dump-proofs","--proof-format-mode=alethe"]
    if not paired:
        flags+=["--simplification=none","--dag-thresh=0","--proof-granularity=theory-rewrite"]
    return [binary,*flags,str(source_path)]


def _proof_body(out, paired):
    if len(out)>MAX_OUTPUT_BYTES or not out.startswith(b"unsat\n"):
        return None
    body=out.split(b"\n",1)[1]
    # Remove exactly the documented outer producer envelope, never proof steps.
    if paired and body.startswith(b"(\n") and body.endswith(b")\n"):
        body=body[2:-2]
    return body


def _checker_args(binary, proof_path, source_path, rules_path=None):
    flags=["check","--allow-int-real-subtyping","--expand-let-bindings"]
    if rules_path is not None:
        flags+=["--rare-file",str(rules_path)]
    return [binary,*flags,str(proof_path),str(source_path)]


def certify_unsat(
    problem: SMTProblem, *, cvc5_binary: str, carcara_binary: str,
    timeout_seconds: int = 10, rare_file: str | None = None,
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
    try:
        rules=_reviewed_rules(rare_file)
    except (OSError,ValueError):
        return ProofVerdict("UNVERIFIED",problem_sha256=problem_hash,
                            limitation="reviewed_rewrite_database_unavailable")
    deadline=monotonic()+timeout_seconds
    with TemporaryDirectory(prefix="c10-proof-") as work:
        path=Path(work)
        source_path=path/"problem.smt2"
        proof_path=path/"problem.smt2.alethe"
        source_path.write_bytes(source)
        rules_path=None
        if rules is not None:
            rules_path=path/"rewrites.eo"
            rules_path.write_bytes(rules)
        try:
            # stdout is proof evidence; never pass through a shell.
            produced=subprocess.run(
                _producer_args(cvc5_binary,source_path,rules is not None),cwd=work,stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                timeout=max(0.001,deadline-monotonic()),check=False,
            )
        except (OSError,subprocess.TimeoutExpired):
            return ProofVerdict("UNVERIFIED",problem_sha256=problem_hash,
                                limitation="producer_execution_or_timeout")
        if produced.returncode!=0:
            return ProofVerdict("UNVERIFIED",problem_sha256=problem_hash,
                                limitation="producer_nonzero_exit")
        out=produced.stdout
        proof=_proof_body(out,rules is not None)
        if proof is None:
            return ProofVerdict("NOT_UNSAT",problem_sha256=problem_hash,
                                limitation="no_unsat_proof_produced")
        if not 1<=len(proof)<=MAX_PROOF_BYTES:
            return ProofVerdict("UNVERIFIED",problem_sha256=problem_hash,
                                limitation="producer_empty_or_oversized_proof")
        proof_path.write_bytes(proof)
        if monotonic()>=deadline:
            return ProofVerdict("UNVERIFIED",problem_sha256=problem_hash,
                                limitation="aggregate_proof_timeout")
        try:
            checked=subprocess.run(
                _checker_args(carcara_binary,proof_path,source_path,rules_path),
                cwd=work,stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                timeout=max(0.001,deadline-monotonic()),check=False,
            )
        except (OSError,subprocess.TimeoutExpired):
            return ProofVerdict("UNVERIFIED",problem_sha256=problem_hash,
                                limitation="checker_execution_or_timeout")
        # 'holey', 'invalid', and any unrecognized result are NOT certified.
        if (monotonic()<deadline and checked.returncode==0 and len(checked.stdout)<=4096
                and checked.stdout.strip().lower()==b"valid"):
            return ProofVerdict("CERTIFIED_UNSAT",problem_sha256=problem_hash,
                                proof_sha256=sha256(proof).hexdigest(),
                                limitation="trusted_host_proof_checker_only")
        return ProofVerdict("UNVERIFIED",problem_sha256=problem_hash,
                            limitation="checker_failed_or_not_valid")
