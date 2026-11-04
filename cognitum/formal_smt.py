"""C10 typed, bounded linear integer SMT adapter layer.

No strings are parsed as expressions; no solver script execution. External
Z3/cvc5 are OPTIONAL and only called in trusted in-process development.
Lu security admission and OS process containment are separate requirements.
"""
from dataclasses import dataclass
from itertools import product
from math import prod
from .formal_boolean import CNF, evaluates_true, solve as boolean_solve, verify as boolean_verify

MAX_INT_VARS=8
MAX_DOMAIN_WIDTH=32
MAX_ATOMS=64
MAX_TERMS=128
MAX_EXHAUSTIVE=4096
MAX_TIMEOUT_MS=10000


@dataclass(frozen=True)
class IntVar:
    name: str
    lower: int
    upper: int


@dataclass(frozen=True)
class LinearAtom:
    terms: tuple[tuple[str,int], ...]
    relation: str  # eq, ne, le, lt, ge, gt
    rhs: int


@dataclass(frozen=True)
class SMTProblem:
    integers: tuple[IntVar, ...]
    atoms: tuple[LinearAtom, ...]


@dataclass(frozen=True)
class SMTResult:
    status: str   # SAT, UNSAT_EXHAUSTIVE, UNSAT_UNVERIFIED, UNKNOWN, UNSUPPORTED
    witness: tuple[int, ...] = ()
    backend: str = ""
    assurance: str = "solver_reported"
    limitation: str = "natural_language_formalization_not_verified"


def validate(problem: SMTProblem):
    if type(problem) is not SMTProblem or type(problem.integers) is not tuple or type(problem.atoms) is not tuple:
        raise ValueError("typed SMT structure required")
    if not 1<=len(problem.integers)<=MAX_INT_VARS or len(problem.atoms)>MAX_ATOMS:
        raise ValueError("SMT size bound")
    names=set()
    for v in problem.integers:
        if (type(v) is not IntVar or type(v.name) is not str
                or not v.name.isascii() or not v.name.isidentifier()
                or not 1<=len(v.name)<=32 or v.name in names
                or type(v.lower) is not int or type(v.upper) is not int
                or abs(v.lower)>10000 or abs(v.upper)>10000
                or v.lower>v.upper or v.upper-v.lower>MAX_DOMAIN_WIDTH):
            raise ValueError("invalid bounded integer variable")
        names.add(v.name)
    total=0
    for a in problem.atoms:
        if (type(a) is not LinearAtom or type(a.terms) is not tuple
                or a.relation not in ("eq","ne","le","lt","ge","gt")
                or type(a.rhs) is not int or abs(a.rhs)>100000000):
            raise ValueError("invalid bounded linear atom")
        seen=set()
        for name,coef in a.terms:
            total+=1
            if (type(name) is not str or name not in names or name in seen
                    or type(coef) is not int or abs(coef)>10000):
                raise ValueError("invalid linear coefficient")
            seen.add(name)
        if total>MAX_TERMS:
            raise ValueError("SMT term bound")
    return problem


def satisfies(problem: SMTProblem, witness: tuple[int,...]):
    validate(problem)
    if (type(witness) is not tuple or len(witness)!=len(problem.integers)
            or any(type(n) is not int or not var.lower<=n<=var.upper
                   for var,n in zip(problem.integers,witness))):
        return False
    mapping={v.name:n for v,n in zip(problem.integers,witness)}
    for a in problem.atoms:
        lhs=sum(coef*mapping[name] for name,coef in a.terms)
        rhs=a.rhs
        ok={"eq":lhs==rhs,"ne":lhs!=rhs,"le":lhs<=rhs,
            "lt":lhs<rhs,"ge":lhs>=rhs,"gt":lhs>rhs}[a.relation]
        if not ok:
            return False
    return True


def exhaustive(problem: SMTProblem, max_cases=MAX_EXHAUSTIVE):
    """Independent complete check on tiny finite integer domains only."""
    validate(problem)
    count=prod(v.upper-v.lower+1 for v in problem.integers)
    if count>max_cases:
        return None
    for values in product(*(range(v.lower,v.upper+1) for v in problem.integers)):
        if satisfies(problem,values):
            return values
    return ()


