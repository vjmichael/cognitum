"""Genuine research HDC + represented KAN + SSM integration, strictly offline.

An HDC similarity match is a candidate, KAN values describe a checkpoint's
represented function (not a verified physical field), and SSM predictions
are numerical hypotheses, not autonomous actions or proof of a discovery.
"""
import numpy as np
from .ssm_stochastic import need, array, cov, receipt
from .ssm_interop import digest, hashid, wire, read, ident, evidence, kan_evolve, kan_eval, kan_observe
from .ssm_research_validation import validate_data


def scientific_model(vector_fields, observation_field, *, step_seconds, state_units, dataset_manifest_sha256, source_sha256):
    need(type(vector_fields) in (list,tuple) and len(vector_fields)==2 and type(observation_field) is bytes and 0<len(observation_field)<=40960 and all(type(c) is bytes and 0<len(c)<=40960 for c in vector_fields),'checkpoint bound')
    need(type(step_seconds) in (int,float) and 0<step_seconds<=.25 and type(state_units) in (list,tuple) and len(state_units)==2,'scientific model')
    return wire(dict(version=1,kind='represented-kan-vector-field',dynamics_sha256=[digest(c) for c in vector_fields],observation_sha256=digest(observation_field),step_seconds=float(step_seconds),state_units=[ident(s) for s in state_units],dataset_manifest_sha256=hashid(dataset_manifest_sha256),source_sha256=hashid(source_sha256),domain='normalized-unit-square',execution_authorized=False))


def load_scientific_model(raw):
    m=read(raw)
    need(set(m)=={'version','kind','dynamics_sha256','observation_sha256','step_seconds','state_units','dataset_manifest_sha256','source_sha256','domain','execution_authorized'} and m['version']==1 and m['kind']=='represented-kan-vector-field' and m['execution_authorized'] is False and m['domain']=='normalized-unit-square','scientific model schema')
    need(type(m['dynamics_sha256']) is list and len(m['dynamics_sha256'])==2 and all(hashid(s)==s for s in m['dynamics_sha256']) and hashid(m['observation_sha256'])==m['observation_sha256'] and hashid(m['dataset_manifest_sha256'])==m['dataset_manifest_sha256'] and hashid(m['source_sha256'])==m['source_sha256'] and type(m['state_units']) is list and len(m['state_units'])==2 and all(ident(u)==u for u in m['state_units']) and type(m['step_seconds']) in (float,int) and 0<m['step_seconds']<=.25,'scientific model fields')
    need(wire(m)==raw,'noncanonical scientific model')
    return m


def scientific_state(model_raw,values,step=0,stream='science-1'):
    load_scientific_model(model_raw);x=array(values,1)
    need(x.shape==(2,) and np.all((x>=0)&(x<=1)) and type(step) is int and 0<=step<=2**31-1,'scientific state shape/domain')
    return wire(dict(version=1,kind='scientific-state',model_sha256=digest(model_raw),values=x.tolist(),step=step,stream=ident(stream),execution_authorized=False))


def load_scientific_state(model_raw,state_raw):
    z=read(state_raw)
    need(set(z)=={'version','kind','model_sha256','values','step','stream','execution_authorized'} and z['version']==1 and z['kind']=='scientific-state' and z['execution_authorized'] is False and z['model_sha256']==digest(model_raw),'scientific state/model mismatch')
    need(scientific_state(model_raw,z['values'],z['step'],z['stream'])==state_raw,'noncanonical scientific state')
    return z


