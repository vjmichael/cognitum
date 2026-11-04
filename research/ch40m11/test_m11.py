"""M11 real security/recovery checks. Run as privileged research coordinator.
Required external frozen CH40 originals; missing sources => explicit SKIP.
"""
from __future__ import annotations
import base64, hashlib, json, os, pathlib, shutil, sqlite3, subprocess, sys, tempfile, unittest
HERE=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from coordinator_m11 import Lab,Refusal,ROOT,HERE,invoke,PY,VERIFIER_UID,ANCHOR_UID,PRODUCER_UID

LIVE=HERE/'live15'
class OSBoundaryTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
    if not (LIVE/'lab_record.json').is_file():raise unittest.SkipTest('no original 15-case M11 live acceptance')
    cls.lab=Lab(LIVE)
 def runrole(self,role,code):
    l=self.lab
    if role=='producer':uid,sbox,ro,rw=PRODUCER_UID,l.sandbox_producer,[],[l.inputs]
    elif role=='verifier':uid,sbox,ro,rw=VERIFIER_UID,l.sandbox_ver,l.ver_ro(),[l.dbdir]
    elif role=='anchor':uid,sbox,ro,rw=ANCHOR_UID,l.sandbox_anchor,l.anchor_ro(),[l.anchor]
    else:raise ValueError(role)
    print('M11_ROLE_START',role,flush=True)
    r=invoke(uid,sbox,ro,rw,[PY,'-c',code],timeout=7)
    print('M11_ROLE_DONE',role,r.returncode,flush=True)
    self.assertEqual(r.returncode,0,r.stderr[-1200:])
    self.assertIn('M11_ISOLATED:',r.stdout)
    return r.stdout
 def test_live15_reconciled_public_only(self):
    result=self.lab.reconcile()
    self.assertEqual((result['anchored_cases'],result['children_checked']),(15,296))
    self.assertEqual(result['checkpoint_tip'],self.lab.run_anchor('status')['checkpoint_tip'])
 def test_producer_cannot_see_verifier_signer_anchor_or_source(self):
    l=self.lab
    s=self.runrole('producer',f'''import pathlib,json
p=[{str(l.priv)!r},{str(l.anchor/'anchor-state.json')!r},'/mnt/data/CH40K/traces', '/etc/shadow']
print('M11_DENIED_JSON '+json.dumps([pathlib.Path(x).exists() for x in p]))''')
    dat=json.loads([x.split('M11_DENIED_JSON ')[1] for x in s.splitlines() if x.startswith('M11_DENIED_JSON ')][0])
    self.assertEqual(dat,[False,False,False,False])
 def test_verifier_cannot_read_anchor_or_modify_frozen_source(self):
    l=self.lab
    s=self.runrole('verifier',f'''import pathlib,json
anchor=pathlib.Path({str(l.anchor/'anchor-state.json')!r})
original=pathlib.Path('/mnt/data/CH40K/CH40K_ACCEPTANCE.json')
try:
 f=original.open('ab');f.close();modified=True
except OSError:modified=False
print('M11_DENIED_JSON '+json.dumps({{'anchor_visible':anchor.exists(),'source_modified':modified}}))''')
    dat=json.loads([x.split('M11_DENIED_JSON ')[1] for x in s.splitlines() if x.startswith('M11_DENIED_JSON ')][0]);self.assertEqual(dat,{'anchor_visible':False,'source_modified':False})
 def test_anchor_cannot_read_verifier_private_key(self):
    l=self.lab
    s=self.runrole('anchor',f'''import pathlib
print('ANCHOR_SEES_SIGNER',pathlib.Path({str(l.priv)!r}).exists())''')
    self.assertIn('ANCHOR_SEES_SIGNER False',s)
 def test_process_group_watchdog_kills_isolated_descendants(self):
    l=self.lab
    with self.assertRaisesRegex(Refusal,'timed out'):
       invoke(PRODUCER_UID,l.sandbox_producer,[],[l.inputs],
              [PY,'-c',"import time;print('SLEEP_STARTED',flush=True);time.sleep(30)"],timeout=2.0)
 def test_network_namespace_blocks_tcp_and_capabilities_dropped(self):
    code='''import socket,ctypes,json,os
s=socket.socket();s.settimeout(1.0);failure=None
try:s.connect(('1.1.1.1',53))
except OSError as e:failure=e.errno
finally:s.close()
# No CAP_SYS_ADMIN: remount is disallowed after the capability drop.
l=ctypes.CDLL(None,use_errno=True)
ret=l.mount(ctypes.c_char_p(b'/usr'),ctypes.c_char_p(b'/usr'),ctypes.c_void_p(),ctypes.c_ulong(32),ctypes.c_void_p())
print('NET_CAP_JSON',json.dumps({'socket_errno':failure,'mount_errno':ctypes.get_errno(),'mount_return':ret,'uid_inside_userns':os.getuid()}))'''
    for role in ['producer','verifier','anchor']:
      s=self.runrole(role,code)
      dat=json.loads([x.split('NET_CAP_JSON ')[1] for x in s.splitlines() if x.startswith('NET_CAP_JSON ')][0])
      self.assertIn(dat['socket_errno'],[101,113,99,None],dat)
      self.assertEqual(dat['mount_return'],-1)
      self.assertEqual(dat['mount_errno'],1)
 def test_anchor_cannot_be_tricked_by_forged_or_duplicate_row(self):
    row=self.lab.dbrows()[-1]
    obj={k:row[k] for k in ('body_b64','signature_b64','tip','body_sha')}
    with self.assertRaisesRegex(Refusal,'checkpoint|anchor'):
      self.lab.run_anchor('advance',row=obj)
    obj=dict(obj);obj['signature_b64']=base64.b64encode(b'\0'*64).decode()
    with self.assertRaisesRegex(Refusal,'checkpoint|anchor'):
      self.lab.run_anchor('advance',row=obj)
    self.assertEqual(self.lab.run_anchor('status')['sequence'],15)
 def test_anchored_database_rollback_is_refused(self):
    l=self.lab
    backup=l.dbdir/'m11_checkpoint.sqlite.backup'
    shutil.copyfile(l.db,backup);os.chown(backup,VERIFIER_UID,VERIFIER_UID)
    try:
      with sqlite3.connect(l.db) as db:db.execute('DELETE FROM verified WHERE idx=14')
      with self.assertRaisesRegex(Refusal,'AHEAD_OF_CHECKPOINT_DB'):
         l.reconcile()
    finally:
      os.replace(backup,l.db)
      os.chown(l.db,VERIFIER_UID,VERIFIER_UID)
    self.assertEqual(l.reconcile()['anchored_cases'],15)
 def test_changed_producer_journal_breaks_signed_recovery(self):
    l=self.lab
    p=l.inputs/'quasi_separated_n80_i00_arb_gram.json'
    original=p.read_bytes()
    try:
      p.write_bytes(original+b'\n')
      with self.assertRaisesRegex(Refusal,'rejected recovery DB'):
        l.reconcile()
    finally:p.write_bytes(original)
    self.assertEqual(l.reconcile()['anchored_cases'],15)