def _z3(problem, timeout_ms):
    try:
        import z3
    except ImportError:
        return SMTResult("UNSUPPORTED",backend="z3",limitation="z3_not_installed")
    variables={v.name:z3.Int(v.name) for v in problem.integers}
    solver=z3.Solver()
    solver.set(timeout=timeout_ms)
    for v in problem.integers:
        solver.add(variables[v.name]>=v.lower,variables[v.name]<=v.upper)
    for a in problem.atoms:
        lhs=z3.Sum([coef*variables[name] for name,coef in a.terms]) if a.terms else z3.IntVal(0)
        expr={"eq":lhs==a.rhs,"ne":lhs!=a.rhs,"le":lhs<=a.rhs,
              "lt":lhs<a.rhs,"ge":lhs>=a.rhs,"gt":lhs>a.rhs}[a.relation]
        solver.add(expr)
    status=solver.check()
    if status==z3.sat:
        m=solver.model()
        return SMTResult("SAT",tuple(m.eval(variables[v.name],model_completion=True).as_long()
                                     for v in problem.integers),"z3","witness_rechecked")
    if status==z3.unsat:
        return SMTResult("UNSAT_UNVERIFIED",backend="z3",limitation="no_proof_certificate")
    return SMTResult("UNKNOWN",backend="z3",limitation="resource_limit_or_solver_unknown")


def _cvc5(problem,timeout_ms):
    try:
        import cvc5
        from cvc5 import Kind
    except ImportError:
        return SMTResult("UNSUPPORTED",backend="cvc5",limitation="cvc5_not_installed")
    s=cvc5.Solver()
    s.setLogic("QF_LIA")
    s.setOption("tlimit-per",str(timeout_ms))
    integer=s.getIntegerSort()
    variables={v.name:s.mkConst(integer,v.name) for v in problem.integers}
    def integer_constant(n):return s.mkInteger(n)
    for v in problem.integers:
        s.assertFormula(s.mkTerm(Kind.GEQ,variables[v.name],integer_constant(v.lower)))
        s.assertFormula(s.mkTerm(Kind.LEQ,variables[v.name],integer_constant(v.upper)))
    kind={"eq":Kind.EQUAL,"le":Kind.LEQ,"lt":Kind.LT,
          "ge":Kind.GEQ,"gt":Kind.GT}
    for a in problem.atoms:
        terms=[s.mkTerm(Kind.MULT,integer_constant(coef),variables[name]) for name,coef in a.terms]
        lhs=s.mkTerm(Kind.ADD,*terms) if len(terms)>1 else terms[0] if terms else integer_constant(0)
        if a.relation=="ne":
            term=s.mkTerm(Kind.NOT,s.mkTerm(Kind.EQUAL,lhs,integer_constant(a.rhs)))
        else:
            term=s.mkTerm(kind[a.relation],lhs,integer_constant(a.rhs))
        s.assertFormula(term)
    s.setOption("produce-models","true")
    status=s.checkSat()
    if status.isSat():
        try:
            witness=tuple(int(str(s.getValue(variables[v.name]))) for v in problem.integers)
        except (ValueError,TypeError):
            return SMTResult("UNKNOWN",backend="cvc5",limitation="model_decode_failed")
        return SMTResult("SAT",witness,"cvc5","witness_rechecked")
    if status.isUnsat():
        return SMTResult("UNSAT_UNVERIFIED",backend="cvc5",limitation="no_proof_certificate")
    return SMTResult("UNKNOWN",backend="cvc5",limitation="resource_limit_or_solver_unknown")


def solve(problem: SMTProblem, *, backend="z3", timeout_ms=1000):
    validate(problem)
    if type(timeout_ms) is not int or not 1<=timeout_ms<=MAX_TIMEOUT_MS:
        raise ValueError("timeout outside bound")
    if backend not in ("z3","cvc5","exhaustive"):
        return SMTResult("UNSUPPORTED",backend=str(backend),limitation="backend_not_allowed")
    if backend=="exhaustive":
        outcome=exhaustive(problem)
        if outcome is None:
            return SMTResult("UNKNOWN",backend=backend,limitation="exhaustive_budget")
        if outcome:
            return SMTResult("SAT",outcome,backend,"witness_rechecked")
        return SMTResult("UNSAT_EXHAUSTIVE",backend=backend,assurance="independent_exhaustion")
    result=(_z3 if backend=="z3" else _cvc5)(problem,timeout_ms)
    if result.status=="SAT":
        if not satisfies(problem,result.witness):
            return SMTResult("UNKNOWN",backend=backend,limitation="invalid_solver_witness")
        return result
    if result.status=="UNSAT_UNVERIFIED":
        checked=exhaustive(problem)
        if checked==():
            return SMTResult("UNSAT_EXHAUSTIVE",backend=backend,
                             assurance="independent_exhaustion")
        if checked is not None:
            return SMTResult("UNKNOWN",backend=backend,limitation="solver_disagrees_with_verifier")
    return result
