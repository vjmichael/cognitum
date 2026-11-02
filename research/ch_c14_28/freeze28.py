"""Freeze CH28 exploratory benchmark protocol before any benchmark execution."""
import json,hashlib
from pathlib import Path
D=Path(__file__).resolve().parent;BASE=D.parent
P=json.loads((BASE/'CH_C14_27'/'frozen_protocol.json').read_text())
files=['solver28.py','verifier28.py','run_case28.py','freeze28.py']
p={
 'milestone':'CH-C14-28','research_only':True,'scientific_release':'NO_GO',
 'cohort_CH27_sha256':hashlib.sha256((BASE/'CH_C14_27'/'frozen_protocol.json').read_bytes()).hexdigest(),
 'original_case_sha256':P['case_input_sha256'],
 'original_dual_sha256':P['dual_matrices_sha256'],
 'original_root_box':P['original_root_box'],
 'precision_bits':160,'replay_precision_bits':224,
 'objective_absolute_tolerance':'0.05',
 'node_budgets':[63,127],
 'selective_policy':{'always_depth':2,'cadence':3,'description':'root through depth 2 coupled; at deeper levels every third new node gets coupled unless direct bound already <= incumbent+epsilon; otherwise cheap certified Loewner bound'},
 'newton_max_side_width':'3.0','max_newton_evaluations_per_case':8,
 'solver_source_sha256':{f:hashlib.sha256((D/f).read_bytes()).hexdigest() for f in files},
 'dependency_source_sha256':{str(f):hashlib.sha256((BASE/f).read_bytes()).hexdigest() for f in [Path('CH_C14_24/mpfr_interval.py'),Path('CH_C14_24/verified_bnb.py'),Path('CH_C14_26/improved_bounds.py'),Path('CH_C14_27/coupled27.py'),Path('CH_C14_27/interval_newton27.py')]},
 'measurement':'Record process CPU and monotonic wall solve/replay times per case; no additional tests/data substituted.',
 'comparison':'CH27 published 15-node cohort; direct equal-budget CH27 control will be reported separately if completed.'
}
s=json.dumps(p,indent=2,sort_keys=True)+'\n';(D/'frozen_protocol.json').write_text(s)
h=hashlib.sha256(s.encode()).hexdigest();(D/'frozen_protocol.sha256').write_text(h+'  frozen_protocol.json\n')
print('FROZEN',h)
