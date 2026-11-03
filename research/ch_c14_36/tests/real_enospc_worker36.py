"""Real, isolated Linux kernel ENOSPC from an actual full tmpfs mount.

Invoked under `unshare -Urnm` and operates only in a private user/mount
namespace; it does not consume host /dev/shm capacity. No synthetic math.
"""
import argparse, errno, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
D=Path(__file__).resolve().parents[1];sys.path.insert(0,str(D.parent/'CH_C14_35'))
from trust35 import GENESIS,WitnessStore,atomic,canonical,shaobj,strict,verify_chain

def sample(case):
    return {'case_id':case,'binding_sha256':'e'*64,'original_head_sha256':'a'*64,
            'checkpoint_sha256':'b'*64,'archive_sha256':'c'*64,'nodes':127,
            'archive_epochs':2,'mpfr_replayed_frames':6,'proof_replayed':True,
            'scientific_release':'NO_GO','verified_source':'original_CH23_independent_MPFR_224'}

def run(reserve):
    top=Path(tempfile.mkdtemp(prefix='ch36-private-mount-'))
    mnt=top/'mount';mnt.mkdir();mounted=False
    try:
        mount=subprocess.run(['mount','-t','tmpfs','-o','size=256k,nr_inodes=500','tmpfs',str(mnt)],
                             capture_output=True,text=True)
        if mount.returncode:raise RuntimeError('tmpfs mount unavailable: '+mount.stderr)
        mounted=True
        root=mnt/'signer';key=WitnessStore.provision(root)
        first=WitnessStore(root).publish(sample('first_original_metadata'),expected_tip=GENESIS)
        old=first['tip']
        atomic(root,'trusted_tip.json',canonical({'tip':old,'fingerprint':key['fingerprint_sha256']})+b'\n',prefix='tip')
        # A concurrent reader holding the old HEAD open retains its storage
        # across atomic replacement. This makes post-HEAD ENOSPC reachable,
        # rather than letting unlink immediately free the old 4 KiB page.
        held_head=os.open(root/'HEAD',os.O_RDONLY) if reserve==8192 else None
        fs=os.statvfs(mnt);block=fs.f_frsize;available=fs.f_bavail*block
        amount=(available-reserve)//block*block
        if amount<=0:raise ValueError('Not enough space to run isolated test')
        fd=os.open(mnt/'full',os.O_CREAT|os.O_WRONLY|os.O_EXCL,0o600)
        try:os.posix_fallocate(fd,0,amount)
        finally:os.close(fd)
        fs=os.statvfs(mnt);actual_left=fs.f_bavail*fs.f_frsize
        if actual_left>reserve+block:raise ValueError('Did not fill isolated tmpfs sufficiently')
        fail=None;phase=None
        try:
            result=WitnessStore(root).publish(sample('second_original_metadata'),expected_tip=old)
            phase='trusted_tip'
            atomic(root,'trusted_tip.json',canonical({'tip':result['tip'],'fingerprint':key['fingerprint_sha256']})+b'\n',prefix='tip')
        except OSError as e:fail=e.errno
        if fail!=errno.ENOSPC:raise AssertionError(f'Expected REAL ENOSPC got {fail}; reserve={reserve},phase={phase}')
        pub=(root/'public.ed25519.pem').read_bytes()
        pinned=json.loads((root/'trusted_tip.json').read_bytes())['tip']
        if pinned!=old:raise AssertionError('Trusted external pin advanced during ENOSPC')
        head=strict((root/'HEAD').read_bytes());h=shaobj(head)
        if h==old:
            chain=verify_chain(root,pub,expected_fingerprint=key['fingerprint_sha256'],expected_tip=old)
            if chain['length']!=1:raise AssertionError('Prior chain lost')
            outcome='PREVIOUS_TIP_VALID_PENDING_OR_ORPHAN'
        else:
            try:verify_chain(root,pub,expected_fingerprint=key['fingerprint_sha256'],expected_tip=old)
            except ValueError:pass
            else:raise AssertionError('Old trusted tip erroneously accepted after HEAD replacement')
            quarantine=WitnessStore(root).recover(external_tip=old,candidate_tip=h)
            if quarantine['state']!='QUARANTINED_UNTIL_INDEPENDENT_REPLAY_AND_EXTERNAL_REPIN':
                raise AssertionError('Invalid quarantine state')
            outcome='NEW_HEAD_QUARANTINED'
        # No automatic retry may adopt the candidate or mint another signature.
        try:WitnessStore(root).publish(sample('third_original_metadata'),expected_tip=old)
        except (ValueError,OSError):pass
        else:raise AssertionError('Unexpected new signature after full-filesystem failure')
        if held_head is not None:os.close(held_head)
        return {'status':'PASS','reserve_bytes':reserve,'actual_free_bytes_pre_failure':actual_left,
                'real_kernel_errno':fail,'fs_type':'isolated_private_tmpfs','prior_tip':old,
                'head_after_failure':h,'outcome':outcome,
                'journal_math_tested':False,'power_cut_tested':False}
    finally:
        if mounted:
            subprocess.run(['umount',str(mnt)],check=True,capture_output=True,text=True)
        shutil.rmtree(top,ignore_errors=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--reserve',type=int,required=True)
    a=p.parse_args()
    print(json.dumps(run(a.reserve),sort_keys=True))
