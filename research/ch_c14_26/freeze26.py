import hashlib,json,pathlib
D=pathlib.Path(__file__).resolve().parent; C=D.parent/'CH_C14_25';H=D.parent/'CH_C14_24'
protocol25=json.loads((C/'frozen_protocol_B.json').read_bytes())
case=[]
for d in protocol25['cases']:
 raw=(C/'inputs'/f'{d["id"]}.json').read_bytes()
 check=hashlib.sha256(raw).hexdigest()
 assert check==d['exact_input_sha256'],d['id']
 case.append({k:d[k] for k in ('id','family','n','index','seed','original_digest','exact_input_sha256','ambiguous')})
source={}
for p in ('improved_bounds.py','solver26.py','verifier26.py'):
 source[p]=hashlib.sha256((D/p).read_bytes()).hexdigest()
proto={
 'milestone':'CH-C14-26','date':'2026-11-02','research_only':True,
 'study':'Original CH23 12 fixed index-0 bounding cases plus 3 original zero-event ambiguous datasets',
 'CH23_frozen_protocol_sha256':'31cd3f5d01e40e496e59d48b4160a9a3a4894645509eca9eae4cdcaf3e618bde',
 'CH25_frozen_protocol_B_sha256':hashlib.sha256((C/'frozen_protocol_B.json').read_bytes()).hexdigest(),
 'objective_absolute_tolerance':'0.05','root_box':[ ['-10','1'],['-5','5'],['-5','5'] ],
 'precision_bits':160,'replay_precision_bits':224,
 'node_budget_per_case':127,'max_hessian_calls_per_case':2,'hessian_max_root_side_width':'2.75',
 'use_loglikelihood_tangent':True,'split_policy':'CH24 physical widest Decimal interval, deterministic ties',
 'search_priority':'largest upper display float used only for ordering; decisions checked at MPFR precision',
 'interval_fisher_bound':'Hadamard AND termwise Fisher interval determinant AND Loewner Fisher Gram determinant',
 'interval_loglik_bound':'termwise binomial maxima AND concave tangent planes at original CH23 seed',
 'analytic_interval_hessian':'dI/dβ and d2I/dβ2 traced through adj(I)/det(I), MPFR outward',
 'failure_policy':'claim UNRESOLVED unless independently replayed U<=L+0.05; bounded box only',
 'old_CH25_max_nodes':31,'old_CH25_curvature':'root-only diagnostic',
 'source_sha256_at_freeze':source,
 'CH24_sources_sha256':{p:hashlib.sha256((H/p).read_bytes()).hexdigest() for p in ('verified_bnb.py','mpfr_interval.py','verify_certificate.py')},
 'cases':case
}
p=D/'frozen_protocol.json';p.write_text(json.dumps(proto,indent=2)+'\n')
sha=hashlib.sha256(p.read_bytes()).hexdigest();(D/'frozen_protocol.sha256').write_text(sha+'  frozen_protocol.json\n')
print('FROZEN CH26',sha,'cases',len(case),'max_nodes',proto['node_budget_per_case'],'source',source)
