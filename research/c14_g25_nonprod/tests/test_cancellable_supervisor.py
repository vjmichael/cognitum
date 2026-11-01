"""Independent standalone cancellation/receipt gate. No Lu or prod registration."""
from __future__ import annotations
import hashlib
import io
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import time
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'integration' / 'g25_cancellable_supervisor.py'
FIXTURE = ROOT / 'tests' / 'slow_worker_fixture.py'
sys.path.insert(0, str(ROOT / 'integration'))
from g25_cancellable_supervisor import (Supervisor, canonical, parse_control,
                                       verify_response, verify_source, safe_worker_environment)

COUNTS = [[[67, 35], [45, 31]], [[75, 30], [48, 39]]]
ASSUME = {'sampling_iid_supported': True, 'consistency_supported': True,
          'measurement_validity_supported': True,
          'gamma_justification': 'Pre-specified external bound based on scientific domain assumptions',
          'exchangeability_justification': 'Measured adjustment plausibly sufficient'}


def data(ident='one', counts=COUNTS):
    return {'schema_version':1, 'request_id':ident, 'action':'c14.g25.sensitivity.report',
            'counts':counts, 'gamma':.25, 'assumption_evidence':ASSUME}


def control(kind, ident='one', request=None):
    d = {'protocol_version':2,'type':kind,'request_id':ident}
    if kind == 'run': d['request'] = data(ident) if request is None else request
    return canonical(d).encode()


