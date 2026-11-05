"""Reconstruct exact CH23 binary64 datasets with pinned seed protocol. No new simulation."""
from __future__ import annotations
import hashlib, json, pathlib, sys
from decimal import Decimal
from datetime import date
OUT=pathlib.Path(__file__).resolve().parent
CH23=OUT.parent/'ch_c14_23'
CH24=OUT.parent/'ch_c14_24'
if not CH23.exists():CH23=pathlib.Path('/mnt/data/recovered_ch23/CH_C14_23')
if not CH24.exists():CH24=pathlib.Path('/mnt/data/CH_C14_24')
sys.path.insert(0,str(CH23))
import run as ch23_run
p=json.loads((CH23/'frozen_protocol.json').read_text())
recorded=[json.loads(x) for x in (CH23/'results.jsonl').read_text().splitlines()]
byid={(r['family'],r['n'],r['index']):r for r in recorded}
B=p['additional_bounded_certification']['box']
ids=[(fam,n,0) for fam in p['families'] for n in p['n_values']]
ids += [('zero_imbalanced',160,5),('zero_imbalanced',160,7),('rare_1pct',160,13)]
assert len(ids)==15 and len(set(ids))==15

def binary64_as_exact_decimal(x):
    return str(Decimal.from_float(float(x)))

protocol={
  'milestone':'CH-C14-25','study':'original_CH23_MPFR_bounded_replay',
  'frozen_before_solver_execution':True,'CH23_protocol_sha256':hashlib.sha256((CH23/'frozen_protocol.json').read_bytes()).hexdigest(),
  'CH23_results_sha256':hashlib.sha256((CH23/'results.jsonl').read_bytes()).hexdigest(),
  'CH23_generator_sha256':hashlib.sha256((CH23/'run.py').read_bytes()).hexdigest(),
  'CH24_solver_sha256':hashlib.sha256((CH24/'verified_bnb.py').read_bytes()).hexdigest(),
  'CH24_interval_sha256':hashlib.sha256((CH24/'mpfr_interval.py').read_bytes()).hexdigest(),
  'CH24_verifier_sha256':hashlib.sha256((CH24/'verify_certificate.py').read_bytes()).hexdigest(),
  'case_selection':'original_CH23_first_index_0_each_of_6_family_x_2_n_plus_all_3_original_ambiguous',
  'root_box':[[str(a),str(b)] for a,b in B],
  'precision_bits':160,'verifier_precision_bits':224,'objective_absolute_tolerance':'0.05',
  'node_budget_per_case':15,'curvature':True,
  'seeds':'all_original_validated_maxima_INSIDE_root_box_plus_CH23_root_box_midpoint',
  'dataset_interpretation':'original float64 exact bit patterns exported as finite exact base-10 decimals via Decimal.from_float',
  'scope':'bounded 3D objective, no unbounded/global-R3 inference, ambiguous cases remain refused',
  'cases':[]
}
for fam,n,idx in ids:
    rec=byid[fam,n,idx]
    X,y=ch23_run.generator(fam,n,rec['seed'])
    origsha=hashlib.sha256(X.tobytes()+y.tobytes()).hexdigest()
    assert origsha==rec['data_digest'],('DIGEST_MISMATCH',fam,n,idx)
    # Preserve exact float64 values, not shorter repr decimal approximations.
    rows=[{'x':[binary64_as_exact_decimal(v) for v in row], 'y':int(z)} for row,z in zip(X,y)]
    seeds=[]
    for group in rec['clusters']:
        point=[binary64_as_exact_decimal(c) for c in group['beta']]
        if all(Decimal(lo)<=Decimal(v)<=Decimal(hi) for v,(lo,hi) in zip(point,protocol['root_box'])):
            seeds.append(point)
    tag=f'{fam}_n{n}_i{idx:02d}'
    inp={'case_id':tag,'original_CH23_identity':{'family':fam,'n':n,'index':idx,'seed':rec['seed'],'data_digest':rec['data_digest'],'events':rec['events'],'ambiguous':rec['ambiguous']},'rows':rows,'bounds':protocol['root_box'],'seeds':seeds}
    blob=(json.dumps(inp,indent=2,ensure_ascii=True)+'\n').encode()
    (OUT/'inputs'/f'{tag}.json').write_bytes(blob)
    protocol['cases'].append({'id':tag,'family':fam,'n':n,'index':idx,'seed':rec['seed'],'original_digest':origsha,'events':rec['events'],'ambiguous':rec['ambiguous'],'validated_maxima_in_box':len(seeds),'exact_input_sha256':hashlib.sha256(blob).hexdigest()})

(OUT/'frozen_protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
(OUT/'frozen_protocol.sha256').write_text(hashlib.sha256((OUT/'frozen_protocol.json').read_bytes()).hexdigest()+'  frozen_protocol.json\n')
print('FROZEN',hashlib.sha256((OUT/'frozen_protocol.json').read_bytes()).hexdigest(), 'cases',len(protocol['cases']))
for c in protocol['cases']:print(c['id'],c['original_digest'][:12],c['events'],'ambiguous',c['ambiguous'],'seeds',c['validated_maxima_in_box'])