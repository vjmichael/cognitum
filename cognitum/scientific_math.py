"""C05 bounded, separately typed scientific-mathematics reference specialists.

EXPERIMENTAL, trusted in-process, offline-only math kernels: NOT installed
in Lu, NOT exposed to a model, NOT an OS-isolated worker. Lu must authorize
all future specialist discovery and launch through its own C02/C04 gates.
No sympify, parse_expr, eval, exec, subprocess, filesystem or network access.
"""
import ast
from decimal import Decimal, localcontext, InvalidOperation, DivisionByZero, Overflow
from fractions import Fraction
import re

from google.protobuf.message import DecodeError
from .proto import specialists_pb2 as pb

MAX_WIRE=4096
_REQUESTS={
    "symbolic": (pb.SymbolicRequest,pb.SymbolicResult),
    "scientific": (pb.ScientificRequest,pb.ScientificResult),
    "precision": (pb.PrecisionRequest,pb.PrecisionResult),
    "linear": (pb.LinearRequest,pb.LinearResult),
    "root": (pb.RootRequest,pb.RootResult),
    "simulation": (pb.SimulationRequest,pb.SimulationResult),
}
_CANON_NUMBER=re.compile(r"-?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)\Z",re.ASCII)
_RATIONAL=re.compile(r"-?(?:[0-9]+/[0-9]+|[0-9]+(?:\.[0-9]*)?|\.[0-9]+)\Z",re.ASCII)
ALLOWED = "0123456789.xX+-*/() \t"  # strict AST still rejects X, callers can only use x

def _frame(data,cls):
    if type(data) is not bytes or not 0<len(data)<=MAX_WIRE:
        raise ValueError("invalid/oversized specialist Protobuf")
    obj=cls()
    try:
        obj.ParseFromString(data)
    except DecodeError as exc:
        raise ValueError("malformed specialist Protobuf") from exc
    known=cls()
    known.CopyFrom(obj)
    known.DiscardUnknownFields()
    if known!=obj or obj.SerializeToString(deterministic=True)!=data:
        raise ValueError("unknown/duplicate/noncanonical specialist Protobuf")
    return obj

def _wire(obj):
    data=obj.SerializeToString(deterministic=True)
    if not 0<len(data)<=MAX_WIRE:
        raise ValueError("specialist Protobuf exceeds size limit")
    return data

def _digits(n,maximum=80):
    if type(n) is not int or not 15<=n<=maximum:
        raise ValueError("digits outside supported precision range")
    return n

def _number(raw,*,as_fraction=True):
    if type(raw) is not str or not 1<=len(raw)<=64:
        raise ValueError("invalid numeric token size")
    pattern=_RATIONAL if as_fraction else _CANON_NUMBER
    if pattern.fullmatch(raw) is None:
        raise ValueError("numeric token outside decimal/rational grammar")
    try:
        n=Fraction(raw) if as_fraction else Decimal(raw)
    except (ZeroDivisionError,ValueError,InvalidOperation) as exc:
        raise ValueError("invalid numeric value") from exc
    if as_fraction:
        _bound(n)
    elif not n.is_finite():
        raise ValueError("nonfinite decimal")
    return n

def _bound(f,limit=512):
    if max(f.numerator.bit_length(),f.denominator.bit_length())>limit:
        raise ValueError("rational magnitude cap")
    return f

