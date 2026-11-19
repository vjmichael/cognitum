"""Matched diagnostic CPU GGUF trials; no natural-language intent extraction."""
import argparse,json,platform
from pathlib import Path
from cognitum.mel import intent_reference as ir,model_reference as r,admission as a
from tools.mel06a.experiment import Generator,Case,APP,HDC,KAN,VFA,T,answer,description,sha,negatives
from tools.mel06a.schema_grammar import request_grammar
RULE='Return only {"answer":"above"} if definitely >=, "below" if definitely <, or "uncertain" if neither can be proved.'
VQ='Gaussian VFA axes [{"name":"x","unit":"1"}], domain [-1,1], term center [0], width [1], weight 2, constant 0, output_unit "1", points [[0.5]]. f(x)=2*exp(-0.5*x*x). Is the represented value at least '
KQ='Approved scalar KAN represents f(x)=2*exp(-x*x), grid [-1,0,1]. Evaluate at x='
CASES=(
 Case('hdc-tie','Compare probe 101101 with ordered candidates [101001,111101,000000] by Hamming distance. Return {"answer":[all minimum-distance indices, zero-based, ascending]}.','hdc.query',HDC,[0,1]),
 Case('hdc-xor','Compute binary XOR of bit strings left 10110011 and right 01101001. Return the eight-bit string in {"answer":"bits"}.','hdc.bind',{'left':'10110011','right':'01101001'},'11011010'),
 Case('kan-above',KQ+'0.5. Is the represented value at least 1.5? '+RULE,'kan.evaluate',KAN,'above',1.5),
 Case('kan-below',KQ+'1. Is the represented value at least 1.5? '+RULE,'kan.evaluate',{'points':[[1]]},'below',1.5),
 Case('vfa-ambiguous',VQ+repr(T)+'? If no certified interval is available, answer uncertain. '+RULE,'vfa.evaluate',VFA,'uncertain',T),
 Case('vfa-above',VQ+'1.2? '+RULE,'vfa.evaluate',VFA,'above',1.2))

def answer_grammar(op):
    body={'hdc.query':'"[" ws (idx (ws "," ws idx){0,7})? ws "]"','hdc.bind':'"\\\"" [01]{1,1024} "\\\""'}.get(op,'"\\\"" ("above" | "below" | "uncertain") "\\\""')
    return 'root ::= ws "{" ws "\\\"answer\\\"" ws ":" ws '+body+' ws "}" ws\nidx ::= [0-7]\nws ::= [ \\t\\n\\r]*\n'

def run_case(case,gen):
    ident=case.id; ag=gen.out/(ident+'-answer.gbnf');ag.write_text(answer_grammar(case.op),encoding='utf8')
    def generate(tag,prompt,n,grammar):
        try:return gen(tag,prompt,n,grammar)
        except (ValueError,RuntimeError):return ''
    braw=generate(ident+'-baseline',case.question,64,ag);baseline=answer(braw)
    scope=a.Scope('mel06r1','bench','cpu',ident)
    intent=ir.Intent(scope,case.op,r.canonical(case.args),case.threshold,APP.checkpoint.identity if case.op=='kan.evaluate' else None)
    row=dict(id=ident,question=case.question,operation=case.op,args=case.args,threshold=case.threshold,expected=case.answer,intent_sha256=intent.identity,baseline=baseline,baseline_correct=r.canonical(baseline)==r.canonical(case.answer))
    with ir.BoundTurn(intent,r.Allowed(r.OPS,APP)) as turn:
        g=gen.out/(ident+'-tools.gbnf');g.write_text(request_grammar(turn.schemas()),encoding='utf8')
        raw=generate(ident+'-select','Choose exactly one live tool for the task. Return only tool and arguments JSON, no final answer. Copy all input values and exact units.\n'+description(turn.schemas(),True)+'\nTask: '+case.question,256,g)
        row['raw_call']=raw;row['intent_match']=intent.matches(raw)
        try:row['selected_correctly']=r.parse_request(raw)[0]==r.NAMES[case.op]
        except ValueError:row['selected_correctly']=False
        out=turn.dispatch(raw);row['feedback']=out;row['worker_calls']=turn.worker_calls;row['audit']=turn.audit
        final=''
        if out['ok']:
            if case.threshold is not None:
                prompt='Return only one JSON answer for the original threshold question. Use these certified facts, not mental arithmetic. If lower_ge_threshold is true answer above. Else if upper_lt_threshold is true answer below. Else answer uncertain.\nFacts: '+r.canonical(out['projection'])
            else:prompt=case.question+'\nUse the exact submitted-bit result, not mental arithmetic: '+r.canonical(out['projection'])+'\nReturn only the requested JSON answer.'
            final=generate(ident+'-interpret',prompt,64,ag)
        row['raw_final']=final;row['model_answer']=answer(final)
        pub=turn.publish(final,host_fallback=True);row['publication']=pub
        row['model_correct']=bool(pub.get('ok') and pub['source']=='model_verified' and r.canonical(pub['answer'])==r.canonical(case.answer))
        row['host_correct']=bool(pub.get('ok') and r.canonical(pub['answer'])==r.canonical(case.answer))
        row['fallback']=bool(pub.get('source')=='host_verified_fallback')
    (gen.out/(ident+'.json')).write_text(json.dumps(row,indent=2),encoding='utf8')
    print(ident,'base',row['baseline_correct'],'intent',row['intent_match'],'calls',row['worker_calls'],'model',row['model_correct'],'fallback',row['fallback'],flush=True);return row

def main():
    p=argparse.ArgumentParser();p.add_argument('--driver',required=True);p.add_argument('--model',required=True);p.add_argument('--label',required=True);p.add_argument('--out',required=True);p.add_argument('--threads',type=int,default=4);p.add_argument('--case',action='append');a=p.parse_args()
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True);empty=out/'empty.gbnf';empty.write_text('',encoding='utf8');gen=Generator(a.driver,a.model,empty,out,a.threads,True,True)
    rows=[run_case(c,gen) for c in CASES if not a.case or c.id in a.case];controls=negatives(gen)
    summary=dict(model=a.label,model_sha256=sha(gen.model),driver_sha256=sha(gen.driver),platform=platform.platform(),threads=a.threads,cases=rows,negative_controls=controls,inference=gen.records,baseline_correct=sum(x['baseline_correct'] for x in rows),assisted_model_correct=sum(x['model_correct'] for x in rows),published_correct=sum(x['host_correct'] for x in rows),host_fallbacks=sum(x['fallback'] for x in rows),intent_matches=sum(x['intent_match'] for x in rows),verified_receipts=sum(x['feedback']['ok'] for x in rows),production_enabled=False)
    (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf8');print({k:v for k,v in summary.items() if k.endswith('correct') or k in ('host_fallbacks','intent_matches','verified_receipts')},flush=True)
if __name__=='__main__':main()
