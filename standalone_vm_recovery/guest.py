"""Opt-in DISPOSABLE-VM reboot validation of P2Z persisted host and journal.

Never reboots or shuts down a machine. powercut mode additionally requires
independent hypervisor event evidence for certification; this code cannot prove it.
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
import uuid
from cognitum.spatial_host_recovery_readiness import P2ZHostReadiness
from cognitum.spatial_durable_incremental_volume import bits
from standalone_windows_host.authority import StandaloneAuthority
from standalone_windows_host.platform_io import windows_require_ntfs, reject_reparse
from tests.test_c15_t3_p2w_map_lifecycle import request

class GateRejected(RuntimeError): pass

def boot_identity():
    if os.name=='nt':
        # Boot time is OS reported, not a cryptographic attestation.
        script='(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().ToString("o")'
        p=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],capture_output=True,text=True,timeout=30)
        if p.returncode!=0 or not p.stdout.strip(): raise GateRejected('WINDOWS_BOOT_IDENTITY_UNAVAILABLE')
        return p.stdout.strip()
    path=Path('/proc/sys/kernel/random/boot_id')
    if path.is_file():return path.read_text().strip()
    raise GateRejected('BOOT_IDENTITY_UNAVAILABLE')

def _read(path):return json.loads(Path(path).read_text('utf8'))
def _write_new(path,obj):
    raw=(json.dumps(obj,sort_keys=True,indent=2)+'\n').encode()
    with open(path,'xb') as f:
        f.write(raw);f.flush();os.fsync(f.fileno())

def _status(scope,anchor):
    return {'schema':1,'research_only':True,'scope':scope,'sequence':anchor.sequence,
            'epoch':anchor.authority_epoch,'anchor_sha256':hashlib.sha256(bits(anchor)).hexdigest()}

def _ensure_vm(root,allow_linux):
    if os.name=='nt':
        if platform.machine().lower() not in ('amd64','x86_64') or sys.maxsize<=2**32:raise GateRejected('WINDOWS_X86_64_REQUIRED')
        if os.environ.get('COGNITUM_DISPOSABLE_VM')!='I_CONFIRM_DISPOSABLE_VM':
            raise GateRejected('DISPOSABLE_VM_OPT_IN_MISSING')
        windows_require_ntfs(root.parent)
    elif not allow_linux:raise GateRejected('NATIVE_WINDOWS_REQUIRED')
    reject_reparse(root.parent)

def prepare(root,scenario,*,allow_linux=False,boot_override=None):
    root=Path(root).absolute();_ensure_vm(root,allow_linux)
    if root.exists():raise GateRejected('REFUSE_OVERWRITE_EXISTING_STATE')
    if scenario not in ('reboot','hypervisor_powercut'):raise GateRejected('UNSUPPORTED_SCENARIO')
    root.mkdir(parents=True)
    host=StandaloneAuthority(root/'authority',insecure_test_backend=allow_linux)
    q=request();d=q.source_request.dynamic_request
    initial=host.enroll(d.conversation_id,d.volume_id,epoch=9,journal_directory=root/'journal')
    scope=hashlib.sha256((d.conversation_id+'\x00'+d.volume_id).encode()).hexdigest()[:32]
    from cognitum.proto import spatial_durable_incremental_volume_pb2 as ypb
    genesis=ypb.P2YHostAnchor.FromString(initial.external_anchor)
    z=P2ZHostReadiness(root/'journal',host=host)
    z.open_session().advance(q)
    preview=z.inspect()
    if preview.status!='CLEAN':raise GateRejected('PREPARE_NOT_CLEAN')
    anchor=host.read_binding().external_anchor
    current=ypb.P2YHostAnchor.FromString(anchor)
    if current.sequence!=1:raise GateRejected('UNEXPECTED_COMMIT_SEQUENCE')
    start=_status(scope,genesis)
    intent=_status(scope,current)
    intent['previous_anchor_sha256']=start['anchor_sha256']
    _write_new(root/'witness-enroll.json',start)
    _write_new(root/'witness-advance.json',intent)
    marker={'schema':1,'research_only':True,'scenario':scenario,'boot_before':boot_override or boot_identity(),
            'scope':scope,'anchor_sha256':intent['anchor_sha256'],'sequence':1,
            'run_id':str(uuid.uuid4()),'windows_native':os.name=='nt',
            'hypervisor_powercut_confirmed':False}
    _write_new(root/'phase-marker.json',marker)
    return {'status':'PREPARED','root':str(root),'run_id':marker['run_id'],
        'scenario':scenario,'next':'OPERATOR_RESTARTS_DISPOSABLE_VM; then run verify; no automatic shutdown'}

def verify(root,*,allow_linux=False,boot_override=None):
    root=Path(root).absolute();_ensure_vm(root,allow_linux)
    m=_read(root/'phase-marker.json')
    if m.get('schema')!=1:raise GateRejected('INVALID_PHASE_MARKER')
    now=boot_override or boot_identity()
    if m['boot_before']==now:raise GateRejected('WINDOWS_REBOOT_NOT_OBSERVED')
    host=StandaloneAuthority(root/'authority',insecure_test_backend=allow_linux)
    z=P2ZHostReadiness(root/'journal',host=host)
    p=z.inspect()
    if p.status!='CLEAN':raise GateRejected('REPLAY_NOT_CLEAN:'+p.status)
    session=z.open_session()
    anchor=session.anchor
    if anchor.sequence!=m['sequence'] or hashlib.sha256(bits(anchor)).hexdigest()!=m['anchor_sha256']:
        raise GateRejected('ANCHOR_MISMATCH_ON_REBOOT')
    state=_status(m['scope'],anchor)
    output={'status':'REBOOT_AND_FULL_REPLAY_PASS','research_only':True,'run_id':m['run_id'],
            'scenario':m['scenario'],'boot_changed':True,'p2z_status':p.status,'sequence':anchor.sequence,
            'external_witness_verdict':'PENDING_HOST_COMPARISON',
            'hypervisor_powercut_certification':'NOT_ESTABLISHED',
            'notes':'Guest boot identity is OS-provided; independent host witness required to detect guest snapshot rollback.'}
    _write_new(root/'witness-check.json',state)
    _write_new(root/'reboot-evidence.json',output)
    return output

def snapshot_initialize(root,*,allow_linux=False,boot_override=None):
    """Create genesis, then operator snapshots the DISPOSABLE guest VM."""
    root=Path(root).absolute();_ensure_vm(root,allow_linux)
    if root.exists():raise GateRejected('REFUSE_OVERWRITE_EXISTING_STATE')
    root.mkdir(parents=True)
    host=StandaloneAuthority(root/'authority',insecure_test_backend=allow_linux)
    q=request();d=q.source_request.dynamic_request
    binding=host.enroll(d.conversation_id,d.volume_id,epoch=9,journal_directory=root/'journal')
    z=P2ZHostReadiness(root/'journal',host=host)
    if z.inspect().status!='CLEAN':raise GateRejected('GENESIS_NOT_CLEAN')
    from cognitum.proto import spatial_durable_incremental_volume_pb2 as ypb
    anchor=ypb.P2YHostAnchor.FromString(binding.external_anchor)
    scope=hashlib.sha256((d.conversation_id+'\x00'+d.volume_id).encode()).hexdigest()[:32]
    start=_status(scope,anchor)
    _write_new(root/'witness-enroll.json',start)
    _write_new(root/'snapshot-marker.json',{'schema':1,'research_only':True,
        'boot_before':boot_override or boot_identity(),'scope':scope,
        'anchor_sha256':start['anchor_sha256'],'sequence':0})
    return {'status':'SNAPSHOT_GENESIS_READY','sequence':0,
        'next':'HOST enroll at sequence 0; THEN take a VM snapshot before commit'}

def snapshot_commit(root,*,allow_linux=False):
    root=Path(root).absolute();_ensure_vm(root,allow_linux)
    m=_read(root/'snapshot-marker.json')
    if m.get('schema')!=1 or m.get('sequence')!=0:raise GateRejected('BAD_SNAPSHOT_MARKER')
    host=StandaloneAuthority(root/'authority',insecure_test_backend=allow_linux)
    z=P2ZHostReadiness(root/'journal',host=host)
    if z.inspect().status!='CLEAN' or z.open_session().anchor.sequence!=0:
        raise GateRejected('SNAPSHOT_GENESIS_NOT_CLEAN')
    z.open_session().advance(request())
    if z.inspect().status!='CLEAN':raise GateRejected('SNAPSHOT_COMMIT_NOT_CLEAN')
    from cognitum.proto import spatial_durable_incremental_volume_pb2 as ypb
    anchor=ypb.P2YHostAnchor.FromString(host.read_binding().external_anchor)
    if anchor.sequence!=1:raise GateRejected('SNAPSHOT_SEQUENCE_NOT_ONE')
    latest=_status(m['scope'],anchor)
    latest['previous_anchor_sha256']=m['anchor_sha256']
    _write_new(root/'witness-advance.json',latest)
    return {'status':'SNAPSHOT_COMMITTED','sequence':1,
        'next':'Copy witness-advance to OFF-GUEST host and commit there; restore older VM snapshot ONLY in disposable VM'}

def snapshot_check(root,*,allow_linux=False):
    root=Path(root).absolute();_ensure_vm(root,allow_linux)
    m=_read(root/'snapshot-marker.json')
    host=StandaloneAuthority(root/'authority',insecure_test_backend=allow_linux)
    z=P2ZHostReadiness(root/'journal',host=host)
    if z.inspect().status!='CLEAN':raise GateRejected('RESTORED_JOURNAL_NOT_CLEAN')
    anchor=z.open_session().anchor
    current=_status(m['scope'],anchor)
    _write_new(root/'witness-check.json',current)
    return {'status':'GUEST_SNAPSHOT_READABLE_NOT_YET_ACCEPTED',
        'sequence':anchor.sequence,
        'next':'HOST runs witness check against OFF-GUEST high-water DB; ROLLBACK_DETECTED is the expected negative-test outcome'}

def main(argv=None):
    p=argparse.ArgumentParser(description='Prepare/verify a disposable Windows VM test; NEVER commands a reboot or power-off')
    p.add_argument('command',choices=['prepare','verify','snapshot-init','snapshot-commit','snapshot-check'])
    p.add_argument('--root',required=True)
    p.add_argument('--scenario',choices=['reboot','hypervisor_powercut'],default='reboot')
    p.add_argument('--insecure-linux-test-only',action='store_true')
    args=p.parse_args(argv)
    try:
        if args.command=='prepare':result=prepare(args.root,args.scenario,allow_linux=args.insecure_linux_test_only)
        elif args.command=='verify':result=verify(args.root,allow_linux=args.insecure_linux_test_only)
        elif args.command=='snapshot-init':result=snapshot_initialize(args.root,allow_linux=args.insecure_linux_test_only)
        elif args.command=='snapshot-commit':result=snapshot_commit(args.root,allow_linux=args.insecure_linux_test_only)
        else:result=snapshot_check(args.root,allow_linux=args.insecure_linux_test_only)
        print(json.dumps(result,indent=2));return 0
    except (GateRejected,ValueError,OSError,RuntimeError) as ex:
        print('VM GATE REJECTED: '+str(ex),file=sys.stderr);return 2

if __name__=='__main__':sys.exit(main())