def _polynomial(source):
    """Parse at most degree-six single-variable polynomial with safe AST."""
    if type(source) is not str or not 1<=len(source)<=160:
        raise ValueError("bounded polynomial input required")
    if any(ch not in ALLOWED for ch in source):
        raise ValueError("unexpected polynomial characters")
    try:
        tree=ast.parse(source,mode="eval")
    except (SyntaxError,RecursionError,ValueError) as exc:
        raise ValueError("invalid polynomial syntax") from exc
    if sum(1 for _ in ast.walk(tree))>48:
        raise ValueError("polynomial AST too large")

    def normalize(p):
        p={k:_bound(v) for k,v in p.items() if v}
        if len(p)>7 or any(k>6 for k in p):
            raise ValueError("polynomial degree/term cap")
        return p
    def add(a,b,sign=1):
        x=a.copy()
        for degree,val in b.items():
            x[degree]=x.get(degree,Fraction(0))+sign*val
        return normalize(x)
    def mul(a,b):
        out={}
        for i,x in a.items():
            for j,y in b.items():
                if i+j>6:
                    raise ValueError("polynomial product degree bound")
                out[i+j]=_bound(out.get(i+j,Fraction(0))+x*y)
        return normalize(out)
    def visit(n,depth=0):
        if depth>12:
            raise ValueError("polynomial depth cap")
        if isinstance(n,ast.Name) and n.id=="x":
            return {1:Fraction(1)}
        if isinstance(n,ast.Constant) and type(n.value) in (int,float):
            token=ast.get_source_segment(source,n)
            return normalize({0:_number(token)})
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.UAdd,ast.USub)):
            r=visit(n.operand,depth+1)
            return normalize({k: (-v if isinstance(n.op,ast.USub) else v)
                              for k,v in r.items()})
        if isinstance(n,ast.BinOp) and isinstance(n.op,(ast.Add,ast.Sub,ast.Mult,ast.Div,ast.Pow)):
            a=visit(n.left,depth+1)
            b=visit(n.right,depth+1)
            if isinstance(n.op,ast.Add): return add(a,b)
            if isinstance(n.op,ast.Sub): return add(a,b,-1)
            if isinstance(n.op,ast.Mult): return mul(a,b)
            if isinstance(n.op,ast.Div):
                if set(b)-{0} or not b.get(0):
                    raise ValueError("only constant nonzero polynomial denominators")
                return normalize({k:_bound(v/b[0]) for k,v in a.items()})
            if set(b)-{0} or b.get(0,Fraction(0)).denominator!=1:
                raise ValueError("only bounded unsigned integer polynomial powers")
            exp=int(b.get(0,0))
            if not 0<=exp<=6: raise ValueError("polynomial exponent cap")
            out={0:Fraction(1)}
            for _ in range(exp): out=mul(out,a)
            return out
        raise ValueError("unapproved symbolic AST construct")
    return visit(tree.body)

def _poly_text(p):
    if not p: return "0"
    parts=[]
    for deg in sorted(p,reverse=True):
        val=p[deg]
        if not val: continue
        unit="x" if deg==1 else "x**"+str(deg) if deg>1 else ""
        coef=abs(val)
        term=(unit if coef==1 and unit else str(coef)+("*" if unit else "")+unit)
        sign="-" if val<0 else "+"
        parts.append((sign,term))
    if not parts: return "0"
    first,tail=parts[0],parts[1:]
    return ("-" if first[0]=="-" else "")+first[1]+ "".join(" "+("-" if s=="-" else "+")+" "+t for s,t in tail)

def _eval_poly(poly,x):
    out=Fraction(0)
    for degree,coefficient in poly.items():
        out=_bound(out+_bound(coefficient*(x**degree)))
    return out

def _symbolic(req):
    if req.action not in ("expand","derivative"): raise ValueError("unsupported symbolic action")
    poly=_polynomial(req.expression)
    if req.action=="derivative":
        poly={degree-1:_bound(c*degree) for degree,c in poly.items() if degree}
    return pb.SymbolicResult(
        polynomial=_poly_text(poly),assurance="exact_symbolic",
        limitations=["intent_not_verified","single_variable_polynomial_degree_le_6"],
    )

