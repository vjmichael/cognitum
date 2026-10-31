"""P46R8: prevent false cleanup-success exits and unbounded recovery history.

These are error-path and bounded-memory tests, NOT a real cgroup.kill gate.
"""
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from cognitum import host_recovery as rec, recovery_service as svc


class RecoveryCliHardening(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name) / 'state'
        self.state.mkdir(mode=0o700)
        self.fake_root = Path(self.temp.name) / 'fake-cgroup'
        self.fake_root.mkdir()

    def _invoke(self):
        sink=io.StringIO()
        with redirect_stdout(sink):
            code=rec.main(['--state-dir',str(self.state),'--delegated-root',str(self.fake_root),'--execute'])
        return code,json.loads(sink.getvalue())

    def test_empty_ledger_with_fake_kernel_is_refused(self):
        with patch.object(rec, 'reconcile_pending') as scan:
            code, result=self._invoke()
        self.assertEqual(code,2)
        self.assertEqual(result['status'],'FAILED_CLOSED')
        scan.assert_not_called()

    def test_readonly_kernel_is_refused_even_without_jobs(self):
        with patch.object(rec,'_kernel_root_fd',return_value=os.open(self.fake_root,os.O_RDONLY)), \
             patch.object(rec.os,'fstatvfs',return_value=type('StatVFS',(),{'f_flag':os.ST_RDONLY})()), \
             patch.object(rec,'reconcile_pending') as scan:
            code,result=self._invoke()
        self.assertEqual(code,2)
        self.assertIn('CGROUP2_READ_ONLY',result['reason'])
        scan.assert_not_called()

    def test_host_closed_marker_cannot_exit_cleanup_success(self):
        with patch.object(rec,'_kernel_root_fd',return_value=os.open(self.fake_root,os.O_RDONLY)), \
             patch.object(rec.os,'fstatvfs',return_value=type('StatVFS',(),{'f_flag':0})()), \
             patch.object(rec,'reconcile_pending',return_value=[{'status':'HOST_REPORTED_CLOSED_UNATTESTED'}]):
            code,_=self._invoke()
        self.assertEqual(code,2)

    def test_kernel_cleanup_observation_still_does_not_grant_authority(self):
        with patch.object(rec,'_kernel_root_fd',return_value=os.open(self.fake_root,os.O_RDONLY)), \
             patch.object(rec.os,'fstatvfs',return_value=type('StatVFS',(),{'f_flag':0})()), \
             patch.object(rec,'reconcile_pending',return_value=[{'status':'KERNEL_TREE_CLEARED_UNATTESTED',
                 'production_authorized':False,'independent_attestation':False}]):
            code,values=self._invoke()
        self.assertEqual(code,0)  # mock CLI returns success, NOT real kernel proof
        self.assertFalse(values['results'][0]['production_authorized'])
        self.assertFalse(values['results'][0]['independent_attestation'])

    def test_failed_cgroup_read_is_refused(self):
        with patch.object(rec,'_kernel_root_fd',side_effect=OSError('injected')), \
             patch.object(rec,'reconcile_pending') as scan:
            code,result=self._invoke()
        self.assertEqual(code,2)
        self.assertEqual(result['status'],'FAILED_CLOSED')
        scan.assert_not_called()

    def test_continuous_service_does_not_retain_unbounded_results(self):
        observed=[]
        def fake_cycle(*_args,**_kwargs):
            observed.append(1)
            return {'status':'INSPECTION_ONLY', 'records': [],'data':'a'*1024}
        with patch.object(svc,'_cycle',side_effect=fake_cycle), \
             patch.object(svc, '_lock_state', return_value=os.open(self.state,os.O_RDONLY)), \
             patch('builtins.print'):
            returned=svc.run_service(self.state,self.fake_root,inspection_only=True,
                                     interval=.05,stop=lambda: len(observed)>=4)
        self.assertEqual(len(observed),4)
        self.assertEqual(returned,[])

    def test_explicit_bounded_test_cycles_preserve_test_output(self):
        with patch.object(svc,'_cycle',return_value={'status':'INSPECTION_ONLY','records':[]}), \
             patch.object(svc, '_lock_state', return_value=os.open(self.state,os.O_RDONLY)), \
             patch('builtins.print'):
            returned=svc.run_service(self.state,self.fake_root,inspection_only=True,
                                     interval=.05,cycles=3,stop=lambda:False)
        self.assertEqual(len(returned),3)


if __name__=='__main__':unittest.main()
