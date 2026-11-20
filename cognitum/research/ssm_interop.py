"""Bounded research interoperability; digests identify bytes, not authority."""
import json
import hashlib
import re
from fractions import Fraction
import numpy as np
from .ssm_stochastic import need, array, cov, gaussian_update, receipt
from .ssm_learned import recurrence

ID=re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,95}\Z')
HASH=re.compile(r'[0-9a-f]{64}\Z')
KINDS=('exact-represented','numerical-residual','empirical','conditional-certificate')


def ident(s):
    need(type(s) is str and ID.fullmatch(s),'identifier');return s


def digest(raw):return hashlib.sha256(raw).hexdigest()


def hashid(s):
    need(type(s) is str and HASH.fullmatch(s),'digest');return s


def wire(obj):
    raw=json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False,ensure_ascii=True).encode('ascii');need(len(raw)<=65536,'wire budget');return raw


def read(raw):
    need(type(raw) is bytes and 0<len(raw)<=65536,'wire size')
    try:z=json.loads(raw)
    except (ValueError,UnicodeError,RecursionError) as e:raise ValueError('invalid JSON') from e
    need(type(z) is dict and wire(z)==raw,'noncanonical object');return z


def units(u,n):
    need(type(u) in (tuple,list) and len(u)==n,'unit shape');return [ident(v) for v in u]


def model(F,G,C,dt,state_units,input_units,output_units,source):
    F,G,C=(array(x,2) for x in (F,G,C));n=len(F);need(1<=n<=16 and F.shape==(n,n) and G.shape[0]==n and 1<=G.shape[1]<=16 and C.shape[1]==n and 1<=len(C)<=16 and type(dt) in (int,float) and 0<dt<=1,'model profile');return wire(dict(version=1,kind='discrete-lti',F=F.tolist(),G=G.tolist(),C=C.tolist(),step_seconds=float(dt),state_units=units(state_units,n),input_units=units(input_units,G.shape[1]),output_units=units(output_units,len(C)),source_sha256=hashid(source)))


def load_model(raw):
    z=read(raw);need(set(z)=={'version','kind','F','G','C','step_seconds','state_units','input_units','output_units','source_sha256'} and z['version']==1 and z['kind']=='discrete-lti','model schema');need(model(z['F'],z['G'],z['C'],z['step_seconds'],z['state_units'],z['input_units'],z['output_units'],z['source_sha256'])==raw,'model canonical profile');return z


def state(model_raw,values,step=0,stream='stream-1'):
    m=load_model(model_raw);v=array(values,1);need(len(v)==len(m['F']) and type(step) is int and 0<=step<=2**31-1,'state shape/step');return wire(dict(version=1,kind='state',model_sha256=digest(model_raw),stream=ident(stream),step=step,values=v.tolist()))


def load_state(model_raw,raw):
    z=read(raw);need(set(z)=={'version','kind','model_sha256','stream','step','values'} and z['version']==1 and z['kind']=='state' and z['model_sha256']==digest(model_raw),'state/model mismatch');need(state(model_raw,z['values'],z['step'],z['stream'])==raw,'state canonical profile');return z


def advance(model_raw,state_raw,inputs,expected_state_sha256,expected_step):
    m=load_model(model_raw);z=load_state(model_raw,state_raw);need(hashid(expected_state_sha256)==digest(state_raw) and type(expected_step) is int and expected_step==z['step'],'stale state');u=array(inputs,2);need(len(u)<=512 and u.shape[1]==len(m['input_units']) and z['step']+len(u)<=2**31-1,'chunk budget');a=recurrence(m['F'],m['G'],m['C'],u,z['values']);end=state(model_raw,a['final_state'],z['step']+len(u),z['stream']);tr=wire(dict(version=1,kind='trajectory',model_sha256=digest(model_raw),start_state_sha256=digest(state_raw),end_state_sha256=digest(end),stream=z['stream'],first_step=z['step']+1,states=a['states'].tolist(),outputs=a['outputs'].tolist()));return receipt(state=end,trajectory=tr)


def belief(model_raw,state_raw,covariance):
    z=load_state(model_raw,state_raw);P=cov(covariance,len(z['values']));return wire(dict(version=1,kind='gaussian-belief',model_sha256=digest(model_raw),state_sha256=digest(state_raw),covariance=P.tolist(),execution_authorized=False))


