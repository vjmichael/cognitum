"""CPU-only COG-07 known-truth causal reference evidence.

All generated inputs are synthetic, not collected user data. No causal assumption
is inferred from a fitted model, and no discovery graph is automatically used as
an identifying DAG. Estimates are conditional on the declared model.
"""
from argparse import ArgumentParser
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from statistics import NormalDist
from time import perf_counter,process_time
import json,os,sys
import numpy as np

from cognitum.proto import causal_pb2 as pb
from cognitum.causal_specialists import run_causal_wire

EFFECT=("consistency","no_interference","conditional_exchangeability","positivity")
PC=("causal_markov","faithfulness","causal_sufficiency","iid_sampling")
OPS={"statsmodels":"ate_statsmodels","dowhy":"ate_dowhy",
     "econml":"conditional_effect_econml","causal-learn":"discover_pc"}

def effect_data(seed=731,n=1200,heterogeneous=False):
    rng=np.random.default_rng(seed)
    w=rng.uniform(-1,1,n);x=rng.uniform(-1,1,n)
    propensity=1/(1+np.exp(-2*w))
    t=(rng.random(n)<propensity).astype(float)
    y=(2.+1.2*x if heterogeneous else 2.5)*t+3*w+.45*x+rng.normal(0,.65,n)
    return np.column_stack((t,y,w,x))

def effect_request(op,data,profile=0.):
    q=pb.CausalRequest(schema_version=1,operation=op,columns=["T","Y","W","X"],
                       declared_assumptions=EFFECT,alpha=.05,treatment="T",outcome="Y")
    q.adjustment.extend(["W","X"] if op!="conditional_effect_econml" else ["W"])
    if op=="ate_dowhy":
        # X is a prognostic variable and not a confounder. Require exactly the
        # identified declared W backdoor set; use an adjusted fixture with
        # X also causing T only if that is part of the data mechanism.
        q.adjustment[:]=["W"]
        for a,b in (("W","T"),("W","Y"),("X","Y"),("T","Y")):
            q.graph_edges.add(source=a,target=b)
    if op=="conditional_effect_econml":
        q.effect_modifiers.append("X");q.modifier_profile.append(profile)
    q.rows.extend(pb.NumericRow(values=row) for row in data)
    return q

def oracle_hc3(data,adjust,interaction=False,profile=0.,alpha=.05):
    # Independent QR fit / sandwich covariance, no statsmodels or DoWhy.
    t=data[:,0];y=data[:,1]
    design=np.column_stack((np.ones(len(t)),t,*[data[:,i] for i in adjust],
                            *([t*data[:,3]] if interaction else [])))
    Q,R=np.linalg.qr(design,mode="reduced")
    beta=np.linalg.solve(R,Q.T@y)
    residual=y-design@beta
    leverage=np.sum(Q*Q,axis=1)
    if np.any(leverage>=1):raise ValueError("singular leverage")
    A=np.linalg.solve(R,Q.T)
    V=(A*(residual/(1-leverage))**2)@A.T
    contrast=np.zeros(len(beta));contrast[1]=1
    if interaction:contrast[-1]=profile
    mu=float(contrast@beta)
    se=float(np.sqrt(contrast@V@contrast))
    z=NormalDist().inv_cdf(1-alpha/2)
    return (mu,mu-z*se,mu+z*se)

