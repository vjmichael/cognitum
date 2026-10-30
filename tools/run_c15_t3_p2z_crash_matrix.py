"""C15 T3 P2Z Linux process-termination simulation; NOT power-loss certification.

Uses a test-only file-backed external anchor, stored outside the journal. A
real host must supply independent protected key custody, durable atomic CAS,
revocation, consent and authorization. This local harness is not such a host.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from cognitum.proto import spatial_durable_incremental_volume_pb2 as ypb
from cognitum.proto import spatial_host_recovery_readiness_pb2 as zpb
from cognitum.spatial_durable_incremental_volume import genesis, bits
from cognitum.spatial_host_recovery_readiness import P2ZHostReadiness
from tests.test_c15_t3_p2w_map_lifecycle import request

KEY = b'p2z-test-only-host-secret-32-bytes-and-more'


class ExternalFileTestHost:
    def __init__(self, path, mode='normal'):
        self.path = Path(path)
        self.mode = mode
        self.proof_used = False
    def _anchor(self):
        return ypb.P2YHostAnchor.FromString(self.path.read_bytes())
    def _store(self, expected, new):
        if self.path.read_bytes() != expected: return False
        tmp=self.path.with_suffix('.tmp')
        with tmp.open('xb') as f:
            f.write(new);f.flush();os.fsync(f.fileno())
        os.replace(tmp,self.path)
        # host-anchor-store simulation, not a general Windows durability claim
        if os.name == 'posix':
            fd=os.open(self.path.parent,os.O_RDONLY)
            try:os.fsync(fd)
            finally:os.close(fd)
        return True
    def read_binding(self):
        a=self._anchor()
        return zpb.P2ZHostBinding(schema_version=1,
            conversation_id=a.conversation_id,volume_id=a.volume_id,
            authority_epoch=a.authority_epoch,key_id='test-epoch-9-key',
            external_anchor=bits(a),research_only=True)
    def release_key(self,binding):return KEY
    def commit_update(self,binding,expected,new):
        if self.mode=='before_host_commit':os._exit(92)
        committed=self._store(expected,new)
        if committed and self.mode=='after_host_commit':os._exit(93)
        return committed
    def approve_reconciliation(self,binding,expected,proposed,digest,proof):
        if proof!=b'explicit-test-approval' or self.proof_used or len(digest)!=32:
            return False
        self.proof_used=True
        return self._store(expected,proposed)


def worker(mode, journal, anchor):
    host=ExternalFileTestHost(anchor, mode)
    z=P2ZHostReadiness(journal,host=host)
    if mode=='partial_temp_file':
        z.open_session()
        p=Path(journal)/'.tmp-interrupted-before-link'
        with p.open('xb') as f:
            f.write(b'partial-observation-journal');f.flush();os.fsync(f.fileno())
        os._exit(91)
    z.open_session().advance(request())
    raise RuntimeError('the intended injected process crash did not occur')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--worker',choices=['partial_temp_file','before_host_commit','after_host_commit'])
    parser.add_argument('--journal')
    parser.add_argument('--anchor')
    parser.add_argument('--out')
    a=parser.parse_args()
    if a.worker:
        worker(a.worker,a.journal,a.anchor)
        return
    results={}
    for mode,expected_exit in [('partial_temp_file',91),('before_host_commit',92),('after_host_commit',93)]:
        with tempfile.TemporaryDirectory(prefix='c15-p2z-process-') as td:
            root=Path(td)
            journal=root/'journal'
            anchor_file=root/'external-host'/'anchor.pb'
            anchor_file.parent.mkdir()
            q=request()
            anchor_file.write_bytes(bits(genesis(q.source_request.dynamic_request.conversation_id,
                                                 q.source_request.dynamic_request.volume_id,9)))
            args=[sys.executable,str(Path(__file__).resolve()),'--worker',mode,
                  '--journal',str(journal),'--anchor',str(anchor_file)]
            p=subprocess.run(args,cwd=str(Path(__file__).resolve().parents[1]),
                             capture_output=True,text=True,timeout=40)
            if p.returncode!=expected_exit:
                raise AssertionError(f'{mode}: expected {expected_exit}, got {p.returncode}: {p.stderr[-1000:]}')
            host=ExternalFileTestHost(anchor_file)
            z=P2ZHostReadiness(journal,host=host)
            preview=z.inspect()
            expected_status={'partial_temp_file':'REJECTED',
                             'before_host_commit':'AUTHENTIC_UNANCHORED_TAIL',
                             'after_host_commit':'CLEAN'}[mode]
            if preview.status!=expected_status:
                raise AssertionError(f'{mode}: {preview.status} != {expected_status}')
            if mode=='before_host_commit':
                intent=zpb.P2ZReconcileIntent(schema_version=1,
                    expected_anchor=bits(host._anchor()),candidate_anchor=preview.candidate_anchor,
                    candidate_record_sha256=preview.candidate_record_sha256,
                    key_id='test-epoch-9-key',host_proof=b'explicit-test-approval',research_only=True)
                z.reconcile(intent)
                if z.inspect().status!='CLEAN':raise AssertionError('post-reconciliation verification failed')
            if mode=='partial_temp_file' and not (journal/'.tmp-interrupted-before-link').exists():
                raise AssertionError('unsafe auto-deletion of temp file')
            results[mode]={'process_exit_code':p.returncode,'post_crash_status':expected_status,
                           'final_anchor_sequence':host._anchor().sequence,
                           'recovery_verification':'FULL_REPLAY_PASSED' if mode!='partial_temp_file' else 'BLOCKED_PENDING_OPERATOR',
                           'real_host':False,'real_power_loss':False}
    report={'milestone':'C15 T3 P2Z','environment':sys.platform,'test_host':'TEST_ONLY_FILE_BACKED_ANCHOR',
            'power_loss_tested':False,'windows_tested':os.name=='nt','results':results}
    if a.out:
        Path(a.out).parent.mkdir(parents=True,exist_ok=True)
        Path(a.out).write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,indent=2,sort_keys=True))


if __name__=='__main__':main()