def _scientific(req):
    digits=_digits(req.digits)
    if req.function not in ("sin","cos","exp","log","sqrt"):
        raise ValueError("unsupported scientific function")
    arg=_number(req.argument,as_fraction=False)
    # Avoid massive exp allocations and costly transcendental range reduction.
    if abs(arg)>100:
        raise ValueError("scientific argument magnitude cap")
    if req.function=="log" and arg<=0 or req.function=="sqrt" and arg<0:
        raise ValueError("real-domain scientific function undefined")
    # Separate clone: never mutate mpmath's global precision configuration.
    try:
        from mpmath import mp
    except ImportError as exc:
        raise ValueError("optional_mpmath_unavailable") from exc
    ctx=mp.clone()
    ctx.dps=digits+12
    x=ctx.mpf(str(arg))
    f={"sin":ctx.sin,"cos":ctx.cos,"exp":ctx.exp,
       "log":ctx.log,"sqrt":ctx.sqrt}[req.function]
    y=f(x)
    if not ctx.isfinite(y):
        raise ValueError("scientific result not finite")
    return pb.ScientificResult(
        decimal=ctx.nstr(y,digits),digits=digits,method="mpmath",
        limitations=["approximation_not_exact","rounding_error_not_certified",
                     "input_units_radians_for_trigonometry","intent_not_verified"],
    )

def _precision(req):
    digits=_digits(req.digits,maximum=256)
    if req.action not in ("add","divide","sqrt"):
        raise ValueError("unsupported precision action")
    x=_number(req.left,as_fraction=False)
    if req.action!="sqrt":
        y=_number(req.right,as_fraction=False)
        if req.action=="divide" and y==0:
            raise ValueError("division by zero")
    elif req.right:
        raise ValueError("unneeded second operand")
    if req.action=="sqrt" and x<0:
        raise ValueError("square root outside real domain")
    try:
        with localcontext() as ctx:
            ctx.prec=digits
            ctx.traps[InvalidOperation]=True
            ctx.traps[DivisionByZero]=True
            ctx.traps[Overflow]=True
            result=(+(x+y) if req.action=="add" else
                    +(x/y) if req.action=="divide" else
                    x.sqrt(context=ctx))
    except (InvalidOperation,DivisionByZero,Overflow) as exc:
        raise ValueError("decimal numerical operation unavailable") from exc
    return pb.PrecisionResult(
        decimal=str(result),digits=digits,method="decimal",
        limitations=["precision_is_decimal_digits","rounding_may_apply",
                     "intent_not_verified"],
    )

def _mat(rows,required=False):
    if not rows:
        if required: raise ValueError("missing matrix")
        return []
    if len(rows)>4: raise ValueError("matrix exceeds four rows")
    width=len(rows[0].entries)
    if not 1<=width<=4 or any(len(r.entries)!=width for r in rows):
        raise ValueError("matrix not rectangular/bounded")
    return [[_number(value) for value in row.entries] for row in rows]

def _mat_result(rows=None,scalar=""):
    reply=pb.LinearResult(scalar=scalar,
                          limitations=["exact_rational_arithmetic",
                                       "intent_not_verified","units_unspecified"])
    for row in rows or ():
        reply.rows.add(entries=[str(_bound(x)) for x in row])
    return reply

def _linear(req):
    if req.action not in ("determinant","multiply","solve"):
        raise ValueError("unknown linear algebra action")
    a=_mat(req.a,required=True)
    b=_mat(req.b)
    n=len(a)
    m=len(a[0])
    if req.action=="multiply":
        if not b or m!=len(b): raise ValueError("matrix dimensions incompatible")
        cols=len(b[0])
        return _mat_result([[_bound(sum((a[i][k]*b[k][j] for k in range(m)),
                                       Fraction(0))) for j in range(cols)] for i in range(n)])
    if n!=m: raise ValueError("square coefficient matrix required")
    if req.action=="determinant" and b: raise ValueError("second matrix unused")
    if req.action=="solve" and (len(b)!=n or len(b[0])!=1):
        raise ValueError("solve requires n by 1 right-hand vector")
    if req.action=="determinant":
        mat=[row[:] for row in a]
        det=Fraction(1)
        for i in range(n):
            pivot=next((r for r in range(i,n) if mat[r][i]),None)
            if pivot is None: return _mat_result(scalar="0")
            if pivot!=i:
                mat[i],mat[pivot]=mat[pivot],mat[i]
                det=-det
            pivot_val=mat[i][i]
            det=_bound(det*pivot_val)
            for r in range(i+1,n):
                factor=mat[r][i]/pivot_val
                for c in range(i+1,n):
                    mat[r][c]=_bound(mat[r][c]-factor*mat[i][c])
                mat[r][i]=Fraction(0)
        return _mat_result(scalar=str(det))
    augmented=[a[i][:]+b[i][:] for i in range(n)]
    for i in range(n):
        pivot=next((r for r in range(i,n) if augmented[r][i]),None)
        if pivot is None: raise ValueError("singular matrix")
        augmented[i],augmented[pivot]=augmented[pivot],augmented[i]
        divisor=augmented[i][i]
        augmented[i]=[_bound(v/divisor) for v in augmented[i]]
        for j in range(n):
            if j==i: continue
            factor=augmented[j][i]
            augmented[j]=[_bound(v-factor*w) for v,w in zip(augmented[j],augmented[i])]
    return _mat_result([[augmented[i][-1]] for i in range(n)])

