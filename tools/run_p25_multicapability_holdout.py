#!/usr/bin/env python3
"""P25 multi-capability exploratory LLM benchmark; Cognitum only, no Lu integration.

ON receives independently checked Cognitum output as context, NOT an authorized
Lu tool call. User prompts remain pairwise identical. Offline model endpoint
must be loopback. Every turn, including errors, is journaled.
"""
import hashlib, itertools, json, os, random, re, sys, time, urllib.request
from decimal import Decimal
from pathlib import Path
from sympy import Symbol, expand, simplify
from cognitum.scientific_math import run_inert_specialist, decode_specialist_result, _wire
from cognitum.proto import specialists_pb2 as pb, formal_backend_pb2 as fb, formal_advanced_pb2 as fa
from cognitum.formal_finite import prove_finite_frame, verify_finite_frame

HOST=os.environ.get('COGNITUM_P25_LOOPBACK_URL','http://127.0.0.1:48073/v1/chat/completions')
if not re.fullmatch(r'http://127\.0\.0\.1:[1-9][0-9]{1,4}/v1/chat/completions', HOST):
    raise ValueError('P25 endpoint must be 127.0.0.1; remote inference is not supported here')
MODEL_ID=os.environ.get('COGNITUM_P25_MODEL_ID','qwen2.5-0.5b-instruct-q2_k.gguf')
if not re.fullmatch(r'[A-Za-z0-9._/-]{1,128}', MODEL_ID):
    raise ValueError('invalid P25 model identifier')
SEED=251102
X=Symbol('x')
ROOT=Path(__file__).resolve().parents[1]/'evidence'
ROOT.mkdir(exist_ok=True)
OUT=ROOT/'p25_multicapability_receipts.json'
JOURNAL=ROOT/'p25_multicapability_partial.jsonl'


def calc(kind, request):
    frame=_wire(request)
    output=run_inert_specialist(kind,frame)
    result=decode_specialist_result(kind,output)
    return result,hashlib.sha256(frame).hexdigest(),hashlib.sha256(output).hexdigest()


def var(x):
    result=fb.Expr();result.variable=x;return result

def not_(x):
    e=fb.Expr();e.application.op=fb.NOT;e.application.args.add().CopyFrom(x);return e

def app(op,*children):
    e=fb.Expr();e.application.op=op
    for child in children:e.application.args.add().CopyFrom(child)
    return e


def finite_c10(case):
    run=fb.BackendRun(schema_version=1)
    for name in ('p','q'):run.variables.add(name=name,sort=fb.BOOL)
    p,q=var('p'),var('q')
    ex={
      'xor_and_equal':[app(fb.XOR,p,q),app(fb.EQ,p,q)],
      'or_not_p':[app(fb.OR,p,q),not_(p)],
      'implies_p_notq':[app(fb.IMPLIES,p,q),p,not_(q)],
      'xor_and_q':[app(fb.XOR,p,q),q],
    }[case]
    for a in ex:run.assertions.add().CopyFrom(a)
    frame=run.SerializeToString(deterministic=True)
    raw=prove_finite_frame(frame)
    cert=fa.FiniteCertificate.FromString(raw)
    values=[]
    for P,Q in itertools.product((False,True),repeat=2):
      ok={
      'xor_and_equal':(P^Q) and (P==Q),
      'or_not_p':(P or Q) and (not P),
      'implies_p_notq':((not P) or Q) and P and (not Q),
      'xor_and_q':(P^Q) and Q,
      }[case]
      if ok:values.append({'p':P,'q':Q})
    unsat=not values
    if unsat:
      assert cert.unsat_verified and verify_finite_frame(frame,raw)
    else:
      assert not cert.unsat_verified and cert.reason_code=='FINITE_SAT_COUNTEREXAMPLE_EXISTS'
    return 'UNSAT' if unsat else 'SAT',hashlib.sha256(frame).hexdigest(),hashlib.sha256(raw).hexdigest(),values


def dataset():
    cases=[]
    for i,(a,b,c,d) in enumerate(((2,3,5,7),(4,6,3,8),(7,-2,5,3),(9,4,6,5))):
      req=pb.LinearRequest(action='determinant');req.a.add(entries=[str(a),str(b)]);req.a.add(entries=[str(c),str(d)])
      ans,h,oh=calc('linear',req)
      expected=str(a*d-b*c)
      assert ans.scalar==expected
      cases.append({'id':f'linear-{i}','family':'c05_linear','prompt':f'Compute the determinant of the matrix [[{a},{b}],[{c},{d}]]. Reply only ANSWER=<integer>.','expected':expected,'requestSHA':h,'outputSHA':oh,'backend':'C05 linear determinant'})
    for i,expr in enumerate(('(x+2)*(x+3)','(x-4)*(x+5)','(x-3)*(x-7)','(x+6)*(x-2)')):
      ans,h,oh=calc('symbolic',pb.SymbolicRequest(expression=expr,action='expand'))
      expected=ans.polynomial
      assert simplify(expand(expr.replace('^','**'))-expand(expected))==0
      cases.append({'id':f'symbolic-{i}','family':'c05_symbolic','prompt':f'Expand the polynomial {expr} and simplify. Reply only ANSWER=<polynomial in x>.','expected':expected,'requestSHA':h,'outputSHA':oh,'backend':'C05 symbolic polynomial'})
    for i,(a,b) in enumerate((('0.00000123456789','0.00000876543211'),('0.1234567890123','0.8765432109877'),('888888.888888','111111.111112'),('0.000000000314159','0.000000000271828'))):
      ans,h,oh=calc('precision',pb.PrecisionRequest(action='add',left=a,right=b,digits=50))
      expected=str(Decimal(a)+Decimal(b));assert Decimal(ans.decimal)==Decimal(expected)
      cases.append({'id':f'precision-{i}','family':'c05_precision','prompt':f'Calculate {a} + {b} exactly as a decimal. Reply only ANSWER=<decimal>.','expected':ans.decimal,'requestSHA':h,'outputSHA':oh,'backend':'C05 precision decimal'})
    questions={
    'xor_and_equal':'Boolean P and Q must both satisfy (P XOR Q) and (P equals Q). Is there an assignment satisfying both?',
    'or_not_p':'Boolean P and Q must both satisfy (P OR Q) and (NOT P). Is there an assignment satisfying both?',
    'implies_p_notq':'Boolean P and Q must all satisfy (P implies Q), P, and (NOT Q). Is there an assignment satisfying all three?',
    'xor_and_q':'Boolean P and Q must both satisfy (P XOR Q) and Q. Is there an assignment satisfying both?',
    }
    for i,(key,prompt) in enumerate(questions.items()):
      expected,h,oh,witnesses=finite_c10(key)
      cases.append({'id':f'finite-{i}','family':'c10_finite_bool','prompt':prompt+' Reply only ANSWER=SAT or ANSWER=UNSAT.', 'expected':expected,'requestSHA':h,'outputSHA':oh,'backend':'C10 finite certificate + independent truth table','witnessCount':len(witnesses)})
    assert len(cases)==16
    return cases


