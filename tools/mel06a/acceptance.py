"""Native scoped reference gate; replay historical GGUF text, not fresh inference."""
import base64, hashlib, json, os, subprocess, sys, zlib
from pathlib import Path
import xml.etree.ElementTree as ET
from cognitum.mel import intent_reference as ir, model_reference as r, admission as a
from tools.mel06a.benchmark_r1 import CASES
from tools.mel06a.experiment import APP, answer
from tools.mel03b1.acceptance import check

ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'docs/research/mel06ar1'
OUT=ROOT/'cog03bc-artifacts'/'mel06ar1'
EXPECTED=dict(tests=102,failures=0,errors=0,skipped=0)

def require(ok,where):
    if not ok:raise RuntimeError(where)

def same(x,y,where):require(r.canonical(x)==r.canonical(y),'replay mismatch: '+where)
def sha(raw):return hashlib.sha256(raw).hexdigest()

def archived():
    h=json.loads((DOC/'manifest.json').read_text(encoding='utf8'))
    encoded=(DOC/'recorded_transcripts.b64').read_bytes().strip();require(len(encoded)<=20000,'archive budget')
    z=zlib.decompressobj();raw=z.decompress(base64.b64decode(encoded,validate=True),100000)
    require(z.eof and not z.unconsumed_tail and not z.unused_data,'archive bounds')
    data=json.loads(raw);require(type(data) is dict and len(data)==39,'archive shape')
    for key,value in data.items():require(type(value) is str and sha(value.encode('utf8'))==h['evidence_sha256'].get(key),'archived bytes drift: '+key)
    return h,data

def replay(label,data,expected):
    report=json.loads(data[label+'/summary.json'])
    for k in ('model','model_sha256'):same(report[k],expected[k],label+' '+k)
    records={v['tag']:v for v in report['inference']};seen=set();details=[]
    def raw(tag):
        seen.add(tag);state=records[tag];value=data[label+'/'+tag+'.raw.txt']
        if not state['eog']:
            require(state['generated_tokens'] in (64,96,256),'incomplete generation budget');return ''
        return value
    cases={v.id:v for v in CASES};used=set();calls=pubs=fallbacks=model_correct=baseline_correct=0
    for row in report['cases']:
        key=row['id'];require(key not in used,'duplicate case');used.add(key);c=cases[key]
        for k,v in [('expected',c.answer),('args',c.args),('threshold',c.threshold),('question',c.question)]:same(row[k],v,key+' '+k)
        baseline=answer(raw(key+'-baseline'));same(baseline,row['baseline'],key+' baseline');baseline_correct+=r.canonical(baseline)==r.canonical(c.answer)
        request=raw(key+'-select');same(request,row['raw_call'],key+' raw call')
        scope=a.Scope('mel06r1','bench','cpu',key)
        intent=ir.Intent(scope,c.op,r.canonical(c.args),c.threshold,APP.checkpoint.identity if c.op=='kan.evaluate' else None)
        same(intent.identity,row['intent_sha256'],key+' intent');same(intent.matches(request),row['intent_match'],key+' binding')
        with ir.BoundTurn(intent,r.Allowed(r.OPS,APP)) as turn:
            out=turn.dispatch(request);same(turn.worker_calls,row['worker_calls'],key+' calls');calls+=turn.worker_calls;same(out['ok'],row['feedback']['ok'],key+' admitted')
            final=raw(key+'-interpret') if out['ok'] else '';same(final,row['raw_final'],key+' final');same(answer(final),row['model_answer'],key+' model answer')
            pub=turn.publish(final,host_fallback=True);p=row['publication'];same(pub['ok'],p['ok'],key+' publication')
            if pub['ok']:
                same(pub['answer'],c.answer,key+' expected answer');same(pub['source'],p['source'],key+' source');same(pub['request_sha256'],p['request_sha256'],key+' exact request')
                same(pub['intent_sha256'],intent.identity,key+' publication intent');same(pub['result_sha256'],turn.audit['result_sha256'],key+' new receipt');same(pub['evidence_sha256'],out['evidence_sha256'],key+' new evidence')
                pubs+=1;fallbacks+=pub['source']=='host_verified_fallback';model_correct+=pub['source']=='model_verified'
            else:same(pub,p,key+' refusal');require(not out['ok'],'unexpected refusal')
            details.append(dict(id=key,worker_calls=turn.worker_calls,feedback=out,audit=turn.audit,publication=pub))
    controls=[]
    for ctrl in report['negative_controls']:
        key=ctrl['id'];v=raw(key);same(v,ctrl['raw'],key+' raw control')
        with r.ReferenceTurn(a.Scope('mel06a','bench','local',key),r.Allowed(())) as turn:
            out=turn.dispatch(v);same(out,ctrl['feedback'],key+' refusal');require(not out['ok'] and not turn.host._seen,'negative dispatched');controls.append(dict(id=key,feedback=out,worker_calls=0))
    require(used==set(cases) and seen==set(records) and len(controls)==2,'archived coverage')
    counts=dict(verified_receipts=calls,published_correct=pubs,assisted_model_correct=model_correct,host_fallbacks=fallbacks,baseline_correct=baseline_correct)
    for k,v in counts.items():same(v,expected[k],label+' '+k)
    return dict(model=report['model'],model_sha256=report['model_sha256'],cases=len(used),negative_controls=controls,counts=counts,details=details)