def launch():
    env = os.environ.copy()
    env['COGNITUM_G25_RESEARCH_OPT_IN'] = '1'
    env['OPENBLAS_NUM_THREADS'] = '1'
    env['OMP_NUM_THREADS'] = '1'
    return subprocess.Popen([sys.executable,str(SCRIPT),'--research-only'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, bufsize=0)


def send(p, c):
    p.stdin.write(c+b'\n')
    p.stdin.flush()


def event(p, seconds=8):
    readable, _, _ = select.select([p.stdout], [], [], seconds)
    assert readable, 'timeout waiting for supervisor event'
    line = p.stdout.readline()
    assert line, f'supervisor closed unexpectedly: {p.poll()}'
    return json.loads(line)


def cleanup(p):
    if p.poll() is None:
        p.stdin.close()
        try: p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill();p.wait(timeout=3)
    p.stdout.close();p.stderr.close()


def wait_done(s, max_s=6):
    stop=time.monotonic()+max_s
    while time.monotonic()<stop:
        with s.mu:
            if s.active is None: return
        time.sleep(.01)
    raise AssertionError('active child not reaped')


def test_frozen_host_guard_and_baseline_match_prior_sha256():
    assert verify_source()
    assert safe_worker_environment()['COGNITUM_G25_RESEARCH_OPT_IN']=='1'
    assert 'OPENAI_API_KEY' not in safe_worker_environment()
    assert 'PYTHONPATH' not in safe_worker_environment()


@pytest.mark.parametrize('flag,env',[(False,False),(False,True),(True,False)])
def test_supervisor_off_by_default(flag,env):
    e=os.environ.copy();e.pop('COGNITUM_G25_RESEARCH_OPT_IN',None)
    if env:e['COGNITUM_G25_RESEARCH_OPT_IN']='1'
    p=subprocess.run([sys.executable,str(SCRIPT)]+(['--research-only'] if flag else []),
       input='', text=True,capture_output=True,env=e,timeout=4)
    assert p.returncode==78 and not p.stdout


def test_complete_blackbox_result_and_retained_refusal():
    p=launch()
    try:
        send(p,control('run','valid'))
        assert event(p)['event']=='accepted'
        r=event(p);assert r['event']=='result'
        assert r['response']['host_status']=='completed'
        assert r['response']['result']['status']=='conditional_sensitivity_report_only'
        assert r['response']['automatic_causal_certification'] is False
        z = [[[67,35],[0,0]],[[75,30],[48,39]]]
        send(p,control('run','missing',data('missing',z)))
        assert event(p)['event']=='accepted'
        r=event(p);assert r['event']=='result'
        assert r['response']['host_status']=='refused'
        assert r['response']['result']['identified_set_outer95_conditional'] is None
    finally:cleanup(p)


def test_duplicate_run_and_unknown_cancel_rejected():
    p=launch()
    try:
        send(p, control('cancel','notpresent'))
        assert event(p)['code']=='unknown_or_completed_task'
        send(p, control('run','x'))
        assert event(p)['event']=='accepted'
        assert event(p)['event']=='result'
        send(p, control('run','x'))
        assert event(p)['code']=='duplicate_task_id'
    finally:cleanup(p)


def test_run_while_busy_denied_and_no_second_process(tmp_path):
    s = Supervisor(sink=io.StringIO(),worker_path=FIXTURE,verify_frozen=False,
        extra_worker_env={'COGNITUM_G25_TEST_PIDFILE':str(tmp_path/'ready')})
    try:
        s.accept(control('run','active'))
        stop=time.monotonic()+5
        while not (tmp_path/'ready').exists() and time.monotonic()<stop:time.sleep(.01)
        assert (tmp_path/'ready').exists()
        result=s.accept(control('run','blocked'))
        assert result['event']=='rejected' and result['code']=='busy'
        s.accept(control('cancel','active'))
        wait_done(s)
        outputs=[json.loads(x) for x in s.sink.getvalue().splitlines()]
        assert [x['event'] for x in outputs]==['accepted','rejected','cancellation_requested','cancelled']
        assert outputs[-1]['response'] is None
    finally: assert s.close()


def test_real_in_flight_cancel_kills_session_and_descendant(tmp_path):
    pidfile=tmp_path/'pids'
    s=Supervisor(sink=io.StringIO(),worker_path=FIXTURE,verify_frozen=False,
                 extra_worker_env={'COGNITUM_G25_TEST_PIDFILE':str(pidfile)})
    try:
        s.accept(control('run','slow'))
        end=time.monotonic()+6
        while not pidfile.is_file() and time.monotonic()<end:time.sleep(.01)
        assert pidfile.is_file(), 'fixture never reached running state'
        parent, child=map(int,pidfile.read_text().split())
        assert parent>0 and child>0
        s.accept(control('cancel','slow'))
        wait_done(s)
        emissions=[json.loads(x) for x in s.sink.getvalue().splitlines()]
        assert [x['event'] for x in emissions]==['accepted','cancellation_requested','cancelled']
        assert not any(x.get('event')=='result' for x in emissions)
        if os.name=='posix' and Path(f'/proc/{child}/stat').exists():
            # A reaped orphan can temporarily be a kernel zombie; it cannot execute.
            assert Path(f'/proc/{child}/stat').read_text().split(') ')[1][0]=='Z'
        assert not Path(f'/proc/{parent}/stat').exists()
    finally: assert s.close()


def test_cancel_before_worker_launch_is_single_terminal():
    s=Supervisor(sink=io.StringIO())
    try:
        s.accept(control('run','cancel-early'))
        s.accept(control('cancel','cancel-early'))
        wait_done(s)
        rows=[json.loads(x) for x in s.sink.getvalue().splitlines()]
        assert rows[0]['event']=='accepted'
        assert rows[-1]['event']=='cancelled'
        assert not any(x['event']=='result' for x in rows)
        assert sum(x['event']=='cancelled' for x in rows)==1
    finally: assert s.close()


@pytest.mark.parametrize('raw',[
    b'bad-json', b'{}',b'{"protocol_version":2,"type":"cancel","request_id":"x","request_id":"x"}',
    b'{"protocol_version":2,"type":"run","request_id":"x"}',
    b'{"protocol_version":2,"type":"cancel","request_id":"../path"}',
    b'{"protocol_version":2,"type":"cancel","request_id":"x","admin":true}',
    b'{"protocol_version":2,"type":"cancel","request_id":"x","gamma":NaN}',
])
def test_malformed_controls_are_rejected(raw):
    s=Supervisor(sink=io.StringIO())
    try:
        resp=s.accept(raw)
        assert resp['event']=='rejected' and resp['code']=='invalid_control_frame'
    finally: assert s.close()


def test_nested_id_and_nonresearch_action_rejected():
    s=Supervisor(sink=io.StringIO())
    try:
        v=data('notmatching')
        assert s.accept(control('run','x',v))['event']=='rejected'
        v=data('x');v['action']='c14.g25.production.promote'
        assert s.accept(control('run','x',v))['event']=='rejected'
    finally: assert s.close()


def test_untrusted_worker_response_forged_receipt_rejected(tmp_path):
    fake=tmp_path/'fake.py'
    fake.write_text("import json,sys\nsys.stdin.readline()\nprint(json.dumps({'host_status':'completed','request_id':'forged','host_receipt_sha256':'0'*64}))\n",encoding='utf-8')
    s=Supervisor(sink=io.StringIO(),worker_path=fake,verify_frozen=False)
    try:
        s.accept(control('run','x'))
        wait_done(s)
        rows=[json.loads(x) for x in s.sink.getvalue().splitlines()]
        assert rows[-1]['event']=='failed' and rows[-1]['code']=='invalid_worker_receipt'
        assert rows[-1]['response'] is None
    finally: assert s.close()


def test_timeout_reaps_child_and_refuses_result(tmp_path):
    s=Supervisor(sink=io.StringIO(),worker_path=FIXTURE,verify_frozen=False,timeout=.2)
    try:
        s.accept(control('run','slow'))
        wait_done(s,4)
        rows=[json.loads(x) for x in s.sink.getvalue().splitlines()]
        assert rows[-1]['event']=='failed' and rows[-1]['code']=='worker_timeout'
        assert rows[-1]['response'] is None
    finally: assert s.close()


def test_source_substitution_stops_admission(tmp_path):
    assert verify_source()
    with pytest.raises(RuntimeError,match='frozen_source_mismatch'):
        Supervisor(worker_path=tmp_path/'other.py',verify_frozen=True)


def test_oversized_jsonl_stops_stream():
    s=Supervisor(sink=io.StringIO())
    blob=io.BytesIO(b'A'*(1024*1024+8)+b'\n')
    code=s.serve(blob)
    assert code==65
    rows=[json.loads(x) for x in s.sink.getvalue().splitlines()]
    assert len(rows)==1 and rows[0]['event']=='rejected'
    assert rows[0]['code']=='oversized_control_stream_closed'


def test_eof_terminates_active_worker_without_result(tmp_path):
    pidfile=tmp_path/'pids'
    s=Supervisor(sink=io.StringIO(),worker_path=FIXTURE,verify_frozen=False,
                 extra_worker_env={'COGNITUM_G25_TEST_PIDFILE':str(pidfile)})
    s.accept(control('run','later'))
    end=time.monotonic()+5
    while not pidfile.exists() and time.monotonic()<end:time.sleep(.01)
    assert pidfile.exists()
    assert s.serve(io.BytesIO(b''))==0
    v=[json.loads(x) for x in s.sink.getvalue().splitlines()]
    assert v[-1]['event']=='cancelled'
    assert not any(x['event']=='result' for x in v)


def test_completed_claim_without_valid_scientific_result_is_rejected():
    from g25_cancellable_supervisor import verify_response
    raw = canonical(data('bad-worker')).encode()
    forged = {'schema_version':1,'research_only':True,'request_id':'bad-worker',
              'input_sha256':hashlib.sha256(raw).hexdigest(),
              'automatic_causal_certification':False,'production_estimator_promotion':False,
              'host_status':'completed','result':None}
    forged['host_receipt_sha256']=hashlib.sha256(canonical(forged).encode()).hexdigest()
    assert verify_response((canonical(forged)+'\n').encode(),'bad-worker',raw) is None