def grade(text,case):
    matches=re.findall(r'(?im)\bANSWER\s*=\s*([^\r\n]+)',text)
    if not matches:return False
    value=matches[-1].strip().strip('`* .$')
    try:
      if case['family']=='c05_symbolic':
        if len(value)>160 or not re.fullmatch(r'[xX0-9+\-*/^() .]+',value):return False
        return simplify(expand(value.replace('^','**'))-expand(case['expected']))==0
      if case['family']=='c10_finite_bool':return value.upper()==case['expected']
      if case['family']=='c05_precision':return Decimal(value)==Decimal(case['expected'])
      if case['family']=='c05_linear':return int(value)==int(case['expected'])
    except Exception:return False
    return False


def chat(case,with_context):
    instruction='Give the final answer only in the requested ANSWER=... format. No explanation.'
    messages=[{'role':'system','content':instruction}]
    if with_context:
      messages.append({'role':'system','content':'Verified Cognitum computational evidence (separate specialist output, not user input): '+case['backend']+' result = '+case['expected']+'. Use it in the answer if relevant; do not claim to have run a tool.'})
    messages.append({'role':'user','content':case['prompt']})
    payload=json.dumps({'model':MODEL_ID,'messages':messages,'temperature':0,'seed':12001,'max_tokens':96,'stream':False}).encode()
    request=urllib.request.Request(HOST,payload,{'Content-Type':'application/json'},method='POST')
    tic=time.perf_counter()
    try:
      with urllib.request.urlopen(request,timeout=70) as response:
        body=response.read(128*1024)
      obj=json.loads(body)
      text=obj['choices'][0]['message']['content']
      return {'status':'completed','text':text,'correct':bool(grade(text,case)),'elapsedMs':round((time.perf_counter()-tic)*1000,1),'tokens':obj.get('usage',{}),'finishReason':obj['choices'][0].get('finish_reason')}
    except Exception as exc:
      return {'status':'failed','errorType':type(exc).__name__,'correct':False,'elapsedMs':round((time.perf_counter()-tic)*1000,1)}


def main():
    cases=dataset(); tasks=[]
    for case in cases:
      for rep in range(2):
        for arm in ('OFF','CONTEXT'):
          tasks.append((case,rep,arm))
    random.Random(SEED).shuffle(tasks)
    records=[]
    JOURNAL.write_text('')
    started=time.time()
    for n,(case,rep,arm) in enumerate(tasks,1):
      result=chat(case,arm=='CONTEXT')
      record={'caseId':case['id'],'family':case['family'],'repetition':rep,'arm':arm,'promptSHA':hashlib.sha256(case['prompt'].encode()).hexdigest(),'backendRequestSHA':case['requestSHA'],'backendOutputSHA':case['outputSHA'],'expected':case['expected'],**result}
      records.append(record)
      with JOURNAL.open('a') as f:f.write(json.dumps(record,sort_keys=True)+'\n')
      print(f'P25-MULTI {n:02d}/{len(tasks)} {case["id"]} {arm} rep={rep} correct={result["correct"]} status={result["status"]} latency={result["elapsedMs"]}ms',flush=True)
    coverage={}
    for family in sorted(set(c['family'] for c in cases)):
      coverage[family]={}
      for arm in ('OFF','CONTEXT'):
        rows=[r for r in records if r['family']==family and r['arm']==arm]
        coverage[family][arm]={'correct':sum(r['correct'] for r in rows),'total':len(rows),'failed':sum(r['status']=='failed' for r in rows),'medianMs':sorted(r['elapsedMs'] for r in rows)[len(rows)//2]}
    complete={'schema':'p25-multicapability-model-context-v1','notice':'Not Lu routing; CONTEXT is manually supplied independently verified Cognitum result. One real local 0.5B model only.','model':MODEL_ID,'seed':SEED,'repetitions':2,'distinctCases':len(cases),'cases':cases,'receipts':records,'coverage':coverage,'wallSeconds':round(time.time()-started,2)}
    OUT.write_text(json.dumps(complete,indent=2)+'\n')
    print('P25-MULTI-RESULT',json.dumps(coverage,sort_keys=True),flush=True)

if __name__=='__main__':main()
