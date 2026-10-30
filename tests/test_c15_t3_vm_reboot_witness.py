"""Portable research tests; no real VM boot/power interruption or trusted host."""
import copy
import json
import tempfile
from pathlib import Path
import unittest
from standalone_vm_recovery.guest import prepare,verify,snapshot_initialize,snapshot_commit,snapshot_check,GateRejected
from standalone_vm_recovery.witness import open_db,register,advance,check,WitnessRejected

class RecoveryResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.guest=self.root/'guest'
        self.db=open_db(self.root/'host-only.sqlite')
    def prep(self,scenario='reboot'):
        prepare(self.guest,scenario,allow_linux=True,boot_override='test-boot-A')
        return [json.loads((self.guest/x).read_text()) for x in ('witness-enroll.json','witness-advance.json')]
    def test_requires_different_boot_id(self):
        self.prep()
        with self.assertRaisesRegex(GateRejected,'REBOOT_NOT_OBSERVED'):
            verify(self.guest,allow_linux=True,boot_override='test-boot-A')
    def test_restart_replay_and_independent_witness(self):
        start,new=self.prep()
        self.assertEqual(register(self.db,start)['status'],'ENROLLED')
        self.assertEqual(check(self.db,new)['status'],'UNWITNESSED_AHEAD')
        self.assertEqual(advance(self.db,new)['status'],'COMMITTED')
        v=verify(self.guest,allow_linux=True,boot_override='test-boot-B')
        self.assertEqual(v['status'],'REBOOT_AND_FULL_REPLAY_PASS')
        current=json.loads((self.guest/'witness-check.json').read_text())
        self.assertEqual(check(self.db,current)['status'],'MATCH')
        self.assertEqual(check(self.db,start)['status'],'ROLLBACK_DETECTED')
    def test_refuses_existing_folder(self):
        self.prep()
        with self.assertRaisesRegex(GateRejected,'REFUSE_OVERWRITE'):
            self.prep()
    def test_reject_damaged_journal_and_unchanged_boot(self):
        self.prep()
        journal=self.guest/'journal'
        record=next(p for p in journal.iterdir() if p.is_file() and p.name[0].isdigit())
        record.write_bytes(b'corrupt')
        with self.assertRaises(Exception):
            verify(self.guest,allow_linux=True,boot_override='test-boot-B')
    def test_no_automatic_power_loss_certification(self):
        self.prep('hypervisor_powercut')
        evidence=verify(self.guest,allow_linux=True,boot_override='test-boot-B')
        self.assertEqual(evidence['hypervisor_powercut_certification'],'NOT_ESTABLISHED')
    def test_realistic_snapshot_rollback_against_off_guest_witness(self):
        snapshot_initialize(self.guest,allow_linux=True,boot_override='boot-A')
        genesis=json.loads((self.guest/'witness-enroll.json').read_text())
        register(self.db,genesis)
        # Simulate the VM snapshot of guest state only: witness DB stays outside it.
        import shutil
        saved=self.root/'snapshot-copy'
        shutil.copytree(self.guest,saved)
        snapshot_commit(self.guest,allow_linux=True)
        new=json.loads((self.guest/'witness-advance.json').read_text())
        advance(self.db,new)
        shutil.rmtree(self.guest)
        shutil.copytree(saved,self.guest)
        inspected=snapshot_check(self.guest,allow_linux=True)
        self.assertEqual(inspected['sequence'],0)
        restored=json.loads((self.guest/'witness-check.json').read_text())
        self.assertEqual(check(self.db,restored)['status'],'ROLLBACK_DETECTED')

    def test_duplicate_enrollment_rejected(self):
        start,_=self.prep();register(self.db,start)
        with self.assertRaisesRegex(WitnessRejected,'ALREADY_REGISTERED'):
            register(self.db,start)
    def test_stale_or_replayed_commit_rejected(self):
        start,step=self.prep();register(self.db,start);advance(self.db,step)
        with self.assertRaisesRegex(WitnessRejected,'STALE_OR_FORKED_UPDATE'):
            advance(self.db,step)
    def test_forged_digest_detected(self):
        start,step=self.prep();register(self.db,start);advance(self.db,step)
        forge=copy.deepcopy(step);forge['anchor_sha256']='0'*64
        self.assertEqual(check(self.db,forge)['status'],'FORK_OR_TAMPER_DETECTED')
    def test_future_or_uncommitted_not_a_pass(self):
        start,step=self.prep();register(self.db,start)
        self.assertFalse(check(self.db,step)['pass'])
        self.assertEqual(check(self.db,step)['status'],'UNWITNESSED_AHEAD')
    def test_epoch_mismatch_detected(self):
        start,step=self.prep();register(self.db,start)
        step['epoch']=10
        self.assertEqual(check(self.db,step)['status'],'EPOCH_MISMATCH')
    def test_guest_witness_does_not_accept_bad_manifest(self):
        start,_=self.prep();start['sequence']=True
        with self.assertRaisesRegex(WitnessRejected,'INVALID_SEQUENCE'):
            register(self.db,start)

if __name__=='__main__':unittest.main()
