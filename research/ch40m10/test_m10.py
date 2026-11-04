"""M.10 fail-closed recovery tests. Original-case checks skip, never pass, if frozen fixtures unavailable."""
from __future__ import annotations
import base64
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

HERE=Path(__file__).resolve().parent
ROOT=Path(os.environ.get('CH40M10_WORKSPACE','/mnt/data')).resolve()
sys.path.insert(0,str(HERE))
import m10_durable_auditor as m

FULL=HERE/'hardened15/ledger.sqlite'
PUBLIC=HERE/'local_trust/verifier-public.key'
INPUTS=ROOT/'CH40M9/full15/journals'

class ContractTests(unittest.TestCase):
    def test_protocol_fail_closed(self):
        self.assertEqual(len(m.CASE_ORDER),15)
        with self.assertRaisesRegex(m.Refusal,'duplicates'):
            m.manifest([m.CASE_ORDER[0]]*2,ROOT,'a'*64)
    def test_canonical_rejects_nonfinite(self):
        with self.assertRaises(ValueError):m.canonical({'x':float('nan')})
    def test_secret_not_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            d=Path(td)/'trust'
            pub,sec=m.make_keys(d)
            with self.assertRaisesRegex(m.Refusal,'overwrite'):
                m.make_keys(d)
            self.assertEqual(len(pub.read_bytes()),32)
            self.assertEqual(len(sec.read_bytes()),32)
    def test_signing_key_is_owner_only(self):
        if os.name!='posix':self.skipTest('POSIX private key mode check')
        with tempfile.TemporaryDirectory() as td:
            _,sec=m.make_keys(Path(td)/'trust')
            os.chmod(sec,0o644)
            with self.assertRaisesRegex(m.Refusal,'owner-only'):
                m.load_private(sec)
    def test_empty_valid_db_never_claims_completed(self):
        with tempfile.TemporaryDirectory() as td:
            conn=m.open_db(Path(td)/'db.sqlite')
            try:
                man={'cases':[],'trusted_verifier_public_sha256':'0'*64}
                gen=m.init_or_check(conn,man)
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM verified').fetchone()[0],0)
                with self.assertRaisesRegex(m.Refusal,'manifest'):
                    m.init_or_check(conn,{'different':True})
            finally:conn.close()

@unittest.skipUnless(m.AUDITOR_AVAILABLE and FULL.is_file() and PUBLIC.is_file() and INPUTS.is_dir() and (ROOT/'CH40K/traces').is_dir(),
    'original frozen cases, trusted test public key or M.10 signed research database absent')
class OriginalEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pins=m._load_pins();cls.public,cls.fp=m.load_public(PUBLIC)
    def new_copy(self):
        tmp=tempfile.TemporaryDirectory();p=Path(tmp.name)
        db=p/'ledger.sqlite';shutil.copy2(FULL,db)
        return tmp,db
    def verify(self,db,inputs=INPUTS,public=None,cases=m.CASE_ORDER):
        cn=sqlite3.connect(str(db))
        try:
            genesis=m.init_or_check(cn,m.manifest(cases,ROOT,self.fp))
            return m.verify_rows(cn,inputs,cases,public or self.public,genesis,self.pins)
        finally:cn.close()
    def test_all15_signed_source_pinned_recovery(self):
        s=self.verify(FULL)
        self.assertEqual((s['completed'],s['children_checked']),(15,296))
        self.assertEqual(len(s['body_hashes']),15)
    def test_wrong_public_key_fails(self):
        tmp,db=self.new_copy()
        try:
            with tempfile.TemporaryDirectory() as k:
                wrong,_=m.make_keys(Path(k)/'trust')
                pub,_=m.load_public(wrong)
                with self.assertRaisesRegex(m.Refusal,'signature'):
                    self.verify(db,public=pub)
        finally:tmp.cleanup()
    def test_body_mutation_with_original_signature_refused(self):
        tmp,db=self.new_copy()
        try:
            with closing(sqlite3.connect(db)) as c:
                body=c.execute('SELECT body FROM verified WHERE idx=0').fetchone()[0]
                altered=body.replace(b'NO_GO',b'NO_GX')
                self.assertNotEqual(body,altered)
                c.execute('UPDATE verified SET body=? WHERE idx=0',(altered,));c.commit()
            with self.assertRaisesRegex(m.Refusal,'altered checkpoint'):
                self.verify(db)
        finally:tmp.cleanup()
    def test_forged_signature_refused_even_with_rehashed_body(self):
        tmp,db=self.new_copy()
        try:
            with closing(sqlite3.connect(db)) as c:
                blob=c.execute('SELECT body FROM verified WHERE idx=0').fetchone()[0]
                obj=json.loads(blob);obj['scientific_release']='GO'
                data=m.canonical(obj)
                c.execute('UPDATE verified SET body=?,body_sha=? WHERE idx=0',(data,m.digest(data)));c.commit()
            with self.assertRaisesRegex(m.Refusal,'signature'):
                self.verify(db)
        finally:tmp.cleanup()
    def test_deleted_middle_checkpoint_is_refused(self):
        tmp,db=self.new_copy()
        try:
            with closing(sqlite3.connect(db)) as c:c.execute('DELETE FROM verified WHERE idx=3');c.commit()
            with self.assertRaisesRegex(m.Refusal,'deleted, reordered'):
                self.verify(db)
        finally:tmp.cleanup()
    def test_mutated_input_journal_refused_even_if_wellformed(self):
        tmp,db=self.new_copy()
        try:
            inputs=Path(tmp.name)/'journals';inputs.mkdir()
            for original in INPUTS.glob('*.json'):(inputs/original.name).symlink_to(original)
            bad=inputs/(m.CASE_ORDER[0]+'_arb_gram.json');bad.unlink()
            bad.write_bytes((INPUTS/bad.name).read_bytes()+b'\n')
            with self.assertRaisesRegex(m.Refusal,'journal changed'):
                self.verify(db,inputs)
        finally:tmp.cleanup()
    def test_source_pin_or_signer_identity_cannot_change(self):
        tmp,db=self.new_copy()
        try:
            with closing(sqlite3.connect(db)) as c:
                row=c.execute('SELECT manifest FROM meta WHERE id=1').fetchone()[0]
                obj=json.loads(row);obj['trusted_verifier_public_sha256']='0'*64
                c.execute('UPDATE meta SET manifest=? WHERE id=1',(m.canonical(obj),));c.commit()
            with self.assertRaisesRegex(m.Refusal,'manifest'):
                self.verify(db)
        finally:tmp.cleanup()
    def test_real_sigkill_in_open_sqlite_transaction_rolls_back(self):
        tmp,db=self.new_copy()
        try:
            marker=Path(tmp.name)/'open.txt'
            code=("import sqlite3,sys,time;from pathlib import Path;"
                  "c=sqlite3.connect(sys.argv[1],isolation_level=None);"
                  "c.execute('BEGIN IMMEDIATE');"
                  "c.execute('UPDATE verified SET body=? WHERE idx=0',(b'BAD',));"
                  "Path(sys.argv[2]).write_text('OPEN');"
                  "time.sleep(30)")
            p=subprocess.Popen([sys.executable,'-c',code,str(db),str(marker)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
            try:
                for _ in range(100):
                    if marker.is_file():break
                    if p.poll() is not None:break
                    time.sleep(.04)
                self.assertTrue(marker.is_file(),'subprocess did not enter SQLite transaction')
                p.kill();self.assertEqual(p.wait(timeout=5),-signal.SIGKILL)
            finally:
                if p.poll() is None:p.kill();p.wait()
                if p.stderr is not None:p.stderr.close()
            s=self.verify(db)
            self.assertEqual(s['completed'],15)
        finally:tmp.cleanup()
    def test_signing_receipt_with_altered_proof_refused(self):
        case=m.CASE_ORDER[0]
        with closing(sqlite3.connect(FULL)) as c:
            payload=json.loads(c.execute('SELECT body FROM verified WHERE idx=0').fetchone()[0])
        receipt=payload['audited_receipt']
        obj=json.loads(json.dumps(receipt))
        obj['propositions'][0]['independent_upper']='-999'
        with self.assertRaisesRegex(m.Refusal,'altered proof proposition'):
            m.receipt_check(obj,case,payload['original_trace_sha256'],payload['journal_sha256'])
    def test_checkpoint_tail_rollback_requires_external_anchor(self):
        tmp,db=self.new_copy()
        try:
            original=self.verify(db)
            with closing(sqlite3.connect(db)) as c:c.execute('DELETE FROM verified WHERE idx=14');c.commit()
            # A valid signed prefix is not in itself evidence of latest state.
            rolled=self.verify(db)
            self.assertEqual(rolled['completed'],14)
            with self.assertRaisesRegex(m.Refusal,'rollback'):
                m.run(db,INPUTS,list(m.CASE_ORDER),PUBLIC,expected_tip=original['tip'])
        finally:tmp.cleanup()

    def test_signature_recovery_does_not_recompute_rational_mathematics(self):
        from unittest.mock import patch
        with patch.object(m,'run_batch',side_effect=AssertionError('unexpected rational recomputation')):
            outcome=m.run(FULL,INPUTS,list(m.CASE_ORDER),PUBLIC)
        self.assertEqual(outcome['cases_newly_independently_audited'],0)
        self.assertEqual(outcome['verified_child_checks'],296)

    def test_frozen_no_go_is_preserved(self):
        result=m.run(FULL,INPUTS,list(m.CASE_ORDER),PUBLIC,None)
        self.assertEqual((result['completed_cases'],result['cases_newly_independently_audited'],result['verified_child_checks']),(15,0,296))
        self.assertEqual(result['scientific_release'],'NO_GO')

if __name__=='__main__':unittest.main(verbosity=2)
