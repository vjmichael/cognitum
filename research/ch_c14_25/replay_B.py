import pathlib,json,hashlib,sys,time
from decimal import Decimal
HERE=pathlib.Path(__file__).resolve().parent;CH24=HERE.parent/'ch_c14_24'
if not CH24.exists():CH24=pathlib.Path('/mnt/data/CH_C14_24');sys.path.insert(0,str(CH24))
from verified_bnb import logistic_model,FirthObjective,bound_node,candidate_lower,model_digest
from verify_certificate import check_tree,validate_model
from mpfr_interval import checked_threshold,UP,DOWN
import mpfr_interval
pb=(HERE/'frozen_protocol_B.json').read_bytes();p=json.loads(pb);assert hashlib.sha256(pb).hexdigest()==(HERE/'frozen_protocol_B.sha256').read_text().split()[0]
tag=sys.argv[1];case=next(c for c in p['cases'] if c['id']==tag)
inp_bytes=(HERE/'inputs'/f'{tag}.json').read_bytes();assert hashlib.sha256(inp_bytes).hexdigest()==case['exact_input_sha256'];inp=json.loads(inp_bytes)
cert=json.loads((HERE/'certificates'/f'{tag}.json').read_text());meta=cert['CH25_original_case']
assert meta['original_digest']==case['original_digest'] and meta['frozen_input_sha256']==case['exact_input_sha256']
assert meta['protocol_B_sha256']==hashlib.sha256(pb).hexdigest()
assert cert['root_box']==p['root_box']
assert cert['milestone']=='CH-C14-24' and cert['claim_scope']=='finite_root_box_only' and cert['production_release']=='NO_GO'
assert cert['tolerance']==p['objective_absolute_tolerance'] and cert['precision_bits']==p['precision_bits']
validate_model(cert['model']);assert model_digest(cert['model'])==cert['model_sha256']
assert logistic_model(inp['rows'])==cert['model']
mpfr_interval.PRECISION=p['verifier_precision_bits']
t=time.monotonic();leaves=check_tree(cert['nodes'],cert['root_box']);assert len(leaves)==cert['leaf_count']
incumbent=cert['incumbent'];assert all(Decimal(a)<=Decimal(x)<=Decimal(b) for x,(a,b) in zip(incumbent,cert['root_box']))
model=FirthObjective(cert['model']);lower=candidate_lower(model,incumbent)
uppers=[bound_node(model,leaf['box'],curvature=False)[0].hi for leaf in leaves]
# Use exact MPFR ordering, never binary64 display ordering, for certification.
upper=uppers[0]
for u in uppers[1:]:
    if u.cmp(upper)>0: upper=u
certified=all(checked_threshold(u,lower,p['objective_absolute_tolerance']) for u in uppers)
if cert['status']=='CERTIFIED_BOUNDED_GAP' and not certified:raise ArithmeticError('REPLAY_REJECTED_FALSE_CERTIFICATION')
out={'case_id':tag,'result':'VERIFIED_BOUNDED_GAP' if certified else 'REPLAYED_BUT_UNRESOLVED','original_digest':case['original_digest'],'bits':p['verifier_precision_bits'],'leaf_count':len(leaves),'partition_cover_verified':True,'all_leaf_bounds_recomputed':True,'model_digest_bound_to_input':True,'replay_lower_floor':lower.as_float(DOWN),'replay_upper_ceil':upper.as_float(UP),'absolute_gap_upper_display':max(0,upper.as_float(UP)-lower.as_float(DOWN)),'global_R3_certified':False,'production_release':'NO_GO','replay_mode':'directed_MPFR_direct_bound_no_curvature','elapsed_seconds':round(time.monotonic()-t,3)}
(HERE/'verifications'/f'{tag}.json').write_text(json.dumps(out,indent=2)+'\n')
state={'case_id':tag,'study':'CH-C14-25-stage-B','original_digest':case['original_digest'],'original_CH23_ambiguous':case['ambiguous'],'events':case['events'],'frozen_protocol_B_sha256':hashlib.sha256(pb).hexdigest(),'max_nodes':p['node_budget_per_case'],'tol':p['objective_absolute_tolerance'],'bits':p['precision_bits'],'solver_status':cert['status'],'node_count':len(cert['nodes']),'split_count':cert['split_count'],'leaf_count':len(leaves),'solver_lower':cert['lower_bound_floor_display'],'solver_upper':cert['upper_bound_ceil_display'],'verifier_result':out['result'],'verifier_upper':out['replay_upper_ceil'],'verifier_lower':out['replay_lower_floor'],'gap_upper':out['absolute_gap_upper_display']}
for postfix in ('root','solve'):
    path=HERE/'logs'/f'{tag}_{postfix}.json'
    if path.exists():state.update({postfix+'_evidence':json.loads(path.read_text())})
(HERE/'logs'/f'{tag}.json').write_text(json.dumps(state,indent=2)+'\n')
print(json.dumps(out),flush=True)
