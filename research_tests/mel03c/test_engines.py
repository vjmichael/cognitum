from dataclasses import replace
import hashlib
import math
import numpy as np
import pytest
from cognitum.contracts import Request, HostContext
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.mel import engines as e, engines_pb2 as pb, admission as a
from cognitum.mel.native import serialize, encode_carrier


def v(bits,dimension=5):return pb.BinaryVector(dimension=dimension,bits=bytes([bits]))

def bind():return e.make_call('hdc.bind',pb.BindInput(left=v(5),right=v(19)),'request','turn')

def query():return e.make_call('hdc.query',pb.QueryInput(probe=v(5),candidates=[v(4),v(7),v(31)]),'request','turn')

def kan(basis=pb.RBF, degree=0, xs=(0.,1.), weights=None):
    layer=pb.KanLayer(inputs=1,outputs=1,knots=3,basis=basis,degree=degree,grid=[-1.,0.,1.],
                      coefficients=weights if weights is not None else [1.,2.,3.] if basis==pb.RBF else [2.] if degree==1 else [1.,3.],mask=[1.])
    return e.make_call('kan.evaluate',pb.KanInput(layers=[layer],rows=len(xs),coordinates=xs),'request','turn')

@pytest.fixture(scope='module')
def registry():
    r=Registry();r.install(e.EnginePlugin,enabled=True)
    for op in e.OPERATIONS:r.nominate(op,e.NAME)
    return r


def execute(reg,c,allow=True):
    m=c.message
    return Runtime(reg).call(Request(m.request_id,m.correlation_id,c.operation,c.payload(),workspace_id='ws',subject_id='user',operation_schema_version=e.VERSION,timeout_ms=8000),HostContext('ws','user',allow_research=allow))


def actual(reg,c):return pb.EngineResult.FromString(e.checked_result(c,execute(reg,c)))


def test_worker_binding(registry):
    r=actual(registry,bind());assert r.bound==v(22) and r.assurance=='exact_arithmetic'


def test_worker_query_all_ties(registry):
    r=actual(registry,query());assert list(r.query.hamming_distance)==[1,1,3];assert list(r.query.best_index)==[0,1]


def test_worker_rbf(registry):
    r=actual(registry,kan());expected=[sum(w*math.exp(-(x-g)**2) for w,g in zip([1,2,3],[-1,0,1])) for x in (0,1)]
    assert r.assurance=='numerical';np.testing.assert_allclose(r.kan.values,expected,rtol=1e-6,atol=1e-6)


def test_worker_bspline(registry):
    r=actual(registry,kan(pb.BSPLINE,1,(-.5,0.,.5,1.)));np.testing.assert_allclose(r.kan.values,[1,2,1,0],atol=5e-7,rtol=0)


def test_bound_dimension_max(registry):
    b=pb.BinaryVector(dimension=4096,bits=b'\xaa'*512);z=pb.BinaryVector(dimension=4096,bits=b'\x55'*512)
    c=e.make_call('hdc.bind',pb.BindInput(left=b,right=z),'max','turn');assert actual(registry,c).bound.bits==b'\xff'*512


def test_query_max(registry):
    b=pb.BinaryVector(dimension=4096,bits=b'\xaa'*512);c=e.make_call('hdc.query',pb.QueryInput(probe=b,candidates=[b]*16),'max','turn')
    out=actual(registry,c).query;assert list(out.hamming_distance)==[0]*16 and list(out.best_index)==list(range(16))


def test_research_default_off(registry):
    for c in (bind(),query(),kan()):assert execute(registry,c,False).execution_status=='unavailable'


def test_discovery_is_inert_and_exact(registry):
    sel=tuple((op,e.descriptor(op)[0]) for op in e.OPERATIONS)
    assert e.discover(registry,())==()
    for h,d in e.discover(registry,sel):assert h==e.descriptor(d['operation'])[0] and not d['execution_authorized'] and not d['model_advertised']
    for bad in (sel+sel[:1],(('hdc.bind','0'*64),), (('unknown','0'*64),)):
        with pytest.raises(ValueError):e.discover(registry,bad)
    with pytest.raises(ValueError):e.discover(Registry(),sel)


def test_vfa_only_admission_not_widened(registry):
    assert all(r.operation not in e.OPERATIONS for r in a.routes())
    h=a.Admission(Runtime(registry),'session');s=a.Scope('session','ws','user','turn');d=e.descriptor('hdc.bind')[0]
    route=a.Route('mel_hdc_bind','hdc.bind',d,a.Effect.COMPUTE_ONLY,*e.TYPE_URLS,e.VERSION)
    with pytest.raises(ValueError):h.issue(s,route)


