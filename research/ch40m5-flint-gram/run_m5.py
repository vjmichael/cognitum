"""CH40-M.5 original-case native fast direct Gram kernel and independent acceptance.

Reports pointwise independent verification (one worst-cap terminal leaf per case),
plus native-only full frontier diagnostic, not imported scientific certificates.
Run with --traces, --pins, --checker-dir; no substitute data.
"""
import argparse,hashlib,json,math,os,sys,time
from pathlib import Path
from fractions import Fraction as F
sys.path.insert(0,str(Path(__file__).resolve().parent))
from gram_psd import native_cap
from independent_psd_check import validate_native

def load_cases(traces,pins):
    pinned=json.loads(Path(pins).read_text())['cases']
    expected={p['case']:p['trace_sha256'] for p in pinned}
    if len(expected)!=15 or len(pinned)!=15:raise ValueError('Need 15 unique original pins')
    paths=sorted(Path(traces).glob('*_127_original_mpfr_trace.json'))
    if len(paths)!=15:raise ValueError('Need 15 original files; never substitute synthetic inputs')
    entries=[]
    for path in paths:
        name=path.name.removesuffix('_127_original_mpfr_trace.json')
        data=path.read_bytes();sha=hashlib.sha256(data).hexdigest()
        if expected.get(name)!=sha:raise ValueError('Trace SHA pin mismatch: '+name)
        cert=json.loads(data)['certificate']
        if cert['model']['d']!=3 or len(cert['model']['rows']) not in (80,160):raise ValueError('Unexpected original shape')
        entries.append((name,sha,cert))
    if {x[0] for x in entries}!=set(expected):raise ValueError('Original case mismatch')
    return entries

def cpu(func,*args):
    start=time.process_time();v=func(*args);return v,time.process_time()-start

def diagnostic(entries,checker_dir,all_leaves):
    report={'protocol':'CH40-M5-FLINT-PSD-GRAM-EXACT-LINEAR-ENDPOINTS-V1','original_cases':15,
            'scientific_release':'NO_GO','certified_global_gap_closed':False,
            'label':'One worst-case box per dataset independently checked; remaining frontier diagnostic only.',
            'cases':[]}
    for idx,(name,sha,cert) in enumerate(entries,1):
        leaves=[v for v in cert['nodes'] if not v.get('children')]
        worst=max(leaves,key=lambda n:n['upper_bound_ceil_display'])
        res,flint_cpu=cpu(native_cap,cert,worst['effective_box'])
        check,check_cpu=cpu(validate_native,cert,worst['effective_box'],res,checker_dir)
        found={
          'case':name,'trace_sha256':sha,'worst_leaf_id':worst['id'],
          'worst_leaf_historical_upper_display':worst['upper_bound_ceil_display'],
          'native_gram_upper_display':float(res['gram_upper']),
          'reference_upper_display':float(check['independent_bound']),
          'old_hadamard_display':float(res['hadamard_upper']),
          'gram_better_than_hadamard_by':float(res['hadamard_margin']),
          'native_minus_reference':float(check['upper_excess']),
          'native_cpu_seconds':round(flint_cpu,7),
          'independent_cpu_seconds':round(check_cpu,7),
          'status':check['status'],
          'improves_historical_worst_by_over_1e_7':float(res['gram_upper'])+1e-7<worst['upper_bound_ceil_display'],
          'number_of_frozen_leaves':len(leaves)}
        if all_leaves:
            changes=[];cpu_sum=flint_cpu
            for node in leaves:
                if node['id']==worst['id']:continue
                r,t=cpu(native_cap,cert,node['effective_box']);cpu_sum+=t
                gap=node['upper_bound_ceil_display']-float(r['gram_upper'])
                if gap>1e-7:changes.append({'leaf_id':node['id'],'new_minus_old':-gap})
            found['all_leaf_native_cpu_seconds']=round(cpu_sum,7)
            found['all_leaf_material_improvements_native_only']=changes
            found['all_leaves_checked_natively']=len(leaves)
        report['cases'].append(found)
        print(f'{idx:02d}/15 {name:<35s} independent PASS; Gram-Hadamard {found["gram_better_than_hadamard_by"]:.5f}, native={flint_cpu:.4f}s checker={check_cpu:.4f}s',flush=True)
    report['all15_independently_checked']=all(r['status']=='ACCEPTED_CONSERVATIVE_PSD_GRAM_UPPER' for r in report['cases'])
    report['total_native_worst_cpu_seconds']=round(sum(r['native_cpu_seconds'] for r in report['cases']),6)
    report['total_independent_worst_cpu_seconds']=round(sum(r['independent_cpu_seconds'] for r in report['cases']),6)
    report['worst_box_native_vs_checker_kernel_cpu_ratio']=round(report['total_independent_worst_cpu_seconds']/report['total_native_worst_cpu_seconds'],4)
    report['all15_gram_tighter_than_hadamard']=all(r['gram_better_than_hadamard_by']>0 for r in report['cases'])
    report['worst_box_certified_new_improvements']=sum(r['improves_historical_worst_by_over_1e_7'] for r in report['cases'])
    if all_leaves:
        report['full_frozen_frontier_leaves_native_only']=sum(r['all_leaves_checked_natively'] for r in report['cases'])
        report['all_leaves_native_only_material_improvements']=sum(len(r['all_leaf_material_improvements_native_only']) for r in report['cases'])
        report['full_frontier_independently_checked']=False
    return report

def main():
    p=argparse.ArgumentParser()
    for key in ['traces','pins','checker-dir','output']:p.add_argument('--'+key,required=True)
    p.add_argument('--all-leaves',action='store_true')
    args=p.parse_args()
    entries=load_cases(args.traces,args.pins)
    report=diagnostic(entries,args.checker_dir,args.all_leaves)
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n')
    print('Result',out,'checked',report['all15_independently_checked'],'scientific',report['scientific_release'],flush=True)
if __name__=='__main__':main()
