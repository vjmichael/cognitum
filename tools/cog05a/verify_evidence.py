"""Offline retained-evidence verification; no numerical kernel execution or theorem proof."""
import argparse, hashlib, json, math, re, statistics, zipfile
from fractions import Fraction
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET

HEAD = '826e4b9459e4b70413ef8f0813a4c41c2b609fae'
TARGETS = ('linux311', 'linux313', 'win311', 'win313')
STAGES = ('MEL','MELR1','MELR2','MELR3','O','P','Q','R','S','T','U')
TESTS = dict(zip('OPQRSTU',(14,14,8,19,10,10,20)))
LINKS = {'MELR3':('MELR2','calibration_sha256'),'O':('MELR1','prior_sha256'),
         **{b:(a,'prior_'+a.lower()+'_sha256') for a,b in zip('OPQRST','PQRSTU')}}

def check(ok, message):
    if not ok: raise ValueError(message)

def sha(data): return hashlib.sha256(data).hexdigest()

def verify(manifest, archives):
    rows = {}; hashes = 0; links = 0; tests = 0; exact = {}; checks = 0; intervals = 0; samples = 0
    timing = []; mel = []
    for line in Path(manifest).read_text(encoding='utf-8').splitlines():
        stage, target, aid, digest = line.split()
        check(stage in STAGES and target in TARGETS and aid.isdecimal() and re.fullmatch('[0-9a-f]{64}',digest),'manifest entry')
        key = stage,target; check(key not in rows,'duplicate manifest key')
        path = Path(archives)/f'github-actions-artifact-{aid}.zip'
        check(path.stat().st_size <= 8*1024*1024 and sha(path.read_bytes()) == digest, f'{aid}: archive digest')
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            check(len(names)==len(set(names)) and len(names)<=1000 and sum(i.file_size for i in z.infolist())<=32*1024*1024,'archive limits')
            check(all(not PurePosixPath(n).is_absolute() and '..' not in PurePosixPath(n).parts and '\\' not in n for n in names),'archive path')
            check(z.testzip() is None,'CRC')
            name = 'qualification.json' if stage.startswith('MEL') else 'receipt.json'
            raw = z.read(name); d = json.loads(raw)
            check(d['status']=='PASS' and d.get('source_sha',d.get('source_commit'))==HEAD, f'{aid}: source/status')
            check(('Linux' if target.startswith('linux') else 'Windows') in d['platform'] and d['python'].startswith('3.'+target[-2:]+'.'),'host identity')
            artifacts = d.get('artifacts',d.get('artifact_sha256',{}))
            check(set(artifacts)==set(names)-{name},'archive inventory')
            for filename, expected in artifacts.items():
                check(sha(z.read(filename))==expected, f'{aid}: {filename}')
            hashes+=len(artifacts)
            if stage in TESTS:
                totals={k:sum(int(x.get(k,0)) for x in ET.fromstring(z.read('tests.xml')).iter('testsuite')) for k in ('tests','failures','errors','skipped')}
                check(totals==d['totals']==dict(tests=TESTS[stage],failures=0,errors=0,skipped=0),'JUnit totals')
                tests+=totals['tests']
            for filename in artifacts:
                if filename.endswith(('.exact.json','.matrix.json')):
                    key2=(stage,filename); actual=artifacts[filename]
                    check(exact.setdefault(key2,actual)==actual,'cross-target exact matrix mismatch');checks+=1
            if stage=='U':
                for c in d['cases']:
                    matrix_hashes=[]; width=[]; error=[]
                    for row in c['rows']:
                        n=row['cells']; prefix=f"{c['case']}/{n}"
                        check(row['matrix_sha256']==artifacts[prefix+'.matrix.json'] and row['certificate_sha256']==artifacts[prefix+'.certificate.json'],'U hash linkage')
                        matrix_hashes.append(row['matrix_sha256']);cert=json.loads(z.read(prefix+'.certificate.json'))
                        check(cert['exact_matrix_sha256']==row['matrix_sha256'] and len(cert['rows'])==3,'certificate binding')
                        for r in cert['rows']:
                            lo,hi,x,e=map(Fraction,(r['lower'],r['upper'],r['approximation'],r['absolute_error_upper']))
                            check(0<=lo<=hi and e==max(abs(x-lo),abs(x-hi)),'rational error interval arithmetic');intervals+=1
                            if n==16:width.append(float(hi-lo));error.append(float(e))
                    check([r['cells'] for r in c['rows']]==[2,4,8,16],'mesh inventory')
                    prof={p['route']:p for p in c['profiles']};check(set(prof)=={'baseline','optimized'},'profile routes')
                    out={}
                    for route,p in prof.items():
                        check(p['matrix_hashes']==matrix_hashes and len(p['samples'])==3,'matched hash/samples')
                        for s in p['samples']:
                            check(s['peak_bytes']>=s['before_peak_bytes']>=p['baseline_peak_bytes']>0 and s['elapsed_ns']>0 and s['process_cpu_ns']>0,'resource counters');samples+=1
                        out[route]={'cpu_ns':statistics.median(s['process_cpu_ns'] for s in p['samples']), 'wall_ns':statistics.median(s['elapsed_ns'] for s in p['samples']), 'peak_bytes':max(s['peak_bytes'] for s in p['samples']), 'baseline_peak_bytes':p['baseline_peak_bytes'],'memory_method':p['memory_method']}
                    ratio=out['baseline']['cpu_ns']/out['optimized']['cpu_ns']; wall=out['baseline']['wall_ns']/out['optimized']['wall_ns']
                    check(math.isclose(ratio,c['cpu_speed_ratio'],rel_tol=1e-12) and math.isclose(wall,c['wall_speed_ratio'],rel_tol=1e-12),'reported speed ratio')
                    timing.append(dict(target=target,case=c['case'],cpu_ratio=ratio,wall_ratio=wall,maximum_final_width=max(width),maximum_final_error=max(error),**out))
            if stage=='MELR3':
                for c in d['rows']:
                    arms=c['arms'];check(set(arms)=={'adaptive','constrained','serial'},'MEL arms')
                    check(arms['adaptive']['values']==arms['constrained']['values']==arms['serial']['values'],'MEL exact matched observed values')
                    mel.append(dict(target=target,operation=c['operation'],count=c['count'],speedup=arms['serial']['elapsed_ms']/arms['adaptive']['elapsed_ms'],**{k+'_calls':len(v['calls']) for k,v in arms.items()}))
            rows[stage,target]=(sha(raw),d)
    check(set(rows)=={(s,t) for s in STAGES for t in TARGETS},'complete target grid')
    for (stage,target),(digest,d) in rows.items():
        if stage in LINKS:
            parent,field=LINKS[stage];check(d[field]==rows[parent,target][0],'same-head predecessor link');links+=1
        if stage=='U':
            r=rows['R',target][1]['artifacts']
            for case in d['cases']:
                for i,m in enumerate(case['rows']):check(m['matrix_sha256']==r[f"{case['case']}/level-{i}.exact.json"],'R/U exact matrix identity')
    return dict(source_sha=HEAD,archives=len(rows),internal_hashes=hashes,links=links,dedicated_tests=tests,exact_matrix_occurrences=checks,distinct_matrix_paths=len(exact),interval_arithmetic_checks=intervals,assembly_samples=samples,assembly=timing,mel_r3=mel,scope='archive integrity, recorded tests, matched benchmark arithmetic and rational endpoint arithmetic; not kernel rerun or independent proof replay')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--archives',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    result=verify(a.manifest,a.archives);Path(a.out).write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print({k:v for k,v in result.items() if k not in ('assembly','mel_r3')})
