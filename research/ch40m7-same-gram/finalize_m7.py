"""Aggregate only original all-15 already independently audited batch files.
No generation or substitution of case data.
"""
from __future__ import annotations
import hashlib,json,sys
from fractions import Fraction as F
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from launch_m7 import CASE_ORDER
from audit_m7 import replay
BATCHES=[HERE/f'batch{i}' for i in range(1,6)]
OUTPUT=HERE/'accepted'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    mapping={}
    for folder in BATCHES:
        complete=json.loads((folder/'summary_partial.json').read_text())
        accepted_cases={entry['case'] for entry in complete['rows']}
        for raw in folder.glob('*.json'):
            if raw.name.endswith('.audit.json') or raw.name.startswith('summary'):continue
            data=json.loads(raw.read_text());key=(data['case'],data['backend'])
            if data['case'] not in accepted_cases:continue  # interrupted partial row is not accepted
            if key in mapping:raise ValueError('duplicate case/engine files')
            if key[0] not in CASE_ORDER:raise ValueError('unfrozen case')
            audit=raw.with_suffix('.audit.json')
            if not audit.is_file():raise ValueError('missing audit '+raw.name)
            receipt=json.loads(audit.read_text())
            if receipt['status']!='PASS_INDEPENDENT_RATIONAL_REPLAY' or receipt['journal_tip']!=data['journal_tip']:
                raise ValueError('audit did not match')
            # Fresh read-only recomputation, not reliance on preexisting receipt.
            fresh=replay(raw)
            if fresh!=receipt:raise ValueError('audit receipt mismatch')
            if data['requested_cpu_budget_seconds']!=1.0 or data['split_cap']!=256:
                raise ValueError('comparator budget mismatch')
            mapping[key]={'raw':raw,'data':data,'receipt':receipt}
    if len(mapping)!=30 or set(mapping)!={(case,engine) for case in CASE_ORDER for engine in ('arb_gram','mpfr_gram')}:
        raise ValueError('expected 30 paired original runs')
    rows=[]
    for case in CASE_ORDER:
        a=mapping[(case,'arb_gram')]['data'];b=mapping[(case,'mpfr_gram')]['data']
        if a['trace_sha256']!=b['trace_sha256'] or a['initial_upper']!=b['initial_upper']:
            raise ValueError('not same frozen start')
        if a['splits']<1 or b['splits']<1 or a['events'][0]['parent_id']!=b['events'][0]['parent_id']:
            raise ValueError('different first branch')
        first_diffs=[]
        for i in range(2):
            ac=a['events'][0]['children'][i];bc=b['events'][0]['children'][i]
            if ac['box']!=bc['box']:raise ValueError('different first box')
            difference=abs(F(ac['local_hi'])-F(bc['local_hi']))
            if difference>F(1,10**60):raise ValueError('not same mathematical bound formula')
            first_diffs.append(float(difference))
        row={'case':case,'trace_sha256':a['trace_sha256'],
             'same_initial_upper':a['initial_upper'],
             'first_split_bound_abs_diff_float':first_diffs,
             'arb':{'splits':a['splits'],'children':a['children'],'cpu_stopwatch_seconds':a['process_cpu_including_import_input_and_online_verification'],
                    'peak_rss_kib':a['peak_ru_maxrss_kib'],'upper_reduction':a['upper_reduction'],'final_upper':a['final_upper'],
                    'overshoot_seconds':a['budget_overshoot_seconds']},
             'mpfr':{'splits':b['splits'],'children':b['children'],'cpu_stopwatch_seconds':b['process_cpu_including_import_input_and_online_verification'],
                    'peak_rss_kib':b['peak_ru_maxrss_kib'],'upper_reduction':b['upper_reduction'],'final_upper':b['final_upper'],
                    'overshoot_seconds':b['budget_overshoot_seconds']},
             'winner_at_1e-10': 'arb' if F(a['upper_reduction'])-F(b['upper_reduction'])>F(1,10**10) else ('mpfr' if F(b['upper_reduction'])-F(a['upper_reduction'])>F(1,10**10) else 'tie')}
        rows.append(row)
    # Actual child full-process resource statistics are recorded by original
    # launch metadata (partial summaries of completed batches).
    subprocess_metas={}
    for folder in BATCHES:
        p=folder/'summary_partial.json'
        if not p.is_file():raise ValueError('missing full-process receipt '+str(p))
        o=json.loads(p.read_text())
        for row in o['rows']:
            case=row['case']
            for engine,info in row['arms'].items():
                if info['status']!='ACCEPTED':raise ValueError('incomplete process')
                subprocess_metas[(case,engine)]=info
    if len(subprocess_metas)!=30:raise ValueError('not 30 measured full-process runs')
    for row in rows:
        for e,k in [('arb_gram','arb'),('mpfr_gram','mpfr')]:
            meta=subprocess_metas[(row['case'],e)];row[k]['full_child_process_cpu_seconds']=meta['full_child_process_cpu_seconds']
            row[k]['external_audit_cpu_seconds']=meta['external_auditor_cpu_seconds']
            row[k]['wall_elapsed_seconds']=meta['wall_elapsed']
            row[k]['full_pipeline_cpu_seconds']=meta['full_child_process_cpu_seconds']+meta['external_auditor_cpu_seconds']
    def total(k,f):return sum(row[k][f] for row in rows)
    stats={k:{'splits':total(k,'splits'),'children':total(k,'children'),
              'cpu_within_worker':total(k,'cpu_stopwatch_seconds'),
              'full_child_process_cpu':total(k,'full_child_process_cpu_seconds'),
              'read_only_external_audit_cpu':total(k,'external_audit_cpu_seconds'),
              'full_pipeline_cpu_including_second_audit':total(k,'full_pipeline_cpu_seconds'),
              'max_peak_rss_kib':max(row[k]['peak_rss_kib'] for row in rows)} for k in ('arb','mpfr')}
    wins={k:sum(r['winner_at_1e-10']==k for r in rows) for k in ('arb','mpfr','tie')}
    result={'protocol':'CH40-M7-ALL15-EQUAL-FORMULA-PSD-GRAM-CONTROL-V1','research_only':True,
            'data':'15 original pinned CH23 127-node/64-terminal cases','both_bound_formulas':'PSD_GRAM_DOMINANCE',
            'precision_bits':256,'requested_per_arm_cpu_after_stdlib_import_seconds':1.0,
            'max_splits':256,'cases':15,'accepted_arms':30,'independent_replayed_children':stats['arb']['children']+stats['mpfr']['children'],
            'identical_first_child_box_checks':30,'all_30_read_only_audits_pass':True,
            'wins':wins,'totals':stats,'rows':rows,
            'limits':[
              'CPU cutoff starts after standard-library imports, so whole-process CPU includes additional interpreter startup that is separately measured.',
              'One atomic split can overshoot the cutoff; actual CPU differs between arms.',
              'Online rational checks are included in the worker CPU; independent read-only replays are measured separately and must not be conflated.',
              'Original historical tree correctness inherited from previous CH40-K/J acceptance, not re-proved here.',
              'No global 0.05 convergence or causal identification follows from these trials.',
              'Producers are research-only, not authority for production activation.'
            ],'scientific_release':'NO_GO'}
    out=OUTPUT/'CH40M7_ALL15_MATCHED_GRAM.json'
    out.write_text(json.dumps(result,indent=2)+'\n')
    for case in CASE_ORDER:
        for eng in ('arb_gram','mpfr_gram'):
            a=mapping[(case,eng)];target=OUTPUT/(case+'_'+eng+'.json');target.write_bytes(a['raw'].read_bytes())
            receipt=OUTPUT/(case+'_'+eng+'.audit.json');receipt.write_text(json.dumps(a['receipt'],indent=2)+'\n')
    print(json.dumps({'cases':15,'stats':stats,'wins':wins,'verified_children':result['independent_replayed_children']},indent=2))
    return result
if __name__=='__main__':build()