def hdc_candidates(model_raw,records,query,*,not_after_step,minimum=.3,margin=.05):
    """Use the existing research Spec('MAP') + Cleanup engine, not a reimplementation."""
    from cognitum.research.hdc_algebra import Spec
    from cognitum.research.hdc_associative import Cleanup
    load_scientific_model(model_raw)
    q=np.asarray(query)
    need(q.ndim==1 and 16<=len(q)<=4096 and q.dtype==np.int8 and np.all((q==1)|(q==-1)) and type(records) in (tuple,list) and 2<=len(records)<=128 and type(not_after_step) is int and not_after_step>=0,'HDC profile')
    eligible=[];vectors=[];seen=set()
    for raw,h,label in records:
        s=load_scientific_state(model_raw,raw);key=digest(raw)
        need(key not in seen,'duplicate scientific state');seen.add(key)
        v=np.asarray(h)
        need(v.dtype==np.int8 and v.shape==q.shape and np.all((v==1)|(v==-1)),'HDC row type');ident(label)
        if s['step']<=not_after_step:
            vectors.append(v.astype(np.float32));eligible.append(dict(state_sha256=key,step=s['step'],stream=s['stream'],regime=label))
    if len(eligible)<2:return receipt(candidate=None,abstained=True,candidate_only=True,matched_engine='hdc_associative.Cleanup')
    spec=Spec('MAP',len(q));bank=Cleanup(spec,np.stack(vectors));candidate=bank.propose(q.astype(np.float32),minimum=minimum,margin=margin)
    if candidate is None:return receipt(candidate=None,abstained=True,candidate_only=True,matched_engine='hdc_associative.Cleanup')
    row=eligible[candidate.index].copy();row['cosine_similarity']=float(candidate.score);row['margin']=float(candidate.margin)
    # Independent integer bipolar dot check; the runtime supplies the actual ranking/abstention.
    exact=float(np.dot(q.astype(np.int64),np.asarray(vectors[candidate.index],dtype=np.int64))/len(q))
    need(abs(exact-candidate.score)<=1e-6,'HDC/reference mismatch')
    return receipt(candidate=row,abstained=False,candidate_only=True,matched_engine='hdc_associative.Cleanup')


def investigate(model_raw,state_raw,vector_fields,observation_field,records,query,*,expected_state_sha256,not_after_step,steps,heldout_observation,measurement_variance,model_variance,dataset_raw,manifest_raw,prior_covariance):
    """Reproducible hypothesis evaluation; creates a candidate, never admits it as fact.

    Dataset and KAN checkpoint digests must match the supplied scientific model.
    The held-out observation is external to fitting; the caller owns provenance.
    """
    m=load_scientific_model(model_raw);s=load_scientific_state(model_raw,state_raw)
    need(digest(state_raw)==hashid(expected_state_sha256) and s['step']==not_after_step and type(steps) is int and 1<=steps<=16 and s['step']+steps<=2**31-1,'stale experiment state')
    need([digest(c) for c in vector_fields]==m['dynamics_sha256'] and digest(observation_field)==m['observation_sha256'],'KAN checkpoint mismatch')
    dataset=validate_data(dataset_raw,manifest_raw)
    need(digest(manifest_raw)==m['dataset_manifest_sha256'] and digest(dataset_raw)==m['source_sha256'],'dataset provenance mismatch')
    need(type(heldout_observation) in (int,float) and np.isfinite(heldout_observation) and abs(heldout_observation)<=1e6,'heldout observation')
    P=cov(prior_covariance,2)
    past=hdc_candidates(model_raw,records,query,not_after_step=s['step'])
    trajectory=kan_evolve(vector_fields,s['values'],m['step_seconds'],steps)
    x=trajectory['states'][-1];v=kan_eval(observation_field,x)
    post=kan_observe(observation_field,x,P,heldout_observation,measurement_variance,model_variance)
    next_raw=scientific_state(model_raw,post['mean'],s['step']+steps,s['stream'])
    trace=wire(dict(version=1,kind='scientific-hypothesis-trace',model_sha256=digest(model_raw),state_sha256=digest(state_raw),dataset_sha256=digest(dataset_raw),start_step=s['step'],end_step=s['step']+steps,trajectory=trajectory['states'].tolist(),predicted_observation=float(v['value']),heldout_observation=float(heldout_observation),absolute_error=float(abs(heldout_observation-v['value'])),hdc_candidate_state_sha256=past['candidate']['state_sha256'] if past['candidate'] else None,post_state_sha256=digest(next_raw),unverified=True,execution_authorized=False))
    ev=evidence('numerical-residual',digest(model_raw),['heldout-observation','normalized-domain','local-ekf','model-variance-assumed'],digest(trace),f'abs_error={abs(heldout_observation-v["value"]):.12g}')
    return receipt(next_state=next_raw,trace=trace,evidence=ev,hdc=past,posterior_covariance=post['covariance'],checkpoint_hashes=tuple(m['dynamics_sha256']+[m['observation_sha256']]),dataset_rows=len(dataset),verified_scientific_claim=False)
