"""Bounded exact tensor scientific exchange. Research-only; no MEL admission.
A separate typed protobuf profile, preserving original J/K/L checkpoint bytes.
The solution certificate is recomputed, never trusted from transport metadata.
"""
from dataclasses import asdict, is_dataclass
from fractions import Fraction as Q
from itertools import product
from math import prod, isfinite
import hashlib, json, base64, re
from google.protobuf.message import DecodeError
from . import tensor_field_pb2 as pb
from cognitum.research import kan_elliptic_certificate as j, kan_transient_certificate as k, kan_spacetime_certificate as l

MAX_FRAME=40960 # existing MEL native object budget
MAX_REQUEST=4096
MAX_RESULT=6144 # existing MEL native result budget
MAX_PROBLEM=32768
MAX_CERT=32768
MAX_POINTS=3
BASIS='clamped-cubic-bspline-v1'
LAYOUT='row-major-last-axis-fastest'
ARITHMETIC='represented-binary64-exact-rational'
PROFILES={pb.ELLIPTIC_XY:(j,('x','y')),pb.PARABOLIC_XT:(k,('x','t')),pb.PARABOLIC_XYT:(l,('x','y','t'))}
ID=re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}\Z')
need=j.need

def digest(b):return hashlib.sha256(b).digest()
def wire(m):return m.SerializeToString(deterministic=True)
DESCRIPTOR=digest(pb.DESCRIPTOR.serialized_pb)

def parse(raw,cls,limit):
    need(type(raw) is bytes and 0<len(raw)<=limit,'bounded wire frame')
    try:m=cls.FromString(raw)
    except (DecodeError,ValueError,RecursionError) as e:raise ValueError('invalid protobuf') from e
    m.DiscardUnknownFields()
    need(wire(m)==raw,'noncanonical or unknown protobuf fields')
    return m

def carrier(raw):
    need(type(raw) is bytes and 0<len(raw)<=MAX_FRAME,'carrier size')
    return base64.b64encode(raw).decode('ascii')