def causal_call(q,expected="completed"):
    raw=q.SerializeToString(deterministic=True)
    a=perf_counter();cpu=process_time()
    result=run_causal_wire(raw)
    wall=perf_counter()-a;cpu=process_time()-cpu
    reply=pb.CausalReply.FromString(result)
    assert reply.SerializeToString(deterministic=True)==result
    assert reply.input_sha256==sha256(raw).hexdigest()
    assert reply.status==expected,(reply.status,reply.code,q.operation)
    evidence={"request_sha256":reply.input_sha256,"reply_sha256":sha256(result).hexdigest(),
              "operation":q.operation,"rows":len(q.rows),"columns":list(q.columns),
              "assumptions":list(q.declared_assumptions),"status":reply.status,
              "code":reply.code,"backend":reply.backend,"limitations":list(reply.limitations),
              "wall_seconds":wall,"cpu_seconds":cpu}
    if expected!="completed":
        assert not reply.has_effect and not reply.has_interval and not reply.discovered_edges
        assert not reply.estimand and not reply.uncertainty_kind
        return reply,evidence
    assert tuple(reply.declared_assumptions)==tuple(q.declared_assumptions)
    assert "assumptions_declared_not_verified" in reply.limitations
    if reply.has_effect:
        assert reply.has_interval and reply.interval_lower<=reply.effect<=reply.interval_upper
        assert abs(reply.confidence_level-(1-q.alpha))<1e-12
        assert "observational_causal_identification_not_verified" in reply.limitations
        evidence.update(effect=reply.effect,interval=[reply.interval_lower,reply.interval_upper],
                        uncertainty_kind=reply.uncertainty_kind,estimand=reply.estimand)
    else:
        assert not reply.has_interval
        evidence.update(edges=[{"source":e.source,"target":e.target,"orientation":e.orientation}
                               for e in reply.discovered_edges],
                        uncertainty_kind=reply.uncertainty_kind,estimand=reply.estimand)
    return reply,evidence

def numeric_statsmodels():
    data=effect_data()
    q=effect_request("ate_statsmodels",data)
    reply,ev=causal_call(q)
    oracle=oracle_hc3(data,[2,3]);naive=oracle_hc3(data,[])
    assert np.allclose([reply.effect,reply.interval_lower,reply.interval_upper],oracle,atol=1e-9,rtol=1e-9)
    assert abs(reply.effect-2.5)<.2 and abs(naive[0]-2.5)>.5
    # Repeated independently seeded simulated datasets. Finite-sample
    # coverage and error are descriptive, not proof of future calibration.
    sims=[]
    for seed in range(810,830):
        sample=effect_data(seed,600)
        y,e=causal_call(effect_request("ate_statsmodels",sample))
        exact=oracle_hc3(sample,[2,3])
        assert np.allclose([y.effect,y.interval_lower,y.interval_upper],exact,atol=1e-9,rtol=1e-9)
        sims.append({**e,"seed":seed,"truth":2.5,
                     "covered":y.interval_lower<=2.5<=y.interval_upper})
    return {"fixture":ev,"truth":2.5,"independent_hc3":oracle,"unadjusted_hc3":naive,
            "simulations":sims,"coverage_count":sum(s["covered"] for s in sims),
            "coverage_trials":len(sims),"mean_absolute_error":float(np.mean([abs(s["effect"]-2.5) for s in sims]))}

def numeric_dowhy():
    data=effect_data()
    # Include every declared variable in the DAG. X is an independent
    # outcome predictor, not a treatment cause; use exactly W as backdoor.
    q=effect_request("ate_dowhy",data)
    reply,ev=causal_call(q)
    baseline=effect_request("ate_statsmodels",data);baseline.adjustment[:]=["W"]
    sm,smev=causal_call(baseline)
    oracle=oracle_hc3(data,[2])
    assert np.allclose([reply.effect,reply.interval_lower,reply.interval_upper],oracle,atol=1e-9,rtol=1e-9)
    assert abs(reply.effect-sm.effect)<1e-9 and abs(reply.effect-2.5)<.2
    bad=pb.CausalRequest();bad.CopyFrom(q);del bad.adjustment[:]
    refused,negative=causal_call(bad,"invalid_input")
    assert refused.code=="unblocked_backdoor_path"
    return {"fixture":ev,"standalone_statsmodels":smev,"independent_hc3":oracle,"truth":2.5,
            "declared_graph":[(e.source,e.target) for e in q.graph_edges],
            "missing_adjustment_control":negative,
            "composition":"DoWhy graph identification + maintained statsmodels HC3; independent QR check"}

