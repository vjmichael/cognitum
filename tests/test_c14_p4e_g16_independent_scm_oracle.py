"""C14 G16: seeded independent exact-rational oracle for a confounded SCM.

The oracle uses explicit truth tables over U,E, not Cognitum's causal.py
execution or built-in replay. Does NOT identify causal effect from raw data.
"""
import random
from fractions import Fraction
from cognitum.proto import causal_pb2 as pb
from cognitum.causal import run_causal_frame,verify_causal_result,causal_receipt


def make_case(seed):
    r=random.Random(seed)
    u_prob=r.randrange(150_000,850_001)
    e_prob=r.randrange(150_000,850_001)
    x_fn=[r.randrange(2) for _ in range(4)]
    y_fn=[r.randrange(2) for _ in range(4)]
    # Avoid degenerate default cases; retain differing exposure outcomes.
    if set(x_fn)=={0} or set(x_fn)=={1}:x_fn[0]=0;x_fn[3]=1
    exo=[pb.ExogenousVariable(id='U',states=['u0','u1'],probability_ppm=[u_prob,1_000_000-u_prob]),
         pb.ExogenousVariable(id='E',states=['e0','e1'],probability_ppm=[e_prob,1_000_000-e_prob])]
    scm=pb.StructuralCausalModel(
        assumption_id=f'g16-synthetic-{seed}',exogenous=exo,
        endogenous=[pb.EndogenousVariable(id='X',states=['x0','x1'],noise=[0,1],function_outputs=x_fn),
                    pb.EndogenousVariable(id='Y',states=['y0','y1'],parents=[0],noise=[0],function_outputs=y_fn)])
    return scm,x_fn,y_fn,u_prob,e_prob


def oracle(x_fn,y_fn,u_prob,e_prob):
    values=[]
    for u in (0,1):
        for e in (0,1):
            x=x_fn[u*2+e]
            y=y_fn[x*2+u]
            w=Fraction(u_prob if u==0 else 1_000_000-u_prob,1_000_000)*Fraction(e_prob if e==0 else 1_000_000-e_prob,1_000_000)
            values.append((u,e,x,y,w))
    def cond(test, outcome):
        total=sum((w for u,e,x,y,w in values if test(u,e,x,y)),Fraction(0))
        if not total:return None
        return sum((w for u,e,x,y,w in values if test(u,e,x,y) and outcome(u,e,x,y)),Fraction(0))/total
    return {
      'observe':cond(lambda u,e,x,y:x==1,lambda u,e,x,y:y==1),
      'intervene':sum((w for u,e,x,y,w in values if y_fn[2+u]==1),Fraction(0)),
      'counterfactual':cond(lambda u,e,x,y:x==0 and y==0,lambda u,e,x,y:y_fn[2+u]==1),
    }


def query(scm,op,seed):
    kw={'schema_version':1,'trace_id':f'c14-g16-{seed}-{op}', 'operation':op,'model':scm,
        'target':1,'max_exogenous_assignments':16,'timeout_ms':2000}
    if op==pb.OBSERVATIONAL_QUERY:
        kw['factual_evidence']=[pb.StateObservation(variable=0,state=1)]
    if op==pb.INTERVENTIONAL_QUERY:
        kw['interventions']=[pb.StateObservation(variable=0,state=1)]
    if op==pb.COUNTERFACTUAL_QUERY:
        kw['interventions']=[pb.StateObservation(variable=0,state=1)]
        kw['factual_evidence']=[pb.StateObservation(variable=0,state=0),pb.StateObservation(variable=1,state=0)]
    return pb.CausalRequest(**kw)


def test_randomized_independent_causal_oracle():
    mismatches=0;effects_differ=0;checked=0;zero_support=0
    for seed in range(1600,1696):
        scm,xf,yf,up,ep=make_case(seed)
        expected=oracle(xf,yf,up,ep)
        if expected['observe'] is not None and expected['observe']!=expected['intervene']:
            effects_differ+=1
        for op,key in [(pb.OBSERVATIONAL_QUERY,'observe'),(pb.INTERVENTIONAL_QUERY,'intervene'),(pb.COUNTERFACTUAL_QUERY,'counterfactual')]:
            q=query(scm,op,seed)
            raw=q.SerializeToString(deterministic=True)
            result_frame=run_causal_frame(raw,host_authorized=True,enabled=True)
            result=pb.CausalResult.FromString(result_frame)
            assert verify_causal_result(raw,result_frame), (seed,key,'replay')
            if expected[key] is None:
                zero_support+=1
                assert result.status==pb.IMPOSSIBLE_FACTUAL_EVIDENCE,(seed,key,result.status)
                assert not causal_receipt(raw,result_frame).evidence_valid
            else:
                assert result.status==pb.EXACT_MODEL_RESULT,(seed,key,result.status)
                assert Fraction(result.posterior[1].probability)==expected[key],(seed,key,result.posterior,expected[key])
                assert causal_receipt(raw,result_frame).evidence_valid
                checked+=1
            # Cross-instance result substitution cannot verify.
            other=query(scm,op,seed+10_000)
            assert not verify_causal_result(other.SerializeToString(deterministic=True),result_frame)
    assert checked>=200 and effects_differ>=8
    print(f'C14_G16_FINITE_ORACLE checked={checked} unsupported_evidence={zero_support} confounding_differences={effects_differ} tested_scms=96')


def test_zero_assumed_scm_authorization():
    scm,*_=make_case(1603)
    q=query(scm,pb.INTERVENTIONAL_QUERY,1603)
    raw=q.SerializeToString(deterministic=True)
    r=pb.CausalResult.FromString(run_causal_frame(raw,host_authorized=False,enabled=True))
    assert r.status==pb.REJECTED_CAUSAL and not r.independently_checked


def test_cross_model_provenance_rejected():
    scm,*_=make_case(1605)
    q=query(scm,pb.INTERVENTIONAL_QUERY,1605)
    raw=q.SerializeToString(deterministic=True)
    out=run_causal_frame(raw,host_authorized=True,enabled=True)
    altered=query(scm,pb.INTERVENTIONAL_QUERY,1605)
    altered.model.exogenous[0].probability_ppm[:]=[400000,600000]
    assert not verify_causal_result(altered.SerializeToString(deterministic=True),out)
