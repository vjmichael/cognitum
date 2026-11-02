"""Reproducibly freeze original CH23 case duals and CH27 15-case protocol.
Never reads CH27 results or modifies CH23/24/25/26 data.
"""
import json,hashlib,sys
from pathlib import Path
BASE=Path(__file__).resolve().parent.parent
for p in (BASE/'CH_C14_24',BASE/'CH_C14_26'):
    if p.is_dir() and str(p) not in sys.path:sys.path.insert(0,str(p))
from coupled27 import heuristic_Q,is_spd_exact
from improved_bounds import ImprovedObjective
from verified_bnb import logistic_model,midpoint_bounds
D=Path(__file__).resolve().parent
C=BASE/'CH_C14_25'
P26=json.loads((BASE/'CH_C14_26'/'frozen_protocol.json').read_text())
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
Q={}
for c in P26['cases']:
    f=C/'inputs'/f"{c['id']}.json"
    assert digest(f)==c['exact_input_sha256'],c['id']
    inp=json.loads(f.read_text())
    assert inp['original_CH23_identity']['data_digest']==c['original_digest']
    m=ImprovedObjective(logistic_model(inp['rows']))
    pts=inp['seeds'][:1]+[midpoint_bounds(inp['bounds'])[0]]
    qq=heuristic_Q(m,pts)
    if not qq or not all(is_spd_exact(q) for q in qq):raise ArithmeticError('Missing exact SPD dual')
    Q[c['id']]=qq
(D/'frozen_duals.json').write_text(json.dumps(Q,indent=2,sort_keys=True)+'\n')
source_names=['coupled27.py','interval_newton27.py','solver27.py','verifier27.py','freeze27.py']
protocol={
    'milestone':'CH-C14-27', 'study':'same frozen CH23 12 bounding + 3 ambiguous original cases',
    'research_only':True,'scientific_release':'NO_GO',
    'cohort_from_CH26_sha256':digest(BASE/'CH_C14_26'/'frozen_protocol.json'),
    'case_input_sha256':{c['id']:c['exact_input_sha256'] for c in P26['cases']},
    'dual_matrices_sha256':digest(D/'frozen_duals.json'),
    'objective_absolute_tolerance':'0.05',
    'precision_bits':160,'replay_precision_bits':224,
    'node_budget_per_case':15,
    'max_newton_evaluations_per_case':8,
    'newton_max_side_width':'3.0',
    'original_root_box':P26['root_box'],
    'split_policy':'deterministic widest exact-Decimal side midpoint; priority heuristic only',
    'bound_policy':'min CH26 independent Loewner-tangent and CH27 SPD dual-supporting-lines',
    'newton_policy':'interior original-domain boxes only; Krawczyk enclosure and gradient sign exclusion; boundary never discarded',
    'source_sha256':{k:digest(D/k) for k in source_names},
    'dependency_sha256':{str(x):digest(BASE/x) for x in [
         'CH_C14_24/mpfr_interval.py','CH_C14_24/verified_bnb.py','CH_C14_24/verify_certificate.py',
         'CH_C14_26/improved_bounds.py']}
}
(D/'frozen_protocol.json').write_text(json.dumps(protocol,indent=2,sort_keys=True)+'\n')
(D/'frozen_protocol.sha256').write_text(digest(D/'frozen_protocol.json')+'  frozen_protocol.json\n')
print('FROZEN',digest(D/'frozen_protocol.json'),'cases',len(Q),'dual hashes',protocol['dual_matrices_sha256'])
