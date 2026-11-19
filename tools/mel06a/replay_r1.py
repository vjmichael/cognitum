"""Re-run recorded model requests through hardened reference turn, no inference.

Validate stored raw outputs, exact receipts and final classifications. Replay
is a real worker execution of recorded requests, not a new GGUF generation.
"""
import argparse,json
from pathlib import Path
from cognitum.mel import intent_reference as ir, model_reference as r, admission as a
from tools.mel06a.benchmark_r1 import CASES
from tools.mel06a.experiment import APP,answer,sha


def same(x,y,where):
    if r.canonical(x)!=r.canonical(y):raise ValueError('replay mismatch: '+where)


def replay(directory):
    directory=Path(directory);report=json.loads((directory/'summary.json').read_text());cases={x.id:x for x in CASES};seen=set();calls=0;fallbacks=0;pubs=0;model_correct=0
    records={x['tag']:x for x in report['inference']}
    def raw_output(tag):
        raw=(directory/(tag+'.raw.txt')).read_text(encoding='utf8')
        run=records[tag]
        if not run['eog']:
            # The generation driver retained partial output but correctly
            # returned no admitted request/answer on token-budget exhaustion.
            if run['generated_tokens'] not in (64,96,256):raise ValueError('unexpected exhausted budget')
            return ''
        return raw
    for row in report['cases']:
        key=row['id'];c=cases[key];assert key not in seen;seen.add(key)
        same(row['expected'],c.answer,key+' expected');same(row['args'],c.args,key+' args');same(row['threshold'],c.threshold,key+' threshold');same(row['question'],c.question,key+' question')
        raw=raw_output(key+'-select')
        same(raw,row['raw_call'],key+' raw call')
        baseline=raw_output(key+'-baseline');same(answer(baseline),row['baseline'],key+' baseline')
        scope=a.Scope('mel06r1','bench','cpu',key);i=ir.Intent(scope,c.op,r.canonical(c.args),c.threshold,APP.checkpoint.identity if c.op=='kan.evaluate' else None)
        same(i.identity,row['intent_sha256'],key+' intent');same(i.matches(raw),row['intent_match'],key+' binding')
        with ir.BoundTurn(i,r.Allowed(r.OPS,APP)) as t:
            out=t.dispatch(raw);same(out,row['feedback'],key+' feedback');same(t.worker_calls,row['worker_calls'],key+' calls');same(t.audit,row['audit'],key+' independent receipt and witness');calls+=t.worker_calls
            final=raw_output(key+'-interpret') if out['ok'] else ''
            same(final,row['raw_final'],key+' final');same(answer(final),row['model_answer'],key+' model answer')
            pub=t.publish(final,host_fallback=True);same(pub,row['publication'],key+' publication')
            if pub['ok']:
                same(pub['answer'],c.answer,key+' expected answer');pubs+=1
                if pub['source']=='host_verified_fallback':fallbacks+=1
                else:model_correct+=1
    for ctrl in report['negative_controls']:
        raw=raw_output(ctrl['id']);same(raw,ctrl['raw'],'negative raw')
        with r.ReferenceTurn(a.Scope('mel06a','bench','local',ctrl['id']),r.Allowed(())) as t:
            out=t.dispatch(raw);same(out,ctrl['feedback'],'negative refusal');assert t.host._seen==set() and not out['ok'] and ctrl['blocked']
    same(calls,report['verified_receipts'],'total calls');same(pubs,report['published_correct'],'published');same(model_correct,report['assisted_model_correct'],'model correctness');same(fallbacks,report['host_fallbacks'],'fallback count')
    return {'model':report['model'],'model_sha256':report['model_sha256'],'cases':len(seen),'worker_receipts_reexecuted_and_replayed':calls,'model_verified':model_correct,'host_fallbacks':fallbacks,'published_correct':pubs,'negative_controls':len(report['negative_controls'])}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directories',nargs='+');args=p.parse_args();print(json.dumps([replay(d) for d in args.directories],indent=2))
