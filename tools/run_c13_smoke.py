"""C13 P1 bounded functional smoke: exact Bayes, soft evidence, impossible, LW, tampering."""
from cognitum.proto import probability_pb2 as p
from cognitum import probability as c


def req(method=p.EXACT_VARIABLE_ELIMINATION):
    q = p.InferenceRequest(schema_version=1, trace_id='c13-smoke', method=method,
                           timeout_ms=5000, max_verifier_assignments=512)
    q.model.nodes.add(id='rain',states=['no','yes'],cpt_ppm=[800000,200000])
    q.model.nodes.add(id='wet',states=['no','yes'],parents=[0],
                      cpt_ppm=[900000,100000,200000,800000])
    q.targets.append(0)
    return q


def run():
    q=req();q.hard_evidence.add(node=1,state=1)
    f=q.SerializeToString(deterministic=True)
    r=c.infer_frame(f,enabled=True,host_authorized=True)
    ans=p.InferenceResult.FromString(r)
    assert ans.status==p.EXACT_POSTERIOR and [x.probability for x in ans.posterior]==['1/3','2/3']
    assert c.verify_receipt(f,r).exact_posterior_verified
    print('PASS 1: independent Bayes posterior certification')
    q=req();q.soft_evidence.add(node=1,likelihood_ppm=[200000,1000000])
    f=q.SerializeToString(deterministic=True);r=c.infer_frame(f,enabled=True,host_authorized=True)
    assert [x.probability for x in p.InferenceResult.FromString(r).posterior]==['4/7','3/7']
    assert c.verify_receipt(f,r).exact_posterior_verified
    print('PASS 2: soft likelihood conditioning')
    q=req();q.model.nodes[1].cpt_ppm[:]=[1000000,0,1000000,0];q.hard_evidence.add(node=1,state=1)
    f=q.SerializeToString(deterministic=True);r=c.infer_frame(f,enabled=True,host_authorized=True)
    assert p.InferenceResult.FromString(r).status==p.IMPOSSIBLE_EVIDENCE
    assert c.verify_receipt(f,r).exact_posterior_verified
    print('PASS 3: impossible evidence certified as zero mass')
    q=req(p.SEEDED_LIKELIHOOD_WEIGHTING);q.samples=1000;q.random_seed=42
    f=q.SerializeToString(deterministic=True);r=c.infer_frame(f,enabled=True,host_authorized=True)
    assert p.InferenceResult.FromString(r).status==p.APPROXIMATE_POSTERIOR
    assert not c.verify_receipt(f,r).exact_posterior_verified
    print('PASS 4: seeded approximate posterior is explicitly uncertified')
    q=req();f=q.SerializeToString(deterministic=True);r=c.infer_frame(f,enabled=True,host_authorized=True)
    modified=p.InferenceResult.FromString(r);modified.posterior[0].probability='1'
    assert not c.verify_receipt(f,modified.SerializeToString(deterministic=True)).evidence_valid
    print('PASS 5: tampered posterior rejected')
    assert p.InferenceResult.FromString(c.infer_frame(f,enabled=True,host_authorized=False)).status==p.REJECTED_INFERENCE
    print('PASS 6: host authority gate denies request')

if __name__ == '__main__':run()
