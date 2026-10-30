"""C14 P1 small functional smoke, no causal-effect performance benchmark."""
from cognitum.proto import causal_pb2 as p
from cognitum.causal import run_causal_frame,causal_receipt,verify_causal_result
from tests.test_c14_causal import request

def test(name,req,expected,checked=True):
    raw=req.SerializeToString(deterministic=True)
    out=run_causal_frame(raw,host_authorized=True,enabled=True)
    r=p.CausalResult.FromString(out)
    assert r.status==expected,(name,r.status,r.reason_code)
    assert verify_causal_result(raw,out)==checked,(name,'independent verification mismatch')
    if expected in (p.EXACT_MODEL_RESULT,p.BACKDOOR_CERTIFIED):
        assert causal_receipt(raw,out).evidence_valid,name
    print('PASS:',name)

def main():
    test('observational distribution',request(),p.EXACT_MODEL_RESULT)
    test('do intervention distinct from observing',request(p.INTERVENTIONAL_QUERY,interventions=[p.StateObservation(variable=0,state=1)]),p.EXACT_MODEL_RESULT)
    test('same-world noise counterfactual',request(p.COUNTERFACTUAL_QUERY,
            interventions=[p.StateObservation(variable=0,state=1)],factual_evidence=[p.StateObservation(variable=0,state=0)]),p.EXACT_MODEL_RESULT)
    test('hidden confounder blocks naive backdoor',request(p.BACKDOOR_CHECK,treatment=0),p.BACKDOOR_NOT_CERTIFIED)
    test('contradictory evidence',request(p.COUNTERFACTUAL_QUERY,
            interventions=[p.StateObservation(variable=0,state=1)],
            factual_evidence=[p.StateObservation(variable=0,state=1),p.StateObservation(variable=1,state=1)]),p.IMPOSSIBLE_FACTUAL_EVIDENCE)
    req=request();raw=req.SerializeToString(deterministic=True)
    out=run_causal_frame(raw,host_authorized=False,enabled=True)
    assert p.CausalResult.FromString(out).status==p.REJECTED_CAUSAL and not causal_receipt(raw,out).evidence_valid
    print('PASS: authorization denial')
    return 0

if __name__=='__main__':raise SystemExit(main())
