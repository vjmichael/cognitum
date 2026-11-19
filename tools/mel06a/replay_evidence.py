"""Replay archived reference receipts and compare original model output.

This validates transcript consistency and represented mathematical results,
not signature authentication or proof of origin for arbitrary imported logs.
Does not launch workers or pretend to run a model.
"""
from pathlib import Path
import argparse
import json
from cognitum.mel import model_reference as r, admission as a, native as n, engines as e
from tools.mel06a.experiment import APP, CASES, answer


def replay(directory):
    directory=Path(directory);summary=json.loads((directory/'summary.json').read_text(encoding='utf8'))
    known={c.id:c for c in CASES};verified=0;refused=0;published=0
    for row in summary['cases']:
        case=known[row['id']];ident=case.id
        if row['expected_operation']!=case.op or row['expected_args']!=case.args:raise ValueError('fixture drift')
        raw=(directory/(ident+'-select.raw.txt')).read_text(encoding='utf8')
        if raw!=row['raw_call']:raise ValueError('raw request drift')
        baseline=answer((directory/(ident+'-baseline.raw.txt')).read_text(encoding='utf8'))
        if r.canonical(baseline)!=r.canonical(row['unassisted_answer']):raise ValueError('baseline transcript drift')
        audit=row.get('audit');feedback=row['feedback']
        if feedback['ok']:
            scope=a.Scope(**audit['scope']);op=audit['operation'];wire=bytes.fromhex(audit['request_hex']);raw_result=bytes.fromhex(audit['result_hex'])
            call=n.decode_request(wire,op) if op in n.OP else e.Call(op,wire)
            rid=call.request_id if op in n.OP else call.message.request_id
            receipt=a.Receipt(scope,rid,op,audit['descriptor_sha256'],audit['request_sha256'],'completed',raw_result,audit['result_sha256'])
            replayed,proof=r.verified_feedback(scope,call,receipt,tuple(audit['tolerance']),APP if op=='kan.evaluate' else None)
            if r.canonical(replayed)!=r.canonical(feedback) or r.canonical(proof)!=r.canonical(audit):raise ValueError('receipt replay mismatch')
            verified+=1
            raw_final=(directory/(ident+'-interpret.raw.txt')).read_text(encoding='utf8')
            if r.canonical(answer(raw_final))!=r.canonical(row['assisted_answer']):raise ValueError('final transcript drift')
            decision=r.publish_checked(raw_final,replayed,matched_intent=r.intent_matches(raw,case.op,case.args),operation=case.op,threshold=case.threshold)
            if 'publication' in row and row['publication']!=decision:raise ValueError('publication decision drift')
            if decision['ok']:published+=1
            else:refused+=1
        else:
            if row['worker_calls'] or row['assisted_answer'] is not None:raise ValueError('unexpected refused payload')
            refused+=1
    for control in summary['negative_controls']:
        if not control['blocked'] or control['worker_calls']!=0 or control['feedback']['ok']:raise ValueError('negative control drift')
        if (directory/(control['id']+'.raw.txt')).read_text(encoding='utf8')!=control['raw']:raise ValueError('negative control text drift')
    return dict(cases=len(summary['cases']),verified_receipts=verified,published=published,refused=refused,negative_controls=len(summary['negative_controls']),model_sha256=summary['model_sha256'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directories',nargs='+');args=p.parse_args()
    print(json.dumps({str(Path(d).name):replay(d) for d in args.directories},indent=2))
