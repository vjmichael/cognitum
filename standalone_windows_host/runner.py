"""Run P2Z crash/restart/rotation checks on native Windows x86-64.

Linux --insecure-test-only executes process/control-flow tests, not DPAPI/NTFS.
No real Lu integration, OS reboot, power interruption or security certification.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time

from cognitum.proto import spatial_host_recovery_readiness_pb2 as zpb
from cognitum.spatial_durable_incremental_volume import bits
from cognitum.spatial_host_recovery_readiness import P2ZHostReadiness
from tests.test_c15_t3_p2w_map_lifecycle import request
from .authority import StandaloneAuthority,AuthorityError
from .platform_io import install_windows_writer,dpapi_protect,dpapi_unprotect,reject_reparse,windows_require_ntfs,windows_restrict_acl
from .acl_audit import audit_exact_acl

EXIT={'before_journal_link':120,'before_host_commit':121,'after_host_commit':122}


def _assert_runtime(insecure):
    if os.name=='nt':
        if insecure:raise RuntimeError('INSECURE_BACKEND_DENIED_ON_WINDOWS')
        if platform.machine().lower() not in ('amd64','x86_64') or sys.maxsize <=2**32:
            raise RuntimeError('WINDOWS_X86_64_REQUIRED')
    elif not insecure:raise RuntimeError('WINDOWS_REQUIRED_OR_EXPLICIT_INSECURE_TEST_ONLY')


def worker(mode,root,insecure):
    _assert_runtime(insecure)
    install_windows_writer()
    host=StandaloneAuthority(root/'authority',insecure_test_backend=insecure,
        crash_at=mode if mode in ('before_host_commit','after_host_commit') else None)
    journal=host.journal
    if os.name=='nt':
        reject_reparse(journal);journal.mkdir(parents=True,exist_ok=True)
        windows_restrict_acl(journal)
    adapter=P2ZHostReadiness(journal,host=host)
    if mode=='before_journal_link':
        adapter.open_session()
        journal.mkdir(parents=True,exist_ok=True)
        tmp=journal/'.tmp-interrupted-test'
        with tmp.open('xb') as f:
            f.write(b'interrupted-before-record-link');f.flush();os.fsync(f.fileno())
        os._exit(EXIT[mode])
    adapter.open_session().advance(request())
    raise AssertionError('INJECTED_CRASH_DID_NOT_OCCUR')


def _case(mode,root,insecure):
    dir=root/mode;dir.mkdir()
    host=StandaloneAuthority(dir/'authority',insecure_test_backend=insecure)
    q=request(); scope=q.source_request.dynamic_request
    journal=dir/'journal'
    host.enroll(scope.conversation_id,scope.volume_id,epoch=9,journal_directory=journal)
    cmd=[sys.executable,'-m','standalone_windows_host.runner','--worker',mode,
        '--root',str(dir)]
    if insecure:cmd.append('--insecure-test-only')
    start=time.perf_counter_ns()
    child=subprocess.run(cmd,cwd=str(Path(__file__).resolve().parents[1]),
        capture_output=True,text=True,timeout=90)
    duration_ms=(time.perf_counter_ns()-start)/1e6
    if child.returncode!=EXIT[mode]:
        raise AssertionError(f'{mode}: expected exit {EXIT[mode]}, saw {child.returncode}, stderr={child.stderr[-800:]}')
    fresh=StandaloneAuthority(dir/'authority',insecure_test_backend=insecure)
    z=P2ZHostReadiness(journal,host=fresh)
    view=z.inspect()
    expected={'before_journal_link':'REJECTED','before_host_commit':'AUTHENTIC_UNANCHORED_TAIL',
              'after_host_commit':'CLEAN'}[mode]
    assert view.status==expected,(mode,view.status,view.reason)
    outcome={'crash_point':mode,'subprocess_exit_code':child.returncode,
        'post_crash_status':view.status,'child_runtime_ms':round(duration_ms,3)}
    if mode=='before_journal_link':
        assert (journal/'.tmp-interrupted-test').exists()
        outcome['replay']='BLOCKED_NO_AUTO_REPAIR'
    elif mode=='before_host_commit':
        bind=fresh.read_binding()
        proof=fresh.prepare_reconciliation(bind.external_anchor,view.candidate_anchor,
                                           view.candidate_record_sha256)
        intent=zpb.P2ZReconcileIntent(schema_version=1,expected_anchor=bind.external_anchor,
          candidate_anchor=view.candidate_anchor,candidate_record_sha256=view.candidate_record_sha256,
          key_id=bind.key_id,host_proof=proof,research_only=True)
        z.reconcile(intent)
        assert P2ZHostReadiness(journal,host=fresh).inspect().status=='CLEAN'
        # The token can never approve a second reconciliation.
        assert fresh.approve_reconciliation(bind,intent.expected_anchor,
                 intent.candidate_anchor,intent.candidate_record_sha256,intent.host_proof) is False
        outcome['replay']='INDEPENDENT_FULL_REPLAY_AFTER_EXPLICIT_APPROVAL'
        outcome['approval_once']=True
    else:
        assert z.open_session().anchor.sequence==1
        outcome['replay']='INDEPENDENT_FULL_REPLAY_AFTER_CRASH'
    if mode=='after_host_commit':
        stale=z
        next_journal=dir/'journal-epoch-10'
        previous,successor=fresh.rotate(next_journal)
        assert successor.authority_epoch==10 and previous.authority_epoch==9
        assert successor.key_id!=previous.key_id
        assert fresh.journal==next_journal
        if os.name=='nt':
            reject_reparse(next_journal);next_journal.mkdir(parents=True,exist_ok=True)
            windows_restrict_acl(next_journal)
        assert P2ZHostReadiness(next_journal,host=fresh).open_session().anchor.sequence==0
        try: stale.open_session()
        except Exception: pass
        else:raise AssertionError('STALE_EPOCH_ACCEPTED')
        fresh.revoke()
        try:fresh.read_binding()
        except AuthorityError:pass
        else:raise AssertionError('REVOKED_BINDING_ACCEPTED')
        outcome.update({'epoch_rotation':'9_TO_10_ISOLATED','stale_epoch_rejected':True,
                        'revocation_enforced':True})
    return outcome


def suite(*,insecure=False,output=None):
    _assert_runtime(insecure)
    install_windows_writer()
    dpapi=None
    if os.name=='nt':
        plain=b'cognitum-dpapi-test-'+os.urandom(16)
        sealed=dpapi_protect(plain)
        assert plain!=sealed and dpapi_unprotect(sealed)==plain
        try:
            altered = dpapi_unprotect(sealed[:-1] + bytes([sealed[-1]^1]))
        except OSError:
            pass
        else:
            # Microsoft cautions that integrity errors are not guaranteed to
            # result in one specific failure code or even a failure return.
            if altered == plain:
                raise AssertionError('DPAPI_TAMPER_WAS_ACCEPTED_AS_ORIGINAL')
        dpapi='CURRENT_USER_ROUNDTRIP_AND_TAMPER_REJECTION'
    scratch_parent=os.environ.get('COGNITUM_P2Z_SCRATCH_PARENT')
    if scratch_parent:
        parent=Path(scratch_parent).resolve(strict=True)
        if not parent.is_dir():
            raise RuntimeError('SCRATCH_PARENT_IS_NOT_DIRECTORY')
        reject_reparse(parent)
        if os.name=='nt': windows_require_ntfs(parent)
    else:
        parent=None
    with tempfile.TemporaryDirectory(prefix='cognitum-p2z-winhost-', dir=parent) as temp:
        root=Path(temp);reject_reparse(root)
        if os.name=='nt':
            windows_require_ntfs(root)
            windows_restrict_acl(root)
            acl_evidence=audit_exact_acl(root)
        else:
            acl_evidence=None
        results={k:_case(k,root,insecure) for k in EXIT}
    report={'milestone':'C15 T3 Windows host-validation harness','platform':sys.platform,
      'machine':platform.machine(),'python':sys.version.split()[0],
      'backend':'INSECURE_LINUX_CONTROL_FLOW_TEST' if insecure else 'WINDOWS_DPAPI_CURRENT_USER',
      'windows_native_executed':os.name=='nt','dpapi':dpapi,
      'journal_fs':'NTFS_CHECKED_RUNTIME' if os.name=='nt' else 'NOT_NTFS',
      'acl_audit':acl_evidence,
      'dedicated_scratch_parent_used':parent is not None,
      'real_lu_host':False,'independent_antirollback_host':False,
      'windows_power_loss_tested':False,'windows_os_reboot_tested':False,
      'real_sensors_tested':False,'recovery_crashes':results,
      'status':'WINDOWS_PROCESS_LEVEL_GATES_PASSED_NOT_CERTIFIED' if os.name=='nt' else 'PORTABLE_TEST_ONLY'}
    if output:
        path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2,sort_keys=True))
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--suite',action='store_true')
    parser.add_argument('--worker',choices=list(EXIT))
    parser.add_argument('--root',type=Path)
    parser.add_argument('--insecure-test-only',action='store_true')
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    if args.worker:
        if not args.root:parser.error('--worker requires --root')
        worker(args.worker,args.root,args.insecure_test_only)
    else:suite(insecure=args.insecure_test_only,output=args.out)

if __name__=='__main__':main()
