#!/usr/bin/env python3
"""Separate strict-format vs bounded semantic P25 grading. Read-only receipts."""
import hashlib,json,re,statistics,sys
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from cognitum.scientific_math import _polynomial

ROOT=Path(__file__).resolve().parents[1]/'evidence'

def semantic(text,case):
    if not isinstance(text,str) or len(text)>200:return False
    token=text.strip().strip('`')
    token=re.sub(r'^ANSWER\s*=\s*','',token,flags=re.I).strip()
    # Reject extraneous prose or multiple answers. Only bounded grammar accepted.
    if case['family']=='c10_finite_bool':return token.upper()==case['expected']
    if case['family']=='c05_linear':
        return bool(re.fullmatch(r'[+-]?\d+',token)) and int(token)==int(case['expected'])
    if case['family']=='c05_precision':
        if not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d{1,3})?',token):return False
        try:return Decimal(token)==Decimal(case['expected'])
        except InvalidOperation:return False
    if case['family']=='c05_symbolic':
        token=token.lower().replace('^','**')
        token=re.sub(r'(?<=\d)(?=x)', '*',token)
        if not re.fullmatch(r'[x0-9+\-*/() .]+',token) or len(token)>160:return False
        try:return _polynomial(token)==_polynomial(case['expected'])
        except (ValueError,SyntaxError):return False
    return False

def audit(path=ROOT/'p25_multicapability_receipts.json',journal=ROOT/'p25_multicapability_partial.jsonl'):
    record=json.loads(Path(path).read_text())
    cases={x['id']:x for x in record['cases']}
    if len(cases)!=16 or len(record['cases'])!=16 or len(record['receipts'])!=64:raise ValueError('wrong benchmark coverage')
    expected_pairs={(case,rep,arm) for case in cases for rep in range(2) for arm in ('OFF','CONTEXT')}
    seen={(x['caseId'],x['repetition'],x['arm']) for x in record['receipts']}
    if seen!=expected_pairs or len(seen)!=len(record['receipts']):raise ValueError('missing or duplicate pair')
    raw_journal=[json.loads(line) for line in Path(journal).read_text().splitlines()]
    if raw_journal!=record['receipts']:raise ValueError('raw journal mismatch')
    for case in cases.values():
        if not re.fullmatch('[0-9a-f]{64}',case['requestSHA']) or not re.fullmatch('[0-9a-f]{64}',case['outputSHA']):raise ValueError('invalid backend digest')
    rows=[]
    summary={}
    for row in record['receipts']:
        case=cases[row['caseId']]
        if row['expected']!=case['expected'] or row['backendRequestSHA']!=case['requestSHA'] or row['backendOutputSHA']!=case['outputSHA'] or row['promptSHA']!=hashlib.sha256(case['prompt'].encode()).hexdigest():raise ValueError('case output or backend binding changed')
        sem=semantic(row.get('text',''),case) if row['status']=='completed' else False
        strict=bool(row['correct'])
        if strict and not sem:raise ValueError('strictly correct response is semantically incorrect')
        rows.append({**row,'strict':strict,'semantic':sem})
    for family in sorted({x['family'] for x in rows}):
        summary[family]={}
        for arm in ('OFF','CONTEXT'):
            subset=[x for x in rows if x['family']==family and x['arm']==arm]
            summary[family][arm]={'strict':sum(x['strict'] for x in subset),'semantic':sum(x['semantic'] for x in subset),'total':len(subset),'medianMs':statistics.median(x['elapsedMs'] for x in subset)}
    by={(r['caseId'],r['repetition'],r['arm']):r for r in rows}
    pairs={'gain':0,'loss':0,'both_correct':0,'both_wrong':0}
    for case in cases:
        for rep in range(2):
            off=by[(case,rep,'OFF')]['semantic'];on=by[(case,rep,'CONTEXT')]['semantic']
            if not off and on:pairs['gain']+=1
            elif off and not on:pairs['loss']+=1
            elif off and on:pairs['both_correct']+=1
            else:pairs['both_wrong']+=1
    return {'schema':'p25-multicapability-independent-audit-v1','metadata':'64 real model responses; manually supplied verified backend CONTEXT, not Lu routing. Semantic grading accepts narrowly bounded equivalent answers; strict checks requested ANSWER= format.', 'cases':len(cases),'turns':len(rows),'pairs':pairs,'families':summary,'rawSHA256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),'journalSHA256':hashlib.sha256(Path(journal).read_bytes()).hexdigest(),'rows':rows}

if __name__=='__main__':
    out=audit()
    (ROOT/'p25_multicapability_independent_audit.json').write_text(json.dumps(out,indent=2)+'\n')
    print('INDEPENDENT_P25_AUDIT',json.dumps({'pairs':out['pairs'],'families':out['families']},sort_keys=True))
