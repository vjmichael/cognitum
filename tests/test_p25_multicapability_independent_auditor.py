"""Independent multi-capability P25 auditor; no LLM or Lu host required."""
import copy,hashlib,json,re
from pathlib import Path
import pytest
from tools.audit_p25_multicapability import semantic, audit

CASES={
 'c05_linear':{'family':'c05_linear','expected':'-1'},
 'c05_symbolic':{'family':'c05_symbolic','expected':'x**2 + 5*x + 6'},
 'c05_precision':{'family':'c05_precision','expected':'0.3'},
 'c10_finite_bool':{'family':'c10_finite_bool','expected':'UNSAT'},
}
@pytest.mark.parametrize('family,raw,correct',[
 ('c05_linear','-1',True),('c05_linear','ANSWER=-1',True),('c05_linear','-2',False),
 ('c05_symbolic','x^2 + 5x + 6',True),('c05_symbolic','ANSWER=x**2+5*x+6',True),
 ('c05_symbolic','x^2+5x+7',False),('c05_symbolic','__import__("os")',False),
 ('c05_precision','ANSWER=0.30',True),('c05_precision','0.299999999999',False),
 ('c10_finite_bool','UNSAT',True),('c10_finite_bool','ANSWER=SAT',False),
 ('c10_finite_bool','SAT and UNSAT',False),
])
def test_semantic_grading(family,raw,correct):
    assert bool(semantic(raw,CASES[family])) is correct


def sample_payload():
    cases=[];rows=[]
    for j in range(16):
        cid=f'case{j}';family=list(CASES)[j%4]
        expected=CASES[family]['expected']
        case={'id':cid,'family':family,'prompt':f'Case {j} example','expected':expected,
              'requestSHA':'a'*64,'outputSHA':'b'*64}
        cases.append(case)
        for rep in range(2):
            for arm in ('OFF','CONTEXT'):
                rows.append({'caseId':cid,'family':family,'repetition':rep,'arm':arm,'promptSHA':hashlib.sha256(case['prompt'].encode()).hexdigest(),
                   'backendRequestSHA':case['requestSHA'],'backendOutputSHA':case['outputSHA'],
                   'expected':expected,'text':'ANSWER='+expected,'correct':True,'status':'completed','elapsedMs':50.0})
    return {'cases':cases,'receipts':rows}


def test_complete_and_tampered_receipts(tmp_path):
    data=sample_payload();p=tmp_path/'receipt.json';j=tmp_path/'raw.jsonl'
    def save():
        p.write_text(json.dumps(data))
        j.write_text(''.join(json.dumps(row)+'\n' for row in data['receipts']))
    save();assert audit(p,j)['pairs']=={'gain':0,'loss':0,'both_correct':32,'both_wrong':0}
    old=copy.deepcopy(data)
    for tamper in ('missing','duplicate','wrong_digest','different_expected','wrong_prompt','journal_mutated'):
        data=copy.deepcopy(old)
        if tamper=='missing':data['receipts'].pop()
        if tamper=='duplicate':data['receipts'][1]=data['receipts'][0]
        if tamper=='wrong_digest':data['receipts'][0]['backendOutputSHA']='c'*64
        if tamper=='different_expected':data['receipts'][0]['expected']='999'
        if tamper=='wrong_prompt':data['receipts'][0]['promptSHA']='0'*64
        save()
        if tamper=='journal_mutated':j.write_text('{}\n')
        with pytest.raises(ValueError):audit(p,j)