def uncarrier(s):
    need(type(s) is str and 0<len(s)<=4*((MAX_FRAME+2)//3),'carrier size')
    try:raw=base64.b64decode(s,validate=True)
    except (ValueError,UnicodeError) as e:raise ValueError('invalid carrier') from e
    need(carrier(raw)==s,'noncanonical carrier');return raw

def canonical(value):
    def transform(x):
        if isinstance(x,Q):return str(x)
        if is_dataclass(x):return transform(asdict(x))
        if type(x) is dict:return {a:transform(b) for a,b in x.items()}
        if type(x) in (tuple,list):return [transform(a) for a in x]
        return x
    return json.dumps(transform(value),sort_keys=True,separators=(',',':'),allow_nan=False).encode('ascii')

def _problem(module,raw):
    need(type(raw) is bytes and 0<len(raw)<=MAX_PROBLEM,'problem size')
    try:
        d=json.loads(raw)
        need(type(d) is dict,'problem object')
        expected=({'ax','ay','reaction','forcing'} if module is j else
                  {'diffusion','reaction','forcing','initial'} if module is k else
                  {'ax','ay','reaction','forcing','initial'})
        need(set(d)==expected,'problem schema')
        need(type(d['forcing']) is list and all(type(t) is list for t in d['forcing']),'forcing schema')
        d['forcing']=tuple(map(tuple,d['forcing']))
        if module is k:
            need(type(d['initial']) is list,'initial shape');d['initial']=tuple(d['initial'])
        if module is l:
            need(type(d['initial']) is list and all(type(t) is list for t in d['initial']),'initial shape');d['initial']=tuple(map(tuple,d['initial']))
        p=module.Problem(**d)
        need(canonical(p)==raw,'noncanonical problem');return p
    except (TypeError,KeyError,OverflowError,RecursionError,UnicodeError) as e:raise ValueError('invalid problem') from e

def _tensor(module,m):
    if module is k:m=m.spline
    return (m.cuts if module is l else (m.xcuts,m.ycuts)),m.shape,m.coefficients

def _axes(msg,module,m,names):
    cuts,shape,_=_tensor(module,m)
    for a,c,n in zip(names,cuts,shape):msg.axes.add(name=a,unit='1',basis_count=n,interior_knots=c)

def export(problem,model,certificate):
    profile=next((i for i,(mod,_) in PROFILES.items() if type(problem) is mod.Problem and type(model) is mod.Model),None)
    need(profile is not None,'unsupported typed profile')
    mod,names=PROFILES[profile];mod.replay(problem,model,certificate)
    need(certificate.solution_error_upper is not None,'uncertified conditions')
    raw=canonical(certificate);pr=canonical(problem);mr=model.checkpoint()
    need(len(raw)<=MAX_CERT and len(pr)<=MAX_PROBLEM,'evidence budget')
    msg=pb.Checkpoint(schema_version=1,profile=profile,basis=BASIS,layout=LAYOUT,arithmetic=ARITHMETIC,model_json=mr,problem_json=pr,certificate_json=raw,model_sha256=digest(mr),problem_identity=bytes.fromhex(problem.identity),certificate_sha256=digest(raw))
    _axes(msg,mod,model,names)
    data=wire(msg);need(len(data)<=MAX_FRAME,'checkpoint frame budget');return data

def restore(raw):
    msg=parse(raw,pb.Checkpoint,MAX_FRAME)
    need(msg.schema_version==1 and msg.profile in PROFILES and msg.basis==BASIS and msg.layout==LAYOUT and msg.arithmetic==ARITHMETIC,'tensor profile')
    mod,names=PROFILES[msg.profile]
    need(len(msg.axes)==len(names) and len(msg.certificate_json)<=MAX_CERT,'rank/evidence budget')
    need(msg.model_sha256==digest(msg.model_json) and msg.certificate_sha256==digest(msg.certificate_json),'payload digest mismatch')
    p=_problem(mod,msg.problem_json)
    need(msg.problem_identity==bytes.fromhex(p.identity),'problem identity mismatch')
    try:m=mod.restore(msg.model_json)
    except (TypeError,KeyError,OverflowError,RecursionError,UnicodeError) as e:raise ValueError('invalid checkpoint') from e
    expected=pb.Checkpoint();_axes(expected,mod,m,names)
    need(list(msg.axes)==list(expected.axes),'axis metadata mismatch')
    cert=mod.assess(p,m)
    need(cert.solution_error_upper is not None and canonical(cert)==msg.certificate_json,'certificate replay mismatch')
    return mod,p,m,cert

def _coordinate(x):
    need(type(x) in (int,float) and 0<=x<=1 and isfinite(x) and (x==0 or x>=2**-128),'coordinate outside bounded normalized domain');return Q(x)

def _local(poly,order,h):
    return tuple(poly[i]*prod(range(i-order+1,i+1))/h**order for i in range(order,len(poly)))

def _basis_values(cuts,x,order):
    segments=j._basis(cuts)
    lo,hi,polys=next(s for s in segments if s[0]<=x<s[1] or x==s[1]==1)
    u=(x-lo)/(hi-lo)
    return tuple(sum((a*u**i for i,a in enumerate(_local(p,order,hi-lo))),Q(0)) for p in polys)

def _basis_integrals(cuts,lo,hi):
    result=[Q(0)]*(len(cuts)+4)
    for a,b,polys in j._basis(cuts):
        left,right=max(lo,a),min(hi,b)
        if left>=right:continue
        u,v=(left-a)/(b-a),(right-a)/(b-a)
        for i,p in enumerate(polys):result[i]+=(b-a)*sum((c*(v**(n+1)-u**(n+1))/(n+1) for n,c in enumerate(p)),Q(0))
    return tuple(result)

def _initial(mod,p):
    if mod is j:return ()
    if mod is k:return tuple((i,0,c) for i,c in enumerate(p.initial))
    return tuple((i,jj,0,c) for i,jj,c in p.initial)

def _power_point(n,x,d):return Q(0) if n<d else Q(prod(range(n-d+1,n+1)))*x**(n-d)
def _power_integral(n,a,b):return (b**(n+1)-a**(n+1))/(n+1)

def _contract(coeff,shape,weights):
    return sum((Q(c)*prod(weights[a][i] for a,i in enumerate(idx)) for idx,c in zip(product(*(range(n) for n in shape)),coeff)),Q(0))

def _validate_request(raw,checkpoint):
    q=parse(raw,pb.Request,MAX_REQUEST)
    need(q.schema_version==1 and q.descriptor_sha256==DESCRIPTOR and q.checkpoint_sha256==digest(checkpoint),'request binding')
    need(ID.fullmatch(q.request_id) and ID.fullmatch(q.correlation_id),'request identity')
    return q

def make_request(checkpoint,operation,lower,*,upper=(),derivative=(),request_id='field-1',correlation_id='turn-1'):
    need(type(operation) is int and operation in (pb.POINT,pb.BOX_INTEGRAL),'operation')
    need(type(checkpoint) is bytes and 0<len(checkpoint)<=MAX_FRAME,'checkpoint bound')
    need(type(lower) is tuple and type(upper) is tuple and type(derivative) is tuple,'typed coordinates')
    need(1<=len(lower)<=MAX_POINTS and len(upper)<=MAX_POINTS and len(derivative)<=MAX_POINTS,'coordinate budget')
    for x in (*lower,*upper):_coordinate(x)
    need(all(type(d) is int and 0<=d<=2 for d in derivative),'derivative order')
    need(type(request_id) is str and type(correlation_id) is str and ID.fullmatch(request_id) and ID.fullmatch(correlation_id),'request identity')
    return wire(pb.Request(schema_version=1,request_id=request_id,correlation_id=correlation_id,checkpoint_sha256=digest(checkpoint),descriptor_sha256=DESCRIPTOR,operation=operation,lower=lower,upper=upper,derivative=derivative))

def execute(checkpoint,request):
    need(type(checkpoint) is bytes and 0<len(checkpoint)<=MAX_FRAME,'checkpoint bound')
    q=_validate_request(request,checkpoint);mod,p,m,cert=restore(checkpoint)
    cuts,shape,coef=_tensor(mod,m);rank=len(shape)
    need(len(q.lower)==rank,'point rank');a=tuple(map(_coordinate,q.lower))
    if q.operation==pb.POINT:
        d=tuple(q.derivative);need(not q.upper and len(d)==rank and sum(d)<=2,'point derivative profile')
        weights=tuple(_basis_values(c,x,o) for c,x,o in zip(cuts,a,d))
        lift=sum((Q(term[-1])*prod(_power_point(n,x,o) for n,x,o in zip(term[:-1],a,d)) for term in _initial(mod,p)),Q(0))
        bound=cert.solution_error_upper if not any(d) else None
    elif q.operation==pb.BOX_INTEGRAL:
        need(len(q.upper)==rank and not q.derivative,'box integral profile');b=tuple(map(_coordinate,q.upper));need(all(x<y for x,y in zip(a,b)),'positive box volume')
        weights=tuple(_basis_integrals(c,x,y) for c,x,y in zip(cuts,a,b))
        lift=sum((Q(term[-1])*prod(_power_integral(n,x,y) for n,x,y in zip(term[:-1],a,b)) for term in _initial(mod,p)),Q(0))
        bound=cert.solution_error_upper*prod(y-x for x,y in zip(a,b))
    else:raise ValueError('unsupported operation')
    value=_contract(coef,shape,weights)+lift
    r=pb.Result(schema_version=1,request_sha256=digest(request),checkpoint_sha256=digest(checkpoint),exact_value=str(value),pde_target_error_upper='' if bound is None else str(bound),assurance='represented-function-exact',request_id=q.request_id,correlation_id=q.correlation_id,descriptor_sha256=DESCRIPTOR)
    raw=wire(r);need(len(raw)<=MAX_RESULT,'result budget');return raw

def replay(checkpoint,request,result):
    parse(result,pb.Result,MAX_RESULT)
    need(execute(checkpoint,request)==result,'result replay mismatch');return True

def descriptor():
    return dict(schema='cognitum.mel.tensor_field.descriptor.v1',protobuf_descriptor_sha256=DESCRIPTOR.hex(),native_proto_type_urls=['type.googleapis.com/'+m.DESCRIPTOR.full_name for m in (pb.Checkpoint,pb.Request,pb.Result)],profile='bounded_scientific_tensor_v1',max_checkpoint_bytes=MAX_FRAME,max_request_bytes=MAX_REQUEST,max_result_bytes=MAX_RESULT,track='research',effects=[],model_advertised=False,lu_registered=False,execution_authorized=False)