def main():
    os.chdir(ROOT);OUT.mkdir(parents=True,exist_ok=True)
    head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();hosted=os.getenv('GITHUB_ACTIONS')=='true'
    if hosted:
        require(os.getenv('COG03BC_EXPECTED_SHA')==head,'wrong checkout')
        p=json.loads((OUT.parent/'mel05c'/'receipt.json').read_text(encoding='utf8'))
        require(p['source_sha']==head and p['totals']==dict(tests=84,failures=0,errors=0,skipped=0) and p['hosted_predecessor_checked'] is True and p['compiled_descriptor_match'] is True and p['continuous_box_verified'] is True and p['production_enabled'] is False,'missing same-head MEL-05C evidence')
    m=json.loads((DOC/'native_manifest.json').read_text(encoding='utf8'));check(m,head);h,data=archived()
    collected=subprocess.check_output([sys.executable,'-m','pytest','--collect-only','-q','research_tests/mel06a'],text=True,timeout=60)
    ids=[x for x in collected.splitlines() if '::test_' in x];require(len(ids)==102 and max(map(len,ids))<=10000,'collection bounds');(OUT/'collection.log').write_text(collected,encoding='utf8')
    xml=OUT/'tests.xml';log=OUT/'tests.log'
    with log.open('w',encoding='utf8') as stream:subprocess.run([sys.executable,'-m','pytest','-q','research_tests/mel06a','--junitxml',str(xml)],stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=240)
    totals={k:sum(int(v.get(k,0)) for v in ET.parse(xml).getroot().findall('.//testsuite')) for k in EXPECTED};require(totals==EXPECTED,'test totals')
    results=[replay(label,data,expected) for label,expected in zip(('qwen05','qwen15'),h['model_trials'])]
    (OUT/'replay.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf8');check(m,head)
    hashes={p.name:sha(p.read_bytes()) for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='receipt.json'}
    (OUT/'receipt.json').write_text(json.dumps(dict(source_sha=head,totals=totals,hosted_predecessor_checked=hosted,recorded_generation_replay=True,fresh_gguf_inference=False,native_lu_accepted=False,production_enabled=False,worker_receipts=sum(v['counts']['verified_receipts'] for v in results),negative_controls=sum(len(v['negative_controls']) for v in results),git_blobs=m['git_blobs'],artifacts=hashes),indent=2)+'\n',encoding='utf8')
    print(totals,'nine actual scoped worker receipts; four refused recorded controls; historical GGUF replay, no fresh inference')

if __name__=='__main__':main()
