"""MEL v1 canonical, content-addressed binary64 objects. Hashes are not grants."""
import base64
import hashlib
import json
import math
import re
import struct
from dataclasses import dataclass

SCHEMA = 'cognitum.mel.object.v1'
MAX_WIRE = 65536
MAX_DIM = 8
MAX_TERMS = 256
MAX_POINTS = 32
PRODUCER = 'cognitum.mel.vfa/1.0.0'
KERNEL = '6e498ac907de910ac00a29a1befefa59fdc1cda4'
TOKEN = re.compile(r'(?:[A-Za-z][A-Za-z0-9_]{0,23}|1)\Z', re.ASCII)
HEX = re.compile(r'[0-9a-f]{64}\Z', re.ASCII)
FIELDS = {'schema','kind','representation','shape','axes','box','units','parents','producer','kernel','assurance','error','payload'}
KINDS = {'function':'diagonal_gaussian_mixture','points':'coordinate_batch','values':'scalar_batch','gradient':'gradient_batch'}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def number(v, limit=1e6):
    need(type(v) in (int,float) and -limit <= v <= limit, 'numeric range or type')
    return float(v)


def token(v):
    return type(v) is str and TOKEN.fullmatch(v) is not None


def parse_hex(v):
    need(type(v) is str and len(v)<=24, 'binary64 bound encoding')
    try:
        f=float.fromhex(v)
    except (ValueError,OverflowError) as e:
        raise ValueError('binary64 bound encoding') from e
    f=number(f)
    need(f.hex()==v, 'noncanonical binary64 bound')
    return f


def seq(v,n):
    return type(v) is list and len(v)==n


def payload(values):
    return base64.b64encode(struct.pack('<'+'d'*len(values),*values)).decode('ascii')


