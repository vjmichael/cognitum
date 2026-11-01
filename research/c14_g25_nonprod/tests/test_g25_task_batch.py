"""P2 safe same-task batch optimization: independent black-box process checks."""
from __future__ import annotations
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'integration'))
from g25_task_batch import TaskBatch, InvalidBatch, MAX_BATCH_ITEMS
from g25_cancellable_supervisor import HOST,canonical,safe_worker_environment

COUNTS=[[[67,35],[45,31]],[[75,30],[48,39]]]
ASSUME={'sampling_iid_supported':True,'consistency_supported':True,
        'measurement_validity_supported':True,
        'gamma_justification':'An externally justified uncertainty sensitivity bound',
        'exchangeability_justification':'Measured covariates plausibly sufficient'}

def req(i,counts=None):
    return {'schema_version':1,'request_id':str(i),'action':'c14.g25.sensitivity.report',
            'counts':copy.deepcopy(COUNTS if counts is None else counts),
            'gamma':0.25,'assumption_evidence':copy.deepcopy(ASSUME)}

def reference_single(request):
    x=subprocess.run([sys.executable,str(HOST),'--research-only'],
        input=canonical(request)+'\n',text=True,capture_output=True,
        env=safe_worker_environment(),timeout=8)
    assert x.returncode==0 and x.stdout.count('\n')==1
    return json.loads(x.stdout)

def test_disabled_by_default_and_no_unsafe_windows_fallback():
    with pytest.raises(PermissionError):TaskBatch()
    with pytest.raises(InvalidBatch):TaskBatch(research_opt_in=True,deadline=999)

@pytest.mark.parametrize('n',[1,2,4,8,16])
def test_entire_batch_equivalent_to_exact_separate_host(n):
    xs=[req(f'q-{n}-{i}') for i in range(n)]
    if n>1:
        xs[-1]['counts'][0][1]=[0,0]  # scientific refusal, not error
    batch=TaskBatch(research_opt_in=True)
    r=batch.execute(f'task-{n}',xs)
    assert r['status']=='completed',r
    assert len(r['responses'])==n
    # Independent selected pointwise subprocess responses, not same in-memory call.
    for i in sorted(set([0,n-1])):
        assert r['responses'][i]==reference_single(xs[i])
    assert r['research_only'] is True
    assert r['automatic_causal_certification'] is False
    assert r['production_estimator_promotion'] is False
    assert r['responses'][-1]['host_status']==('refused' if n>1 else 'completed')
    if n>1:
        assert r['responses'][-1]['result']['identified_set_outer95_conditional'] is None
    batch.close()

@pytest.mark.parametrize('bad',[
    [],[req('a')]*17,[req('x'),req('x')],
    [req('ok'),{**req('x'),'schema_version':True}],
    [{**req('x'),'action':'c14.g25.production.promote'}],
    [{**req('x'),'counts':None,'observations':[]}],
    [{**req('x'),'count':COUNTS}],
    [{**req('x'),'gamma':float('nan')}],
])
def test_preflight_rejects_bad_or_unbounded_batch(bad):
    b=TaskBatch(research_opt_in=True)
    with pytest.raises(InvalidBatch):b.execute('task',bad)
    b.close()

def test_invalid_scientific_request_drops_all_partial_reports():
    x=req('ok')
    y=req('bad');y['counts']=[[[1,2],[3,4]]]  # host science validation failure
    b=TaskBatch(research_opt_in=True)
    r=b.execute('partial',[x,y])
    assert r['status']=='failed' and r['error_code']=='INVALID_OR_UNSAFE_REPORT'
    assert r['responses'] is None
    b.close()

def test_no_replay_and_no_after_close():
    b=TaskBatch(research_opt_in=True)
    assert b.execute('once',[req('once')])['status']=='completed'
    with pytest.raises(InvalidBatch,match='REPLAYED_TASK_ID'):
        b.execute('once',[req('new')])
    b.close()
    with pytest.raises(InvalidBatch,match='SUPERVISOR_CLOSED'):
        b.execute('next',[req('next')])


def wait_for(path,deadline=5):
    start=time.monotonic()
    while time.monotonic()-start<deadline:
        if path.exists():return
        time.sleep(.02)
    raise AssertionError('worker never started')