@pytest.mark.parametrize('case',['padding','dimension','size','mismatch','missing','unknown','duplicate','descriptor','wrong_kind','oversize'])
def test_invalid_bind(case):
    c=bind();m=c.message
    if case=='padding':m.bind.left.bits=b'\x85'
    elif case=='dimension':m.bind.left.dimension=0
    elif case=='size':m.bind.left.bits=b'\x01\x00'
    elif case=='mismatch':m.bind.left.dimension=6
    elif case=='missing':m.bind.ClearField('right')
    elif case=='descriptor':m.descriptor_sha256=b'\x00'*32
    raw=serialize(m)
    if case=='unknown':raw+=b'\x98\x06\x01'
    elif case=='duplicate':raw+=b'\x08\x01'
    elif case=='wrong_kind':raw=query().wire
    elif case=='oversize':raw=b'x'*(e.MAX_REQUEST+1)
    with pytest.raises(ValueError):e.Call('hdc.bind',raw)


@pytest.mark.parametrize('case',['empty','oversize','dimension'])
def test_invalid_query(case):
    m=query().message
    if case=='empty':m.query.ClearField('candidates')
    elif case=='oversize':m.query.candidates.extend([v(1)]*16)
    else:m.query.candidates[0].dimension=6
    with pytest.raises(ValueError):e.Call('hdc.query',serialize(m))


@pytest.mark.parametrize('case',['width','nan','mask','grid','degree','domain','weights','rows','basis','layer_chain','zero_coeff','coords'])
def test_invalid_kan(case):
    m=kan().message;l=m.kan.layers[0]
    if case=='width':l.inputs=9
    elif case=='nan':l.coefficients[0]=float('nan')
    elif case=='mask':l.mask[0]=.5
    elif case=='grid':l.grid[1]=l.grid[0]
    elif case=='degree':l.degree=1
    elif case=='domain':m.kan.coordinates[0]=2
    elif case=='weights':l.coefficients[0]=1e10
    elif case=='rows':m.kan.rows=17
    elif case=='basis':l.basis=0
    elif case=='layer_chain':m.kan.layers.add().CopyFrom(l);m.kan.layers[1].inputs=2
    elif case=='zero_coeff':l.ClearField('coefficients')
    else:m.kan.coordinates.append(0.)
    with pytest.raises(ValueError):e.Call('kan.evaluate',serialize(m))


def test_intermediate_domain_refuses(registry):
    m=kan(weights=[100,100,100]).message;m.kan.layers.add().CopyFrom(kan().message.kan.layers[0]);c=e.Call('kan.evaluate',serialize(m))
    r=execute(registry,c);assert r.execution_status=='invalid_input' and r.result is None


@pytest.mark.parametrize('case',['foreign_request','foreign_parent','wrong_value','bad_kind','wrong_assurance'])
def test_result_refusal(registry,case):
    c=bind();response=execute(registry,c);r=pb.EngineResult.FromString(e.checked_result(c,response))
    if case=='foreign_request':r.request_id='foreign'
    elif case=='foreign_parent':r.request_sha256=b'\x00'*32
    elif case=='wrong_value':r.bound.bits=b'\x00'
    elif case=='bad_kind':r.query.hamming_distance.append(1)
    else:r.assurance='numerical'
    with pytest.raises(ValueError):e.checked_result(c,replace(response,result={'frame':encode_carrier(serialize(r),e.MAX_RESULT)}))


def test_query_result_witness(registry):
    c=query();response=execute(registry,c);r=pb.EngineResult.FromString(e.checked_result(c,response));r.query.best_index[:]=[0]
    with pytest.raises(ValueError):e.checked_result(c,replace(response,result={'frame':encode_carrier(serialize(r),e.MAX_RESULT)}))


def test_kan_result_shape_and_lineage(registry):
    c=kan();response=execute(registry,c);r=pb.EngineResult.FromString(e.checked_result(c,response));r.kan.values[0]=float('nan')
    with pytest.raises(ValueError):e.checked_result(c,replace(response,result={'frame':encode_carrier(serialize(r),e.MAX_RESULT)}))


def test_call_snapshot():
    c=bind();m=c.message;m.bind.left.bits=b'\x00';assert c.message.bind.left.bits==b'\x05';assert hashlib.sha256(c.wire).digest()!=hashlib.sha256(serialize(m)).digest()
