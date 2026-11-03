"""CH34 storage primitive tests anchored to frozen CH33 evidence identities.
No synthetic numerical input or optimizer substitutes are used. These tests
DO NOT test MPFR CH33 integration; that needs the original full reproduction.
"""
import errno, json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from anchor34 import AnchorLedger, GENESIS, canonical, digest

CASE='zero_balanced_n80_i00'
SOURCE='78da02b6d894d27ca7095d8a354c21024640089db629d506763f930cb1917cda'
CHECKPOINT='7547147d08c755a1411de1525fb852a7060dd5f7fcba962ca3c7d7c12d432627'
BINDING='8f'*32  # storage-only scope; never construed as real MPFR binding
ARCHIVE='9e'*32  # storage-only scope; never construed as real archive digest


def att(nodes=127, epochs=2, cp=CHECKPOINT, head=SOURCE):
    return {'case_id':CASE,'binding_sha256':BINDING,'original_head_sha256':head,
            'checkpoint_sha256':cp,'archive_sha256':ARCHIVE,'nodes':nodes,
            'archive_epochs':epochs,'replay_status':'REPLAYED_BUT_UNRESOLVED',
            'mpfr_replayed_frames':6}

class TestAnchorStorage(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.r=Path(self.temp.name)/'external_anchor';self.ledger=AnchorLedger(self.r)

    def genesis(self):
        return self.ledger.publish(att(), expected_tip_sha256=GENESIS, expected_source_head=SOURCE)

    def test_initialization_requires_external_source_pin(self):
        with self.assertRaises(ValueError):self.ledger.publish(att(),expected_tip_sha256=GENESIS)
        self.assertFalse((self.r/'HEAD').exists())

    def test_external_pin_rejects_rollback_and_mutations(self):
        first=self.genesis();self.assertEqual(self.ledger.read(expected_tip_sha256=first)['sha256'],first)
        with self.assertRaises(ValueError):self.ledger.read(expected_tip_sha256=GENESIS)
        hp=self.r/'HEAD';doc=json.loads(hp.read_text());doc['body']['nodes']=126
        doc['sha256']=digest(doc['body']);hp.write_bytes(canonical(doc)+b'\n')
        with self.assertRaises(ValueError):self.ledger.read(expected_tip_sha256=first)

    def test_immutable_history_and_explicit_tip_rotation(self):
        first=self.genesis(); second=self.ledger.publish(att(127,3,'a'*64),expected_tip_sha256=first)
        self.assertNotEqual(first,second)
        self.assertEqual(self.ledger.read(expected_tip_sha256=second)['body']['parent_sha256'],first)
        with self.assertRaises(ValueError):self.ledger.read(expected_tip_sha256=first)
        old=list((self.r/'revisions').glob('00000000_*.json'))[0];old.unlink()
        with self.assertRaises(ValueError):self.ledger.read(expected_tip_sha256=second)

    def test_fail_before_publish_retains_head_requires_explicit_cleanup(self):
        first=self.genesis()
        with self.assertRaises(OSError) as e:
            self.ledger.publish(att(cp='c'*64),expected_tip_sha256=first,fail_at='before_head')
        self.assertEqual(e.exception.errno,errno.ENOSPC)
        self.assertEqual(self.ledger.read(expected_tip_sha256=first)['sha256'],first)
        x=self.ledger.discard_pending(expected_tip_sha256=first)
        self.assertEqual(x['orphan_revisions_discarded'],1)
        second=self.ledger.publish(att(cp='c'*64),expected_tip_sha256=first)
        self.assertEqual(self.ledger.read(expected_tip_sha256=second)['sha256'],second)

    def test_fail_at_temp_retains_prev_head(self):
        first=self.genesis()
        for stage in ['revision_temp','head_temp']:
            with self.assertRaises(OSError):
                self.ledger.publish(att(cp='d'*64),expected_tip_sha256=first,fail_at=stage)
            self.assertEqual(self.ledger.read(expected_tip_sha256=first)['sha256'],first)
            self.ledger.discard_pending(expected_tip_sha256=first)

    def test_fail_after_head_rename_is_fail_closed_until_external_repin(self):
        first=self.genesis()
        with self.assertRaises(OSError):
            self.ledger.publish(att(cp='e'*64),expected_tip_sha256=first,fail_at='after_head_rename')
        with self.assertRaises(ValueError):self.ledger.read(expected_tip_sha256=first)
        new=json.loads((self.r/'HEAD').read_text())['sha256']
        rec=self.ledger.read(expected_tip_sha256=new)
        self.assertEqual(rec['body']['parent_sha256'],first)

    def test_quota_is_checked_before_mutation(self):
        d=AnchorLedger(self.r,max_ledger_bytes=8192)
        first=d.publish(att(),expected_tip_sha256=GENESIS,expected_source_head=SOURCE)
        d.max_ledger_bytes=d._size()+50
        with self.assertRaises(OSError) as e:
            d.publish(att(cp='f'*64),expected_tip_sha256=first)
        self.assertEqual(e.exception.errno,errno.ENOSPC)
        self.assertEqual(d.read(expected_tip_sha256=first)['sha256'],first)

    def test_changed_case_and_binding_rejected(self):
        first=self.genesis();a=att();a['case_id']='one_event_n80_i00'
        with self.assertRaises(ValueError):self.ledger.publish(a,expected_tip_sha256=first)
        a=att();a['binding_sha256']='b'*64
        with self.assertRaises(ValueError):self.ledger.publish(a,expected_tip_sha256=first)

    def test_duplicate_json_rejected(self):
        first=self.genesis()
        p=self.r/'HEAD';raw=p.read_bytes().replace(b'"sha256":',b'"sha256":"bad","sha256":',1)
        p.write_bytes(raw)
        with self.assertRaises(ValueError):self.ledger.read(expected_tip_sha256=first)

    def test_schema_override_and_regression_refused_before_write(self):
        first=self.genesis()
        for field,value in [('generation',777),('parent_sha256','a'*64),
                            ('nodes',True),('archive_epochs',-1),
                            ('checkpoint_sha256','invalid')]:
            a=att();a[field]=value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.ledger.publish(a,expected_tip_sha256=first)
        self.assertEqual(self.ledger.read(expected_tip_sha256=first)['sha256'],first)
        with self.assertRaises(ValueError):
            self.ledger.publish(att(nodes=126,cp='f'*64),expected_tip_sha256=first)
        with self.assertRaises(ValueError):
            self.ledger.publish(att(cp=CHECKPOINT),expected_tip_sha256=first)

    def test_orphan_record_blocks_unrelated_publication(self):
        first=self.genesis()
        with self.assertRaises(OSError):
            self.ledger.publish(att(cp='d'*64),expected_tip_sha256=first,fail_at='before_head')
        with self.assertRaises(ValueError):
            self.ledger.publish(att(cp='e'*64),expected_tip_sha256=first)
        self.ledger.discard_pending(expected_tip_sha256=first)
        new=self.ledger.publish(att(cp='e'*64),expected_tip_sha256=first)
        self.assertNotEqual(new,first)

    def test_kernel_file_size_limit_rejects_actual_write(self):
        # RLIMIT_FSIZE is a genuine Linux kernel write failure (EFBIG), not
        # an ENOSPC quota or power-loss simulation. Isolated in a subprocess.
        import os, subprocess
        first=self.genesis()
        script="import json,os,resource,signal,sys\nsys.path.insert(0,sys.argv[1]);from anchor34 import AnchorLedger\nroot,tip=sys.argv[2],sys.argv[3]\na=AnchorLedger(root)\nbody=a.read(expected_tip_sha256=tip)['body']\natt={k:v for k,v in body.items() if k not in ('version','generation','parent_sha256')}\natt['checkpoint_sha256']='a'*64\nsignal.signal(signal.SIGXFSZ,signal.SIG_IGN)\nresource.setrlimit(resource.RLIMIT_FSIZE,(128,resource.getrlimit(resource.RLIMIT_FSIZE)[1]))\ntry:a.publish(att,expected_tip_sha256=tip)\nexcept OSError as e:\n    assert e.errno in (27,122,28),e\n    print('KERNEL_REJECTED',e.errno)\nelse:raise RuntimeError('Expected kernel file-write failure')\n"
        r=subprocess.run([sys.executable,'-c',script,str(Path(__file__).resolve().parents[1]),str(self.r),first],
                         capture_output=True,text=True,timeout=8)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn('KERNEL_REJECTED',r.stdout)
        self.assertEqual(self.ledger.read(expected_tip_sha256=first)['sha256'],first)
        self.ledger.discard_pending(expected_tip_sha256=first)

    def test_symlink_and_unknown_file_rejected(self):
        first=self.genesis();(self.r/'bad.txt').write_text('x')
        with self.assertRaises(ValueError):self.ledger.read(expected_tip_sha256=first)

if __name__=='__main__':unittest.main()