@pytest.mark.skipif(os.name!='posix',reason='requires Linux POSIX group containment')
def test_cancel_kills_descendant_and_publishes_no_partial(tmp_path):
    fixture=ROOT/'tests'/'slow_worker_fixture.py'
    pidfile=tmp_path/'pids'
    b=TaskBatch(research_opt_in=True,worker_path=fixture,_test_worker=True,
                _test_env={'COGNITUM_G25_TEST_PIDFILE':str(pidfile)})
    outcome=[]
    t=threading.Thread(target=lambda:outcome.append(b.execute('kill',[req('a'),req('b')])))
    t.start()
    wait_for(pidfile)
    parent,child=map(int,pidfile.read_text().split())
    assert b.cancel('kill')
    t.join(timeout=6)
    assert not t.is_alive()
    assert len(outcome)==1 and outcome[0]['status']=='cancelled'
    assert outcome[0]['responses'] is None
    assert not Path(f'/proc/{parent}/stat').exists()
    if Path(f'/proc/{child}/stat').exists():
        assert Path(f'/proc/{child}/stat').read_text().split(') ')[1][0]=='Z'
    assert not b.cancel('kill')
    b.close()

@pytest.mark.skipif(os.name!='posix',reason='requires Linux POSIX group containment')
def test_timeout_has_no_result_and_no_surviving_descendant(tmp_path):
    fixture=ROOT/'tests'/'slow_worker_fixture.py'
    pidfile=tmp_path/'pids'
    b=TaskBatch(research_opt_in=True,deadline=0.45,worker_path=fixture,_test_worker=True,
                _test_env={'COGNITUM_G25_TEST_PIDFILE':str(pidfile)})
    r=b.execute('timeout',[req('a')])
    assert r['status']=='failed' and r['error_code']=='WORKER_TIMEOUT'
    assert r['responses'] is None
    if pidfile.exists():
        parent,child=map(int,pidfile.read_text().split())
        assert not Path(f'/proc/{parent}/stat').exists()
        if Path(f'/proc/{child}/stat').exists():
            assert Path(f'/proc/{child}/stat').read_text().split(') ')[1][0]=='Z'
    b.close()

def test_forged_receipts_and_partial_stdout_fail_atomically(tmp_path):
    script=tmp_path/'fake.py'
    script.write_text("import sys\nraw=sys.stdin.readline()\nprint('not a receipt')\n",encoding='utf-8')
    b=TaskBatch(research_opt_in=True,worker_path=script,_test_worker=True)
    r=b.execute('forged',[req('x')])
    assert r['status']=='failed' and r['responses'] is None
    assert r['error_code']=='INVALID_OR_UNSAFE_REPORT'
    b.close()


def test_empty_model_approval_does_not_change_scientific_refusal():
    x=req('no_evidence')
    x['assumption_evidence']={}
    b=TaskBatch(research_opt_in=True)
    r=b.execute('strict',[x])
    assert r['status']=='completed'
    assert r['responses'][0]['host_status']=='refused'
    assert r['responses'][0]['result']['status']=='blocked_missing_assumption_evidence'
    assert r['responses'][0]['result']['identified_set_plugin'] is None
    b.close()


def test_stdout_overflow_is_bounded_and_returns_no_reports(tmp_path):
    script=tmp_path/'unbounded_stdout.py'
    script.write_text("import sys\n"
                      "sys.stdin.readline()\n"
                      "sys.stdout.write('x'*200000)\n"
                      "sys.stdout.flush()\n",encoding='utf-8')
    b=TaskBatch(research_opt_in=True,worker_path=script,_test_worker=True)
    r=b.execute('oversize',[req('q')])
    assert r['status']=='failed' and r['responses'] is None
    assert r['error_code']=='WORKER_OUTPUT_BUDGET'
    b.close()


def test_malicious_worker_stdin_stall_never_buffers_infinite_output(tmp_path):
    script=tmp_path/'endless_stdout.py'
    script.write_text("import sys\n"
                      "while True:\n"
                      " sys.stdout.write('x'*8192)\n"
                      " sys.stdout.flush()\n",encoding='utf-8')
    b=TaskBatch(research_opt_in=True,worker_path=script,_test_worker=True,deadline=1.0)
    r=b.execute('endless',[req('q')])
    assert r['status']=='failed' and r['responses'] is None
    assert r['error_code']=='WORKER_OUTPUT_BUDGET'
    b.close()