def control_proposal(model_raw,state_raw,inputs):
    m=load_model(model_raw);z=load_state(model_raw,state_raw);u=array(inputs,2);need(len(u)<=64 and u.shape[1]==len(m['input_units']),'control profile');return wire(dict(version=1,kind='control-proposal',model_sha256=digest(model_raw),state_sha256=digest(state_raw),first_step=z['step'],inputs=u.tolist(),execution_authorized=False))


def regime_retrieve(model_raw,records,query,not_after_step,limit=3):
    """Exact bipolar HDC similarity candidates, bound to immutable state bytes."""
    load_model(model_raw);q=np.asarray(query);need(q.ndim==1 and 16<=len(q)<=4096 and q.dtype.kind in 'iu' and np.all((q==-1)|(q==1)) and type(records) in (list,tuple) and 1<=len(records)<=256 and type(not_after_step) is int and 0<=not_after_step<=2**31-1 and type(limit) is int and 1<=limit<=16,'retrieval profile');out=[];seen=set()
    for raw,hv,label in records:
        s=load_state(model_raw,raw);k=digest(raw);need(k not in seen,'duplicate state');seen.add(k);v=np.asarray(hv);need(v.shape==q.shape and v.dtype.kind in 'iu' and np.all((v==-1)|(v==1)),'bipolar vector');ident(label)
        if s['step']<=not_after_step:out.append(dict(state_sha256=k,stream=s['stream'],step=s['step'],regime=label,dot=int(q.astype(np.int64)@v.astype(np.int64))))
    out.sort(key=lambda a:(-a['dot'],a['state_sha256']));return receipt(candidates=out[:limit],dimension=len(q),candidate_only=True)


def evidence(kind,subject,assumptions,artifact,metric):
    need(kind in KINDS and type(assumptions) in (tuple,list) and 1<=len(assumptions)<=16 and type(metric) is str and 1<=len(metric)<=512,'evidence profile');return wire(dict(version=1,kind='evidence',classification=kind,subject_sha256=hashid(subject),artifact_sha256=hashid(artifact),assumptions=[ident(a) for a in assumptions],metric=metric,verified=False,execution_authorized=False))


def kan_eval(checkpoint,x):
    """Evaluate represented two-dimensional KAN field and first derivatives."""
    from cognitum.mel import tensor_field as f
    x=array(x,1);need(x.shape==(2,) and np.all((x>=0)&(x<=1)),'KAN normalized domain');v=[]
    for d in ((0,0),(1,0),(0,1)):
        q=f.make_request(checkpoint,f.pb.POINT,tuple(float(a) for a in x),derivative=d);raw=f.execute(checkpoint,q);r=f.parse(raw,f.pb.Result,f.MAX_RESULT);v.append(float(Fraction(r.exact_value)))
    need(np.isfinite(v).all(),'KAN nonfinite');return receipt(value=v[0],gradient=np.array(v[1:]),checkpoint_sha256=digest(checkpoint),represented_function_only=True)


def kan_evolve(checkpoints,x0,dt,steps):
    need(type(checkpoints) in (tuple,list) and len(checkpoints)==2 and type(dt) in (int,float) and 0<dt<=.25 and type(steps) is int and 1<=steps<=16,'KAN integration budget');x=array(x0,1);need(x.shape==(2,),'KAN state shape');X=[x]
    def f(x):return np.array([kan_eval(c,x)['value'] for c in checkpoints])
    for _ in range(steps):
        a=f(x);b=f(x+dt*a/2);c=f(x+dt*b/2);d=f(x+dt*c);x=x+dt*(a+2*b+2*c+d)/6;need(np.all((x>=0)&(x<=1)),'KAN domain exit');X.append(x)
    return receipt(states=np.array(X),checkpoint_sha256=tuple(map(digest,checkpoints)),represented_function_only=True)


def kan_observe(checkpoint,mean,P,y,measurement_variance,model_variance):
    x=array(mean,1);need(x.shape==(2,) and type(model_variance) in (int,float) and np.isfinite(model_variance) and model_variance>=0 and type(measurement_variance) in (int,float) and measurement_variance>0,'observation variance');P=cov(P,2);z=kan_eval(checkpoint,x);H=z['gradient'][None,:];v=array([y],1);m,C,ll,nis=gaussian_update(x,P,H,[[measurement_variance+model_variance]],v-z['value']+H@x);need(np.all((m>=0)&(m<=1)),'posterior leaves KAN domain');return receipt(mean=m,covariance=C,log_likelihood=ll,nis=nis,checkpoint_sha256=z['checkpoint_sha256'],model_variance=float(model_variance),local_linearization=True)
