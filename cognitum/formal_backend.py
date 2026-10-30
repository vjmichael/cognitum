"""C10 P2: strict typed SMT-LIB compiler and host-registered offline solver adapters.

Never interpret arbitrary model text as executable SMT-LIB; typed protobuf input only.
SAT is accepted only after an independent, exact model evaluation; UNSAT is
reported as a solver claim, not a verified formal proof. A host-controlled
registry authorizes backend execution; production Lu admission is pending.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from fractions import Fraction
from typing import Callable

from .proto import formal_backend_pb2 as p
from .formal_solver import _decode, _encode

NAME = re.compile(r'[A-Za-z][A-Za-z0-9_]{0,31}\Z', re.ASCII)
DECIMAL = re.compile(r'-?(?:0|[1-9][0-9]{0,24})\Z', re.ASCII)
MAX_INPUT = 65536
MAX_OUTPUT = 65536
MAX_VARIABLES = 32
MAX_ASSERTIONS = 64
MAX_NODES = 800
MAX_DEPTH = 24
MAX_TIME_MS = 5000

class UnsupportedFormula(ValueError): pass


def integer(text):
    if not DECIMAL.fullmatch(text): raise ValueError('INVALID_EXACT_INTEGER')
    return int(text)


def _numeral(n):
    return str(n) if n >= 0 else f'(- {-n})'


def _rational(value):
    return _numeral(value.numerator) if value.denominator == 1 else f'(/ {_numeral(value.numerator)} {value.denominator})'


def _type_expr(expr, symbols, depth, nodes):
    nodes[0] += 1
    if nodes[0] > MAX_NODES or depth > MAX_DEPTH: raise ValueError('EXPRESSION_SIZE_LIMIT')
    kind = expr.WhichOneof('node')
    if kind == 'variable':
        if expr.variable not in symbols: raise ValueError('UNKNOWN_VARIABLE')
        return symbols[expr.variable], expr.variable, ('var',expr.variable)
    if kind == 'boolean':return (p.BOOL,0), ('true' if expr.boolean else 'false'), ('bool',bool(expr.boolean))
    if kind == 'integer':
        n = integer(expr.integer.decimal)
        return (p.INT,0),_numeral(n),('int',n)
    if kind == 'rational':
        n=integer(expr.rational.numerator); d=integer(expr.rational.denominator)
        if d <= 0: raise ValueError('INVALID_RATIONAL')
        val=Fraction(n,d)
        return (p.REAL,0),_rational(val),('real',val)
    if kind == 'bitvector':
        val,width=expr.bitvector.value,expr.bitvector.width
        if not 1<=width<=64 or val >= (1<<width): raise ValueError('INVALID_BITVECTOR')
        return (p.BV,width),f'(_ bv{val} {width})',('bv',val,width)
    if kind != 'application': raise ValueError('MISSING_EXPRESSION')
    op=expr.application.op
    args=[_type_expr(x,symbols,depth+1,nodes) for x in expr.application.args]
    ts=[x[0] for x in args]; ss=[x[1] for x in args]; ns=[x[2] for x in args]
    b=(p.BOOL,0)
    def check(test):
        if not test:raise ValueError('INVALID_OPERAND_SORT_OR_ARITY')
    def same():return len(ts)>0 and all(x==ts[0] for x in ts)
    smt={p.AND:'and',p.OR:'or',p.NOT:'not',p.IMPLIES:'=>',p.EQ:'=',p.ITE:'ite',p.ADD:'+',p.SUB:'-',p.MUL:'*',p.LT:'<',p.LE:'<=',p.GT:'>',p.GE:'>=',p.XOR:'xor',p.BVAND:'bvand',p.BVOR:'bvor',p.BVNOT:'bvnot',p.BVADD:'bvadd',p.BVULT:'bvult'}
    if op not in smt:raise UnsupportedFormula('UNSUPPORTED_OPERATOR')
    if op in (p.AND,p.OR,p.XOR):check((len(ts)==2 if op==p.XOR else len(ts)>=2) and all(t==b for t in ts));out=b
    elif op==p.NOT:check(len(ts)==1 and ts[0]==b);out=b
    elif op==p.IMPLIES:check(len(ts)==2 and ts==[b,b]);out=b
    elif op==p.EQ:check(len(ts)==2 and same());out=b
    elif op==p.ITE:check(len(ts)==3 and ts[0]==b and ts[1]==ts[2]);out=ts[1]
    elif op in (p.ADD,p.SUB,p.MUL):check((2<=len(ts)<=8 if op!=p.SUB else 1<=len(ts)<=8) and same() and ts[0][0] in (p.INT,p.REAL));out=ts[0]
    elif op in (p.LT,p.LE,p.GT,p.GE):check(len(ts)==2 and same() and ts[0][0] in (p.INT,p.REAL));out=b
    elif op in (p.BVAND,p.BVOR,p.BVADD):check(len(ts)==2 and same() and ts[0][0]==p.BV);out=ts[0]
    elif op==p.BVNOT:check(len(ts)==1 and ts[0][0]==p.BV);out=ts[0]
    elif op==p.BVULT:check(len(ts)==2 and same() and ts[0][0]==p.BV);out=b
    return out,'('+smt[op]+' '+' '.join(ss)+')',('app',op,ns,out)


def compile_run(request):
    if request.schema_version!=1 or len(request.variables)>MAX_VARIABLES or len(request.assertions)>MAX_ASSERTIONS:
        raise ValueError('INVALID_BACKEND_REQUEST')
    if request.timeout_ms>MAX_TIME_MS or not re.fullmatch(r'[A-Za-z0-9_.:-]{0,64}',request.trace_id, re.ASCII):
        raise ValueError('INVALID_LIMIT_OR_TRACE')
    symbols={};decl=[]
    sort_names={p.BOOL:'Bool',p.INT:'Int',p.REAL:'Real'}
    for var in request.variables:
        if not NAME.fullmatch(var.name) or var.name in symbols:raise ValueError('INVALID_VARIABLE')
        if var.sort not in (p.BOOL,p.INT,p.REAL,p.BV):raise UnsupportedFormula('UNSUPPORTED_SORT')
        if var.sort==p.BV:
            if not 1<=var.width<=64:raise ValueError('INVALID_BV_WIDTH')
            sort=f'(_ BitVec {var.width})'
        else:
            if var.width:raise ValueError('UNEXPECTED_BV_WIDTH')
            sort=sort_names[var.sort]
        symbols[var.name]=(var.sort,var.width)
        decl.append(f'(declare-const {var.name} {sort})')
    statements=[]; trees=[];nodes=[0]
    for expr in request.assertions:
        typ,sm,tree=_type_expr(expr,symbols,0,nodes)
        if typ!=(p.BOOL,0):raise ValueError('ASSERTION_MUST_BE_BOOLEAN')
        statements.append('(assert '+sm+')');trees.append(tree)
    commands=['(set-option :produce-models true)','(set-option :print-success false)',*decl,*statements,'(check-sat)']
    if symbols: commands.append('(get-value ('+' '.join(symbols)+'))')
    script='\n'.join(commands)+'\n'
    if len(script.encode())>MAX_INPUT:raise ValueError('SMTLIB_SIZE_LIMIT')
    return script,symbols,trees


def tokenize_output(text):
    if len(text.encode('utf-8'))>MAX_OUTPUT or any(ord(x)>127 for x in text):raise ValueError('OVERSIZED_OR_NONASCII_RESPONSE')
    tokens=re.findall(r'\(|\)|[^\s()]+',text)
    if len(tokens)>4096:raise ValueError('TOO_MANY_RESPONSE_TOKENS')
    return tokens


def parse_sexpr(tokens,index=0,depth=0):
    if depth>30 or index>=len(tokens):raise ValueError('MALFORMED_SOLVER_RESPONSE')
    t=tokens[index]
    if t!='(':
        if t==')':raise ValueError('MALFORMED_SOLVER_RESPONSE')
        return t,index+1
    items=[];index+=1
    while True:
        if index>=len(tokens):raise ValueError('MALFORMED_SOLVER_RESPONSE')
        if tokens[index]==')':return items,index+1
        item,index=parse_sexpr(tokens,index,depth+1);items.append(item)
        if len(items)>128:raise ValueError('RESPONSE_LIST_LIMIT')


def parse_exact(x, sort,width):
    if sort==p.BOOL:
        if x not in ('true','false'):raise ValueError('BAD_BOOL_MODEL')
        return x=='true'
    if sort in (p.INT,p.REAL):
        def number(y):
            if isinstance(y,str):
                if DECIMAL.fullmatch(y):return Fraction(int(y),1)
                if re.fullmatch(r'[0-9]{1,25}\.[0-9]{1,25}',y):return Fraction(y)
            if isinstance(y,list) and len(y)==2 and y[0]=='-':return -number(y[1])
            if isinstance(y,list) and len(y)==3 and y[0]=='/':
                den=number(y[2]);
                if not den:raise ValueError('BAD_ZERO_DENOMINATOR')
                return number(y[1])/den
            raise ValueError('BAD_NUMERIC_MODEL')
        q=number(x)
        if sort==p.INT:
            if q.denominator!=1:raise ValueError('NONINTEGER_MODEL')
            return int(q)
        return q
    if sort==p.BV:
        if isinstance(x,str) and x.startswith('#b') and re.fullmatch('[01]+',x[2:]):
            if len(x[2:])!=width:raise ValueError('BITVECTOR_WIDTH_MISMATCH')
            return int(x[2:],2)
        if isinstance(x,str) and x.startswith('#x') and re.fullmatch('[0-9a-fA-F]+',x[2:]):
            v=int(x[2:],16)
            if len(x[2:])*4!=width:raise ValueError('BITVECTOR_WIDTH_MISMATCH')
            return v
        if isinstance(x,list) and len(x)==3 and x[0]=='_' and isinstance(x[1],str) and x[1].startswith('bv'):
            v=integer(x[1][2:]); w=integer(x[2]);
            if w!=width or v<0 or v>=1<<width:raise ValueError('BAD_BV_MODEL')
            return v
    raise ValueError('UNSUPPORTED_MODEL_VALUE')


def eval_expr(tree,model):
    if tree[0]=='var':return model[tree[1]]
    if tree[0] in ('bool','int','real'):return tree[1]
    if tree[0]=='bv':return tree[1]
    _,op,children,sort=tree
    a=[eval_expr(x,model) for x in children]
    if op==p.AND:return all(a)
    if op==p.OR:return any(a)
    if op==p.NOT:return not a[0]
    if op==p.XOR:return sum(bool(x) for x in a)%2==1
    if op==p.IMPLIES:return not a[0] or a[1]
    if op==p.EQ:return a[0]==a[1]
    if op==p.ITE:return a[1] if a[0] else a[2]
    if op==p.ADD:return sum(a)
    if op==p.SUB:return (-a[0] if len(a)==1 else a[0]-sum(a[1:]))
    if op==p.MUL:
        out=1
        for x in a:out*=x
        return out
    if op==p.LT:return a[0]<a[1]
    if op==p.LE:return a[0]<=a[1]
    if op==p.GT:return a[0]>a[1]
    if op==p.GE:return a[0]>=a[1]
    if op in (p.BVAND,p.BVOR,p.BVNOT,p.BVADD):
        mask=(1<<sort[1])-1
        if op==p.BVNOT:return (~a[0])&mask
        if op==p.BVAND:return a[0]&a[1]
        if op==p.BVOR:return a[0]|a[1]
        return (a[0]+a[1])&mask
    if op==p.BVULT:return a[0]<a[1]
    raise ValueError('UNSUPPORTED_EVALUATION')


def parse_response(output,symbols,trees):
    tokens=tokenize_output(output.strip());
    if not tokens:raise ValueError('EMPTY_SOLVER_RESPONSE')
    status=tokens[0]
    if status not in ('sat','unsat','unknown'):raise ValueError('BAD_SOLVER_STATUS')
    if status!='sat':
        if len(tokens)!=1:raise ValueError('EXTRANEOUS_SOLVER_OUTPUT')
        return status,[]
    if not symbols:
        if len(tokens)!=1:raise ValueError('EXTRANEOUS_SOLVER_OUTPUT')
        return status,[] if all(eval_expr(t,{}) is True for t in trees) else None
    node,next_i=parse_sexpr(tokens,1)
    if next_i!=len(tokens) or not isinstance(node,list) or len(node)!=len(symbols):raise ValueError('BAD_MODEL_PAIRS')
    model={}
    for item in node:
        if not isinstance(item,list) or len(item)!=2 or not isinstance(item[0],str) or item[0] not in symbols or item[0] in model:
            raise ValueError('BAD_MODEL_BINDING')
        sort,width=symbols[item[0]]
        model[item[0]]=parse_exact(item[1],sort,width)
    if not all(eval_expr(t,model) is True for t in trees):raise ValueError('MODEL_VIOLATES_ASSERTIONS')
    return status,[(name,model[name],*sort) for name,sort in symbols.items()]

@dataclass(frozen=True)
class ApprovedBackend:
    backend_id: str
    kind: str # "z3-cli", "cvc5-cli", "z3-lib"; no arbitrary command strings
    absolute_path: str
    sha256: str

    def validate(self):
        if self.kind not in ('z3-cli','cvc5-cli','z3-lib') or self.backend_id not in ('z3-cli','cvc5-cli','z3-lib') or self.backend_id!=self.kind:
            raise ValueError('INVALID_BACKEND_KIND')
        loc=Path(self.absolute_path)
        if not loc.is_absolute() or not loc.is_file() or loc.is_symlink():raise ValueError('BACKEND_MUST_BE_PINNED_FILE')
        if len(self.sha256)!=64 or any(c not in '0123456789abcdef' for c in self.sha256):raise ValueError('INVALID_BACKEND_DIGEST')
        # The hash verifies the host-selected binary; no caller-provided binary paths.
        with loc.open('rb') as f:
            h=hashlib.file_digest(f,'sha256').hexdigest()
        if h!=self.sha256:raise ValueError('BACKEND_BINARY_CHANGED')


def _run_backend(approved: ApprovedBackend, script: str, timeout_ms: int):
    if approved.kind=='z3-lib':
        cmd=[sys.executable,'-m','cognitum.formal_z3_worker',approved.absolute_path]
    elif approved.kind=='z3-cli':cmd=[approved.absolute_path,'-in','-smt2']
    else:cmd=[approved.absolute_path,'--lang=smt2','--incremental','--produce-models']
    # Check status in a separate invocation. Never request a model for UNSAT.
    # Keep one aggregate timeout across both invocations (not timeout * 2).
    env={k:v for k,v in os.environ.items() if k in ('SYSTEMROOT','WINDIR','PATH','PYTHONPATH')}
    deadline=time.monotonic()+timeout_ms/1000
    def invoke(payload):
        remaining=deadline-time.monotonic()
        if remaining<=0:raise subprocess.TimeoutExpired(cmd,timeout_ms/1000)
        cp=subprocess.run(cmd,input=payload.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                          timeout=remaining,check=False,env=env,cwd=str(Path(__file__).resolve().parents[1]))
        if len(cp.stdout)>MAX_OUTPUT or len(cp.stderr)>1024:raise ValueError('SOLVER_OUTPUT_LIMIT')
        if cp.returncode:raise ValueError('BACKEND_EXIT_NONZERO')
        return cp.stdout.decode('ascii','strict')
    pos=script.find('\n(get-value (')
    status_script=script if pos<0 else script[:pos]+'\n'
    first=invoke(status_script).strip()
    if first not in ('sat','unsat','unknown'):raise ValueError('BAD_STATUS_PHASE')
    if first!='sat' or pos<0:return first+'\n'
    complete=invoke(script)
    if not complete.startswith('sat\n'):raise ValueError('CHANGED_STATUS_BETWEEN_PHASES')
    return complete

class SolverRegistry:
    def __init__(self, approved: tuple[ApprovedBackend,...] = ()): 
        self.backends={x.backend_id:x for x in approved}
        if len(self.backends)!=len(approved):raise ValueError('DUPLICATE_BACKEND_ID')
        self.enabled=True

    def disable(self):
        # Cancels new dispatch only. In-flight kill is Lu supervisor responsibility.
        self.enabled=False

    def run_frame(self, frame: bytes, *, host_authorized: bool=False, runner: Callable|None=None) -> bytes:
        request=_decode(frame,p.BackendRun,MAX_INPUT)
        digest=hashlib.sha256(frame).digest()
        result=p.BackendResult(schema_version=1,backend_id=request.backend_id,request_sha256=digest,
                               trace_id=request.trace_id,verification=p.NO_EVIDENCE,
                               verdict=p.REJECTED,reason_code='HOST_AUTHORIZATION_REQUIRED')
        if not host_authorized:return _encode(result,MAX_OUTPUT)
        if not self.enabled:
            result.reason_code='REGISTRY_DISABLED'
            return _encode(result,MAX_OUTPUT)
        started=time.monotonic_ns()
        try:
            script,symbols,trees=compile_run(request)
            backend=self.backends.get(request.backend_id)
            if backend is None:raise UnsupportedFormula('BACKEND_NOT_REGISTERED')
            backend.validate()
            result.backend_fingerprint=backend.sha256
            timeout=request.timeout_ms or 2000
            output=runner(backend,script,timeout) if runner else _run_backend(backend,script,timeout)
            if type(output) is not str or len(output.encode())>MAX_OUTPUT:raise ValueError('INVALID_SOLVER_OUTPUT')
            result.solver_output_sha256=hashlib.sha256(output.encode()).digest()
            status, values=parse_response(output,symbols,trees)
            if status=='unsat':
                result.verdict=p.UNSAT;result.verification=p.UNSAT_NOT_PROVEN;result.reason_code='UNSAT_SOLVER_CLAIM_NOT_A_PROOF'
            elif status=='unknown':
                result.verdict=p.UNKNOWN;result.reason_code='SOLVER_UNKNOWN'
            elif values is None:
                result.verdict=p.UNKNOWN;result.reason_code='SAT_MODEL_UNVERIFIED'
            else:
                result.verdict=p.SAT;result.verification=p.SAT_WITNESS_CHECKED;result.reason_code='EXACT_MODEL_CHECKED'
                for name,value,sort,width in values:
                    s=str(int(value)) if sort in (p.BOOL,p.INT,p.BV) else f'{value.numerator}/{value.denominator}'
                    result.model.add(name=name,sort=sort,exact_value=s,width=width)
        except subprocess.TimeoutExpired:
            result.verdict=p.UNKNOWN;result.reason_code='SOLVER_TIMEOUT'
        except UnsupportedFormula as exc:
            result.verdict=p.REJECTED;result.reason_code=str(exc)
        except (ValueError,OSError,UnicodeError,OverflowError) as exc:
            result.verdict=p.ERROR;result.reason_code=str(exc)[:64]
        finally:result.wall_ns=time.monotonic_ns()-started
        return _encode(result,MAX_OUTPUT)


def verify_backend_frame(request_frame: bytes, result_frame: bytes) -> bytes:
    """Separate receipt checker: SAT valuation is independently reevaluated.

    It never upgrades UNSAT (or UNKNOWN) into a proof. Backend fingerprints
    are provenance fields, NOT cryptographic attestations of executed code.
    """
    receipt=p.VerificationReceipt(verifier_id='cognitum.c10.exact-model-v1')
    try:
        request=_decode(request_frame,p.BackendRun,MAX_INPUT)
        result=_decode(result_frame,p.BackendResult,MAX_OUTPUT)
        receipt.request_sha256=hashlib.sha256(request_frame).digest()
        receipt.result_sha256=hashlib.sha256(result_frame).digest()
        script,symbols,trees=compile_run(request)
        if (result.schema_version!=1 or result.request_sha256!=receipt.request_sha256 or
                result.backend_id!=request.backend_id or result.trace_id!=request.trace_id or
                result.host_approved or result.semantic_formalization_verified):
            raise ValueError('UNBOUND_OR_FALSE_ASSURANCE')
        if result.verdict!=p.SAT:
            if result.model or result.verification==p.SAT_WITNESS_CHECKED:
                raise ValueError('NON_SAT_PROOF_CLAIM')
            receipt.reason_code='NO_INDEPENDENT_NON_SAT_PROOF'
            return _encode(receipt)
        if result.verification!=p.SAT_WITNESS_CHECKED or len(result.model)!=len(symbols):
            raise ValueError('BAD_SAT_WITNESS')
        env={}
        for item,(name,(sort,width)) in zip(result.model,symbols.items()):
            if item.name!=name or item.sort!=sort or item.width!=width:raise ValueError('MODEL_SORT_MISMATCH')
            if sort==p.BOOL:
                if item.exact_value not in ('0','1'):raise ValueError('BAD_BOOLEAN')
                value=bool(int(item.exact_value))
            elif sort==p.INT:value=integer(item.exact_value)
            elif sort==p.REAL:
                r=re.fullmatch(r'(-?(?:0|[1-9][0-9]{0,24}))/([1-9][0-9]{0,24})',item.exact_value)
                if not r:raise ValueError('BAD_RATIONAL')
                value=Fraction(integer(r.group(1)),integer(r.group(2)))
            else:
                value=integer(item.exact_value)
                if value<0 or value>=(1<<width):raise ValueError('BAD_BV_RANGE')
            env[name]=value
        if not all(eval_expr(t,env) is True for t in trees):raise ValueError('WITNESS_FALSIFIES_ASSERTION')
        receipt.evidence_valid=True
        receipt.reason_code='SAT_WITNESS_RECHECKED'
    except (ValueError,OverflowError,UnicodeError):
        receipt.reason_code='INVALID_OR_UNBOUND_EVIDENCE'
    return _encode(receipt)