class LiveCrashVerifierTests(unittest.TestCase):
 def test_sigkill_verifier_after_sqlite_commit_then_external_anchor_recovers(self):
    if not (ROOT/'CH40K/CH40K_ACCEPTANCE.json').is_file():raise unittest.SkipTest('original frozen source missing')
    p=HERE/'crash_verifier_pilot'
    if p.exists():shutil.rmtree(p)
    lab=Lab(p);lab.setup()
    r=lab.fresh_one(kill_after=1)
    self.assertIn(r.returncode,(-9,137),r.stderr+'\n'+r.stdout)
    self.assertEqual(len(lab.dbrows()),1)
    self.assertEqual(lab.run_anchor('status')['sequence'],0)
    rec=lab.reconcile()
    self.assertEqual((rec['anchored_cases'],rec['children_checked']),(1,34))
    r2=lab.fresh_one()
    self.assertEqual(r2.returncode,0,r2.stderr)
    self.assertEqual(lab.reconcile()['anchored_cases'],2)

class LiveCrashAnchorTests(unittest.TestCase):
 def test_sigkill_before_anchor_rename_reconciles_from_signed_db(self):
    if not (ROOT/'CH40K/CH40K_ACCEPTANCE.json').is_file():raise unittest.SkipTest('original frozen source missing')
    p=HERE/'crash_anchor_pilot'
    if p.exists():shutil.rmtree(p)
    lab=Lab(p);lab.setup()
    result=lab.fresh_one()
    self.assertEqual(result.returncode,0,result.stderr)
    row=lab.dbrows()[0]
    obj={k:row[k] for k in ('body_b64','signature_b64','tip','body_sha')}
    with self.assertRaisesRegex(Refusal,'anchor'):
       lab.run_anchor('advance',row=obj,extra_env={'M11_INJECT_KILL_BEFORE_ANCHOR_RENAME':'1'})
    self.assertEqual(lab.run_anchor('status')['sequence'],0)
    rec=lab.reconcile()
    self.assertEqual((rec['anchored_cases'],rec['children_checked']),(1,34))
    self.assertEqual(lab.run_anchor('status')['sequence'],1)

if __name__=='__main__':unittest.main(verbosity=2)
