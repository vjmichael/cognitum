"""G14 genuine mature-worker process + bounded research gate smoke.

Run with G5 isolated interpreter, no network. Host admission and OS isolation
flags below are development TEST DOUBLES, NOT actual Lu or Windows attestation.
"""
import copy
from hashlib import sha256
from importlib.metadata import version,PackageNotFoundError
import json
from pathlib import Path
import sys
from cognitum import causal_mature_backend as mature
from cognitum import causal_genuine_worker_assurance as gate
from cognitum.proto import causal_mature_pb2 as m
from cognitum.proto import causal_genuine_worker_assurance_pb2 as pb
from tests.test_c14_p3c_mature_adapter import fixtures,encode,policy
from tests.test_c14_p4e_g14_bridge import request

OUT=Path('docs/components/causal/P4E-G14-genuine-worker-smoke-evidence.json')

def conduct():
    cases=[]
    for worker_req in fixtures():
        pkg,pin=mature.BACKEND_PACKAGES[worker_req.backend]
        if version(pkg)!=pin:
            raise RuntimeError('GENUINE_LIBRARY_PIN_NOT_AVAILABLE '+pkg)
        raw=encode(worker_req)
        # Explicitly development-test fake approval/attestation; never a release gate.
        result=mature.run_mature_frame(raw,host_authorized=True,
           enabled=True,worker_policy=policy(worker_req.backend))
        worker=m.MatureCausalResult.FromString(result)
        if worker.status!=m.MATURE_RESULT_CANDIDATE:
            raise RuntimeError('REAL_WORKER_DID_NOT_EXECUTE '+worker.reason_code)
        check=mature.verify_mature_receipt(raw,result)
        if not check.request_bound_structure_checked:
            raise RuntimeError('REAL_WORKER_VERIFIER_REJECTED')
        q=request(worker_req,worker_reply=result)
        d,r=gate.calculate(q)
        if (not gate.verify(q,d,r) or
            d.disposition!=pb.WORKER_ASSURANCE_RESEARCH_DIAGNOSTIC_ONLY or
            any((d.worker_output_independently_authenticated,d.causal_identification_proven,
               d.calibrated_for_worker_dataset,d.authenticated_lu_host,
               d.may_trigger_external_action,d.may_issue_real_world_causal_claim))):
            raise RuntimeError('REAL_WORKER_ASSURANCE_FAILED')
        injection=copy.deepcopy(q);injection.caller_requests_real_world_action=True
        blocked,_=gate.calculate(injection)
        if blocked.disposition!=pb.WORKER_ASSURANCE_ABSTAIN_CAUSAL_OR_ACTION:
            raise RuntimeError('ACTION_REQUEST_NOT_DENIED')
        stable=m.MatureCausalResult();stable.CopyFrom(worker);stable.wall_ns=0
        cases.append({'backend':pkg,'version':worker.runtime_version,
            'trace_id':worker.trace_id,'sample_count':worker.sample_count,
            'effects':[{ 'group':list(x.modifier_states),'estimated_effect':x.estimated_effect,
                          'reference_effect':x.reference_effect} for x in worker.effects],
            'skeleton_edges':[[x.first,x.second] for x in worker.skeleton_edges],
            'worker_result_sha256':sha256(result).hexdigest(),
            'scientific_payload_sha256_without_timing':sha256(encode(stable)).hexdigest(),
            'request_sha256':sha256(raw).hexdigest(),
            'g14_disposition':pb.WorkerAssuranceDisposition.Name(d.disposition),
            'g14_reason_codes':list(d.reason_codes),
            'intervention_request_denied':True,
            'worker_shape_verified':True,'worker_origin_authenticated':False,
            'production_os_isolation_verified':False})
    return {'milestone':'C14 P4E G14','real_scientific_subprocesses':len(cases),
        'real_llm_invoked':False,'actual_lu_host_authenticated':False,
        'native_windows_confinement_verified':False,
        'worker_os_attestation_flags_are_test_doubles':True,
        'external_actions_authorized':0,'cases':cases}

def main():
    evidence=conduct()
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(evidence,indent=2,sort_keys=True)+'\n')
    print('G14 genuine subprocess and assurance PASS:',len(evidence['cases']),
       'real mature-library workers, zero action grants')
    for row in evidence['cases']:
        print(row['backend'],row['version'],row['sample_count'],row['g14_disposition'])
if __name__=='__main__':main()
