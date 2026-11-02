import json,time,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
CH24=HERE.parent/'CH_C14_24'
if not CH24.exists():CH24=HERE.parent/'ch_c14_24'
sys.path.insert(0,str(CH24))
from verified_bnb import logistic_model,FirthObjective, interval_box
from improved_bounds import ImprovedObjective
from mpfr_interval import Interval as I
results=[]
for name in ('zero_balanced_n80_i00','zero_balanced_n160_i00'):
 inp=json.loads((HERE.parent/('CH_C14_25' if (HERE.parent/'CH_C14_25').exists() else 'ch_c14_25')/'inputs'/f'{name}.json').read_text())
 data=logistic_model(inp['rows']);base=FirthObjective(data);new=ImprovedObjective(data)
 box=interval_box([['-4.5','-4.49'],['0','0.01'],['0','0.01']]);
 t=time.perf_counter();g,h=new.analytic_derivatives(box);our=time.perf_counter()-t
 t=time.perf_counter();jet=base.jet(box);old=time.perf_counter()-t
 center=[I('-4.495'),I('0.005'),I('0.005')];ref=base.jet(center)
 ok=all(g[j].lo.cmp(ref.g[j].lo)<=0 and g[j].hi.cmp(ref.g[j].hi)>=0 and all(h[j][k].lo.cmp(ref.h[j][k].lo)<=0 and h[j][k].hi.cmp(ref.h[j][k].hi)>=0 for k in range(3)) for j in range(3))
 results.append(dict(case=name,box=[['-4.5','-4.49'],['0','0.01'],['0','0.01']],new_seconds=round(our,3),old_seconds=round(old,3),speedup=round(old/our,2),verified_encloses_jet_at_midpoint=ok))
 print(results[-1],flush=True)
Path('/mnt/data/CH_C14_26/hessian_profile.json').write_text(json.dumps(results,indent=2)+'\n')