def _root(req):
    if not 1<=req.iterations<=128: raise ValueError("bounded iterations required")
    poly=_polynomial(req.polynomial)
    lo=_number(req.lower)
    hi=_number(req.upper)
    if lo>=hi: raise ValueError("strictly ordered bracket required")
    f_lo=_eval_poly(poly,lo)
    f_hi=_eval_poly(poly,hi)
    if not f_lo:
        hi=lo
    elif not f_hi:
        lo=hi
    elif (f_lo>0)==(f_hi>0):
        raise ValueError("root not bracketed")
    else:
        for _ in range(req.iterations):
            mid=_bound((lo+hi)/2,1024)
            f_mid=_eval_poly(poly,mid)
            if not f_mid: lo=hi=mid;break
            if (f_lo>0)==(f_mid>0):
                lo,f_lo=mid,f_mid
            else:
                hi=mid
    return pb.RootResult(lower=str(lo),upper=str(hi),
                         midpoint=str(_bound((lo+hi)/2,1024)),
                         limitations=["polynomial_bracket_only",
                                      "interval_contains_root_by_continuity",
                                      "not_general_equation_solver",
                                      "intent_not_verified"])

def _simulation(req):
    if not 1<=req.steps<=256: raise ValueError("simulation step cap")
    x=_number(req.position);v=_number(req.velocity)
    k=_number(req.omega_squared);dt=_number(req.step)
    if k<0 or k>100 or dt<=0 or dt>1 or k*dt*dt>Fraction(1,4):
        raise ValueError("unstable/invalid harmonic oscillator settings")
    def energy(x,v): return _bound((v*v+k*x*x)/2,1024)
    e0=energy(x,v)
    for _ in range(req.steps):
        v=_bound(v-k*x*dt,1024)
        x=_bound(x+v*dt,1024)
    return pb.SimulationResult(
        position=str(x),velocity=str(v),
        initial_energy=str(e0),final_energy=str(energy(x,v)),
        limitations=["symplectic_euler_discrete_model",
                     "numerical_discretization_error_unbounded",
                     "units_and_physical_assumptions_unverified",
                     "intent_not_verified"])

_DISPATCH={"symbolic":_symbolic,"scientific":_scientific,
           "precision":_precision,"linear":_linear,
           "root":_root,"simulation":_simulation}
def run_inert_specialist(kind,request_frame):
    """Trusted in-process reference *only*, not an approved Lu worker call."""
    if kind not in _REQUESTS: raise ValueError("unknown specialist operation")
    request_cls,response_cls=_REQUESTS[kind]
    request=_frame(request_frame,request_cls)
    response=_DISPATCH[kind](request)
    if not isinstance(response,response_cls):
        raise ValueError("incorrect typed specialist response")
    return _wire(response)

def decode_specialist_result(kind,response_frame):
    """Revalidate wire shape. Model interpretation and host trust are separate."""
    if kind not in _REQUESTS: raise ValueError("unknown specialist response type")
    return _frame(response_frame,_REQUESTS[kind][1])