def decode_payload(s,n,limit):
    need(type(s) is str and len(s)==4*((8*n+2)//3), 'payload length')
    try:
        b=base64.b64decode(s,validate=True)
    except (ValueError,TypeError) as e:
        raise ValueError('invalid payload') from e
    need(len(b)==8*n and base64.b64encode(b).decode('ascii')==s,'noncanonical payload')
    v=struct.unpack('<'+'d'*n,b)
    need(all(math.isfinite(x) and abs(x)<=limit for x in v),'payload value range')
    return v


def inspect(wire):
    need(type(wire) is str and 1<=len(wire)<=MAX_WIRE and wire.isascii(),'wire budget')
    try:
        envelope=json.loads(wire)
        need(type(envelope) is dict and set(envelope)=={'id','body'},'envelope fields')
        body=envelope['body'];identity=envelope['id']
        need(type(body) is dict and set(body)==FIELDS,'body fields')
        need(canonical(envelope)==wire,'noncanonical object')
        need(type(identity) is str and HEX.fullmatch(identity) and hashlib.sha256(canonical(body).encode('ascii')).hexdigest()==identity,'digest mismatch')
    except (TypeError,RecursionError,OverflowError) as e:
        raise ValueError('invalid object encoding') from e
    kind=body['kind']
    need(type(kind) is str and kind in KINDS and body['schema']==SCHEMA and body['representation']==KINDS[kind],'unknown representation')
    axes=body['axes']; box=body['box']; units=body['units']; shape=body['shape']; parents=body['parents']
    need(type(axes) is list and 1<=len(axes)<=MAX_DIM and all(seq(a,2) and all(token(x) for x in a) for a in axes),'axes')
    d=len(axes)
    need(len({a[0] for a in axes})==d and seq(box,d),'axis identity or domain')
    bounds=[]
    for b in box:
        need(seq(b,2),'domain shape');lo,hi=(parse_hex(v) for v in b)
        need(lo<hi,'domain ordering');bounds.append((lo,hi))
    need(type(shape) is list and all(type(x) is int for x in shape),'shape')
    need(type(units) is list and all(seq(u,2) and all(token(v) for v in u) for u in units),'unit descriptors')
    if kind=='function':
        need(len(shape)==2 and shape[1]==d and 0<=shape[0]<=MAX_TERMS,'function shape')
        need(seq(units,1) and units[0][1]=='1','function units')
        t=shape[0];v=decode_payload(body['payload'],1+t*(2*d+1),1e6)
        need(all(1e-3<=s<=1e3 for s in v[1+t*d:1+2*t*d]),'width range')
    else:
        need(len(shape)==(1 if kind=='values' else 2) and 1<=shape[0]<=MAX_POINTS,'batch shape')
        if kind!='values':need(shape[1]==d,'batch dimension')
        v=decode_payload(body['payload'],shape[0]*(1 if kind=='values' else d),1e6 if kind=='points' else 1e12)
        if kind=='points':
            need(units==[[a[1],'1'] for a in axes],'coordinate units')
            need(all(bounds[i%d][0]<=x<=bounds[i%d][1] for i,x in enumerate(v)),'outside domain')
        elif kind=='values':need(seq(units,1) and units[0][1]=='1','value units')
        else:need(seq(units,d) and len({u[0] for u in units})==1 and all(u[1]==a[1] for u,a in zip(units,axes)),'gradient units')
    if kind in ('function','points'):
        need(parents==[] and body['producer']=='submitted' and body['kernel']=='' and body['assurance']=='unverified_input' and body['error']=='unknown','input provenance')
    else:
        need(seq(parents,2) and all(type(p) is str and HEX.fullmatch(p) for p in parents) and body['producer']==PRODUCER and body['kernel']==KERNEL and body['assurance']=='numerical' and body['error']=='not_certified','result provenance')
    return identity,body,v


@dataclass(frozen=True,slots=True)
class MathObject:
    """Only immutable str retained. Decoded dictionaries are disposable copies."""
    wire: str

    def __post_init__(self):
        inspect(self.wire)

    @property
    def identity(self):return inspect(self.wire)[0]

    @property
    def metadata(self):
        b=inspect(self.wire)[1];del b['payload'];return b

    @property
    def values(self):return inspect(self.wire)[2]


def make(kind,shape,axes,box,units,values,parents=()):
    result=kind in ('values','gradient')
    b=dict(schema=SCHEMA,kind=kind,representation=KINDS[kind],shape=shape,axes=axes,box=box,units=units,parents=list(parents),producer=PRODUCER if result else 'submitted',kernel=KERNEL if result else '',assurance='numerical' if result else 'unverified_input',error='not_certified' if result else 'unknown',payload=payload(values))
    return MathObject(canonical(dict(id=hashlib.sha256(canonical(b).encode('ascii')).hexdigest(),body=b)))


def matrix(rows,n,d,limit=1e6):
    need(type(rows) in (list,tuple) and len(rows)==n,'row count')
    out=[]
    for r in rows:
        need(type(r) in (list,tuple) and len(r)==d,'row shape')
        out.extend(number(x,limit) for x in r)
    return out


def gaussian(centers,widths,weights,*,constant,axes,domain,output_unit):
    need(type(axes) in (list,tuple) and 1<=len(axes)<=MAX_DIM,'dimension')
    d=len(axes)
    need(type(weights) in (list,tuple) and len(weights)<=MAX_TERMS,'term budget')
    n=len(weights)
    need(type(domain) in (list,tuple) and len(domain)==d,'domain dimension')
    box=[]
    for row in domain:
        need(type(row) in (list,tuple) and len(row)==2,'domain shape')
        box.append([number(x).hex() for x in row])
    need(all(type(a) in (list,tuple) and len(a)==2 and all(token(v) for v in a) for a in axes) and token(output_unit),'unit/axis identity')
    v=[number(constant)]+matrix(centers,n,d)+matrix(widths,n,d)+[number(w) for w in weights]
    return make('function',[n,d],[list(a) for a in axes],box,[[output_unit,'1']],v)


def points(function,rows):
    need(type(function) is MathObject,'function object required')
    _,b,_=inspect(function.wire)
    need(b['kind']=='function' and type(rows) in (list,tuple) and 1<=len(rows)<=MAX_POINTS,'point budget or kind')
    d=len(b['axes']);n=len(rows)
    return make('points',[n,d],b['axes'],b['box'],[[a[1],'1'] for a in b['axes']],matrix(rows,n,d))


def pair(function,coordinates):
    need(type(function) is MathObject and type(coordinates) is MathObject,'typed inputs required')
    fi,f,fv=inspect(function.wire);pi,p,pv=inspect(coordinates.wire)
    need(f['kind']=='function' and p['kind']=='points' and f['axes']==p['axes'] and f['box']==p['box'],'incompatible coordinate representation')
    return fi,f,fv,pi,p,pv


def result_object(operation,function,coordinates,values):
    fi,f,_,pi,p,_=pair(function,coordinates);n,d=p['shape'];u=f['units'][0][0]
    need(operation in ('vfa.evaluate','vfa.gradient'),'operation')
    gradient=operation=='vfa.gradient'
    need(type(values) in (list,tuple) and len(values)==n*(d if gradient else 1),'result count')
    units=[[u,a[1]] for a in f['axes']] if gradient else [[u,'1']]
    return make('gradient' if gradient else 'values',[n,d] if gradient else [n],f['axes'],f['box'],units,[number(v,1e12) for v in values],(fi,pi))


def validate_result(operation,function,coordinates,result):
    need(type(result) is MathObject,'result object required')
    expected=result_object(operation,function,coordinates,result.values)
    need(expected.wire==result.wire,'result type or lineage mismatch')
    return result