def numeric_econml():
    data=effect_data(seed=911,n=1600,heterogeneous=True)
    results=[]
    for profile in (-.75,.75):
        q=effect_request("conditional_effect_econml",data,profile)
        reply,ev=causal_call(q)
        truth=2+1.2*profile
        oracle=oracle_hc3(data,[2,3],True,profile)
        assert abs(reply.effect-truth)<.45,(truth,reply.effect)
        assert abs(reply.effect-oracle[0])<.45,(reply.effect,oracle)
        results.append({**ev,"profile":profile,"truth":truth,"independent_interaction_hc3":oracle,
                        "covered_truth":reply.interval_lower<=truth<=reply.interval_upper})
    assert results[1]["effect"]-results[0]["effect"]>1.
    q=effect_request("conditional_effect_econml",data,9.)
    bad,negative=causal_call(q,"invalid_input")
    assert bad.code=="modifier_profile_outside_observed_support"
    return {"profiles":results,"extrapolation_control":negative,
            "comparison":"different estimators, agreement measured against known mechanism and linear interaction oracle",
            "interval_claim":"two fixed-profile conditional intervals; no general calibration claim"}

def pc_request(data):
    q=pb.CausalRequest(schema_version=1,operation="discover_pc",columns=["A","B","C"],
                       declared_assumptions=PC,alpha=.001)
    q.rows.extend(pb.NumericRow(values=row) for row in data)
    return q

def numeric_pc():
    # Collider: A and B independent causes of C. Chain: A-C separation
    # conditioned on B, no identified unique DAG direction.
    rng=np.random.default_rng(448);n=1600
    a=rng.normal(size=n);b=rng.normal(size=n);c=1.4*a+1.4*b+rng.normal(size=n)
    collider=np.column_stack((a,b,c))
    x=rng.normal(size=n);y=1.5*x+rng.normal(size=n);z=1.5*y+rng.normal(size=n)
    chain=np.column_stack((x,y,z))
    result,ev=causal_call(pc_request(collider))
    assert {(e.source,e.target,e.orientation) for e in result.discovered_edges}=={
        ("A","C","directed"),("B","C","directed")}
    assert abs(np.corrcoef(collider,rowvar=False)[0,1])<.08
    result,chain_ev=causal_call(pc_request(chain))
    assert {frozenset((e.source,e.target)) for e in result.discovered_edges}=={
        frozenset(("A","B")),frozenset(("B","C"))}
    assert all(e.orientation=="undirected" for e in result.discovered_edges)
    residual_a=x-np.column_stack((np.ones(n),y))@np.linalg.lstsq(np.column_stack((np.ones(n),y)),x,rcond=None)[0]
    residual_c=z-np.column_stack((np.ones(n),y))@np.linalg.lstsq(np.column_stack((np.ones(n),y)),z,rcond=None)[0]
    partial=float(np.corrcoef(residual_a,residual_c)[0,1]);assert abs(partial)<.08
    return {"collider":ev,"chain":chain_ev,"independent_chain_partial_correlation":partial,
            "truth":"collider compelled orientations; chain Markov equivalence not unique DAG"}

def main():
    p=ArgumentParser();p.add_argument("--backend",choices=OPS,required=True)
    p.add_argument("--out",type=Path,required=True);args=p.parse_args()
    build=os.environ.get("COG06B_EXPECTED_SHA","")
    if len(build)!=40:raise RuntimeError("exact source identity required")
    action={"statsmodels":numeric_statsmodels,"dowhy":numeric_dowhy,
            "econml":numeric_econml,"causal-learn":numeric_pc}[args.backend]
    result=action()
    rss=None
    if sys.platform.startswith("linux"):
        import resource
        rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    record={"schema":"cognitum.cog07.causal-reference.v1","source_sha":build,
            "backend":args.backend,"versions":{k:version(k) for k in sorted({"numpy","scipy","statsmodels",args.backend})},
            "cpu_only":True,"peak_process_rss_kib":rss,"fixture_data":"synthetic known mechanism, fixed seeds",
            "result":result,"production_enabled":False,"Tigramite":"license-gated NOT_RUN",
            "model_trial":"NOT_RUN","scientific_scope":"conditional on declared assumptions; no real-world causal proof"}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(record,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps(record,indent=2,allow_nan=False))

if __name__=="__main__":main()
