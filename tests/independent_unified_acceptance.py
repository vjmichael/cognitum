"""Independent numerical checks; fixed seed, no external truth/certification claims."""
from pathlib import Path
import json,sys,base64,io,hashlib
import numpy as np
from cognitum.specialists.ssm import scan_request
from cognitum.plugins.specialists import Specialists
from cognitum.proto import research_optional_pb2 as pb

rng=np.random.default_rng(117301)
ssm_count=0;ssm_max_err=0
for i in range(160):
 n=int(rng.integers(1,5));d=int(rng.integers(1,5));out=int(rng.integers(1,5));t=int(rng.integers(1,24))
 a=rng.uniform(.0,.95,size=n); b=rng.normal(0,.2,size=(n,d));c=rng.normal(0,.2,size=(out,n));feed=rng.normal(0,.2,size=(out,d))
 x=rng.normal(size=(t,d));h=rng.normal(size=n)
 request={'parameters':{'a':a.tolist(),'b':b.tolist(),'c':c.tolist(),'d':feed.tolist()},'inputs':x.tolist(),'initial_state':h.tolist()}
 actual=scan_request(request)
 exp=[]
 for item in x:
  h=np.diag(a)@h+b@item
  exp.append(c@h+feed@item)
 err=max(np.max(np.abs(np.asarray(actual['outputs'])-np.asarray(exp))),np.max(np.abs(np.asarray(actual['final_state'])-h)))
 ssm_max_err=max(ssm_max_err,float(err));assert err<1e-11
 ssm_count+=1

hdc_count=0
for i in range(50):
 req=pb.HdcQuery(schema_version=1,source_snapshot_id='s2',index_snapshot_id='s2',role='owner',entity=f'e{i}',top_k=3)
 for j in range(5):req.records.add(candidate_id=f'c{j}',role='owner',entity=f'e{i}' if j==0 else f'x{j}')
 raw=req.SerializeToString(deterministic=True)
 output=Specialists().handle('specialist.hdc',{'frame_b64':base64.b64encode(raw).decode()})
 candidates=pb.HdcCandidates.FromString(base64.b64decode(json.loads(output['result_json'])['protobuf_b64']))
 assert candidates.candidate_ids[0]=='c0' and candidates.hamming_distance[0]==0
 hdc_count+=1

from test_research_optional import kan_artifact
kan_checkpoint=kan_artifact();kan_digest=hashlib.sha256(kan_checkpoint).hexdigest()
import os
os.environ['COGNITUM_TRUSTED_KAN_SHA256']=kan_digest
kan_count=0;kan_max_err=0
for i in range(50):
 point=float(rng.uniform(-.9,.9));req=pb.KanRequest(schema_version=1,feature_values=[format(point,'.6f')],checkpoint_sha256=kan_digest)
 raw=req.SerializeToString(deterministic=True)
 v=Specialists().handle('specialist.kan',{'frame_b64':base64.b64encode(raw).decode(),'checkpoint_b64':base64.b64encode(kan_checkpoint).decode()})
 out=pb.KanPrediction.FromString(base64.b64decode(json.loads(v['result_json'])['protobuf_b64']))
 x=float(req.feature_values[0]);expected=sum(np.exp(-((x-g)**2)) for g in [-1.,0.,1.])
 err=abs(float(out.predicted_values[0])-expected)
 kan_max_err=max(kan_max_err,err)
 if err>=1e-6 or out.uncertainty_calibrated:
  print('KAN FAIL', i, x, float(out.predicted_values[0]), expected,err, out.uncertainty_calibrated)
 assert err<1e-6 and not out.uncertainty_calibrated
 kan_count+=1
print(json.dumps({'ssm_checks':ssm_count,'ssm_max_abs_error':ssm_max_err,'hdc_checks':hdc_count,'kan_checks':kan_count,'kan_max_abs_error':kan_max_err,'total_independent_checks':ssm_count+hdc_count+kan_count,'seed':117301,'status':'PASS'},indent=2))
