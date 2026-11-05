#!/usr/bin/env python3
"""OPTIONAL direct MPFR one-case smoke test. Does not test OS process separation.

This runs the original CH30 cold verifier on an original CH29 127-node certificate.
The CH39 full archive checker uses Linux fcntl and is deliberately not invoked.
"""
from __future__ import annotations
import argparse, ctypes, ctypes.util, hashlib, json, os, pathlib, sys, time


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=pathlib.Path,required=True)
    p.add_argument('--output',type=pathlib.Path,required=True)
    p.add_argument('--mpfr-dll',type=pathlib.Path,default=None)
    a=p.parse_args()
    result={'status':'FAIL','case':'one_event_n80_i00','scope':'seven-node prefix projected from frozen original CH29 63-node certificate, checked at 224-bit MPFR',
            'platform':sys.platform,'process_bits':ctypes.sizeof(ctypes.c_void_p)*8,
            'full_CH39_archive_checker_rerun':False,'linux_five_uid_isolation_retested':False}
    dll_handle=None
    try:
        if sys.platform=='win32' and ctypes.sizeof(ctypes.c_void_p)!=8:
            raise RuntimeError('BLOCKED: 64-bit Python required for Windows MPFR test')
        if a.mpfr_dll is not None:
            mpfr=a.mpfr_dll.resolve(strict=True)
            if not mpfr.is_file() or mpfr.suffix.lower()!='.dll':
                raise ValueError('Explicit MPFR DLL is not a .dll file')
            if sys.platform=='win32':
                dll_handle=os.add_dll_directory(str(mpfr.parent))
            original=ctypes.util.find_library
            ctypes.util.find_library=lambda name: str(mpfr) if name=='mpfr' else original(name)
        elif not ctypes.util.find_library('mpfr'):
            raise RuntimeError('BLOCKED: Windows MPFR DLL not discoverable; specify -MpfrDll with matching GMP dependencies')
        root=a.root.resolve(strict=True)
        sys.path.insert(0,str(root/'CH_C14_31'))
        sys.path.insert(0,str(root/'CH_C14_30'))
        t=time.process_time()
        from verifier31 import load_original_case
        from verifier30 import verify_full
        sys.path.insert(0,str(root/'CH_C14_31'))
        from prefix31 import project_prefix
        inp,proto,duals,archived=load_original_case(result['case'])
        cert63,_=archived(63)
        cert=project_prefix(cert63,7)
        verified=verify_full(cert,inp,{**proto,'node_budget_per_case':7},duals)
        status=verified['replay_status']
        if (status!='REPLAYED_BUT_UNRESOLVED' or verified['nodes_verified']!=7
                or verified['precision_bits']!=224 or verified['unbounded_global_claim'] is not False):
            raise ValueError('Unexpected scientific verification result: '+str(status))
        if not (verified['gap_upper_display'] > 0.05):
            raise ValueError('Unexpectedly certified a historically unresolved projected prefix')
        result.update({'status':'PASS','case':result['case'],'fresh_mpfr_nodes':7,'replay_precision_bits':224,
                       'replay_status':status,'gap_upper_display':verified['gap_upper_display'],
                       'cpu_seconds':round(time.process_time()-t,3),
                       'note':'Projected original CH29 prefix, not a new optimizer run; neither a 127-node CH39 verification nor multi-UID acceptance.'})
    except Exception as exc:
        result['error']=f'{type(exc).__name__}: {exc}'
        if 'BLOCKED:' in str(exc):result['status']='BLOCKED'
        print(result['status']+': '+result['error'],file=sys.stderr)
    finally:
        if dll_handle is not None:dll_handle.close()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(result,sort_keys=True,indent=2))
    return 0 if result['status']=='PASS' else 2 if result['status']=='BLOCKED' else 1

if __name__=='__main__':raise SystemExit(main())