#!/usr/bin/env python3
"""CH39 MSYS2 UCRT64 MPFR native runtime closure (offline kit-local only).

Downloads SHA256-pinned upstream binary packages and extracts only specified
UCRT64 runtime DLLs. No installation, PATH, registry or Python changes.
Requires standard Python >=3.14 (compression.zstd).
"""
from __future__ import annotations
import argparse
import ctypes
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import sys
import tarfile
import urllib.request
from datetime import datetime, timezone

PKGS = (
    dict(name='mpfr', filename='mingw-w64-ucrt-x86_64-mpfr-4.2.2-3-any.pkg.tar.zst', sha='6b70a275d2ec75c70aa50a236c218e6b7ee9a5ab4c6d52cb0b580267b7d200fe', dll='libmpfr-6.dll'),
    dict(name='gmp', filename='mingw-w64-ucrt-x86_64-gmp-6.3.0-2-any.pkg.tar.zst', sha='e82a75968a556484a50084578238a84eb60fb93e34986fd6695c537975bd39ea', dll='libgmp-10.dll'),
    dict(name='libgcc', filename='mingw-w64-ucrt-x86_64-libgcc-16.2.0-6-any.pkg.tar.zst', sha='80b2497f019977dd9528b1abc8621b1328a0115ab1f724047ccbb56bf323f11d', dll='libgcc_s_seh-1.dll'),
    dict(name='libwinpthread', filename='mingw-w64-ucrt-x86_64-libwinpthread-14.0.0.r569.g34eeafb7d-1-any.pkg.tar.zst', sha='b4ebe2826e848c5e790e06ea7b37d3e0594e005f42382b0506886f17df8127da', dll='libwinpthread-1.dll'),
    dict(name='libstdcxx', filename='mingw-w64-ucrt-x86_64-libstdc%2B%2B-16.2.0-6-any.pkg.tar.zst', sha='33c5e58a85a538cf843a8672991cce591f0231d66da3b66a57629712d64be17f', dll='libstdc++-6.dll'),
)

# For libstdc++, MSYS2's URL encodes '+' in the download link; filesystem uses '+'.
PKGS = tuple({**p, 'local_filename':p['filename'].replace('%2B','+')} for p in PKGS)
MAX_DOWNLOAD = 6 * 1024 * 1024
MAX_UNPACKED = 50 * 1024 * 1024
MAX_DLL = 20 * 1024 * 1024


def digest(b:bytes)->str:
    return hashlib.sha256(b).hexdigest()


def fetch(pkg:dict, offline_dir:Path)->bytes:
    local = offline_dir / pkg['local_filename']
    if local.is_file():
        data=local.read_bytes()
        if digest(data)!=pkg['sha']:
            raise ValueError('Untrusted local package digest: '+local.name)
        print('Verified cached archive:', local.name, flush=True)
        return data
    errors=[]
    for host in ('https://mirror.msys2.org/mingw/ucrt64/', 'https://repo.msys2.org/mingw/ucrt64/'):
        url=host+pkg['filename']
        try:
            print('Downloading verified upstream runtime:',pkg['name'],flush=True)
            req=urllib.request.Request(url,headers={'User-Agent':'Cognitum-CH39-UCRT64-runtime-closure/2'})
            with urllib.request.urlopen(req,timeout=45) as h:
                data=h.read(MAX_DOWNLOAD+1)
            if len(data)>MAX_DOWNLOAD:raise ValueError('Oversized package')
            if digest(data)!=pkg['sha']:
                raise ValueError('Package SHA256 mismatch '+pkg['name']+' got '+digest(data))
            print('PASS upstream package SHA256:', pkg['name'],flush=True)
            return data
        except Exception as exc:
            errors.append(f'{type(exc).__name__}: {exc}')
    raise RuntimeError('No verified download for '+pkg['name']+'; '+ '; '.join(errors))


def unpack_dll(pkg:dict,payload:bytes)->bytes:
    from compression import zstd
    raw=zstd.decompress(payload)
    if len(raw)>MAX_UNPACKED:raise ValueError('Oversized expanded archive')
    member_name='ucrt64/bin/'+pkg['dll']
    with tarfile.open(fileobj=io.BytesIO(raw),mode='r:') as archive:
        members=[x for x in archive.getmembers() if x.name.removeprefix('./')==member_name]
        if len(members)!=1 or not members[0].isreg():
            raise ValueError('Expected 1 regular DLL: '+member_name)
        member=members[0]
        if not 1024 < member.size < MAX_DLL:raise ValueError('Bad DLL length: '+pkg['dll'])
        f=archive.extractfile(member)
        if f is None:raise ValueError('Empty DLL entry')
        dll=f.read()
        if len(dll)!=member.size or not dll.startswith(b'MZ'):
            raise ValueError('Invalid PE bytes: '+pkg['dll'])
        return dll


def read_imports(blob:bytes)->list[str]:
    """Minimal PE32+/PE32 import-table inspection, for diagnostic display only."""
    def u16(i):return struct.unpack_from('<H',blob,i)[0]
    def u32(i):return struct.unpack_from('<I',blob,i)[0]
    if not blob.startswith(b'MZ') or len(blob)<0x100: return []
    pe=u32(0x3c)
    if pe+24>=len(blob) or blob[pe:pe+4]!=b'PE\0\0':return []
    nsects=u16(pe+6);optsz=u16(pe+20);opt=pe+24
    magic=u16(opt)
    if magic not in (0x10b,0x20b):return []
    dir_offset=opt+(112 if magic==0x20b else 96)
    if dir_offset+16>opt+optsz:return []
    rva=u32(dir_offset+8)
    if not rva:return []
    sections=[]
    for i in range(min(nsects,96)):
        off=opt+optsz+i*40
        if off+40>len(blob):return []
        virtual_size=u32(off+8); virtual_base=u32(off+12)
        raw_size=u32(off+16);raw_pos=u32(off+20)
        sections.append((virtual_base,max(virtual_size,raw_size),raw_pos))
    def ofs(v):
        for b,size,p in sections:
            if b<=v<b+size and p+(v-b)<len(blob):return p+(v-b)
        raise ValueError('bad PE RVA')
    start=ofs(rva);imports=[]
    for i in range(1024):
        p=start+i*20
        if p+20>len(blob):break
        descriptor=blob[p:p+20]
        if descriptor==b'\0'*20:break
        name_rva=u32(p+12)
        k=ofs(name_rva)
        end=blob.find(b'\0',k,min(k+260,len(blob)))
        if end<0:break
        imports.append(blob[k:end].decode('ascii','replace'))
    return imports


def check_loader(dest:Path)->dict:
    lib=dest/'libmpfr-6.dll'
    with os.add_dll_directory(str(dest)):
        try:
            handle=ctypes.CDLL(str(lib))
            fun=handle.mpfr_get_version
            fun.argtypes=[]
            fun.restype=ctypes.c_char_p
            version=fun()
            if not version or not version.startswith(b'4.2.'):
                raise ValueError('Unexpected loaded MPFR version: '+repr(version))
            return {'load':'PASS','mpfr_version':version.decode('ascii','replace')}
        except OSError as exc:
            return {'load':'BLOCKED','error':str(exc),'winerror':getattr(exc,'winerror',None)}


def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--dest',type=Path,default=Path(__file__).resolve().parent/'MPFR_Runtime')
    ap.add_argument('--offline-dir',type=Path,default=Path(__file__).resolve().parent)
    a=ap.parse_args()
    if sys.platform!='win32' or sys.version_info < (3,14):
        print('BLOCKED: requires 64-bit Windows with Python 3.14+')
        return 2
    if struct.calcsize('P')!=8:
        print('BLOCKED: requires 64-bit Python')
        return 2
    try:
        from compression import zstd
    except ImportError:
        print('BLOCKED: standard-library compression.zstd unavailable')
        return 2
    dest=a.dest.resolve();dest.mkdir(parents=True,exist_ok=True)
    result={'version':'2.0','date_utc':datetime.now(timezone.utc).isoformat(),
            'scope':'SHA256-verified five-package MSYS2 UCRT64 DLLs, no system installs',
            'status':'BLOCKED','packages':{},'dll_imports':{}}
    try:
        fetched=[]
        for pkg in PKGS:
            package_bytes=fetch(pkg,a.offline_dir)
            dll=unpack_dll(pkg,package_bytes)
            fetched.append((pkg,dll))
            result['packages'][pkg['name']]={'filename':pkg['local_filename'],
                'package_sha256':pkg['sha'],'dll_sha256':digest(dll), 'dll':pkg['dll']}
            result['dll_imports'][pkg['dll']]=read_imports(dll)
        for pkg,dll in fetched:
            dest_file=dest/pkg['dll']
            tmp=dest/(pkg['dll']+'.tmp')
            tmp.write_bytes(dll)
            os.replace(tmp,dest_file)
            print('PASS: extracted',pkg['dll'],flush=True)
        result.update(check_loader(dest))
        if result['load']=='PASS':
            print('PASS: Windows loader opened libmpfr-6.dll; version '+result['mpfr_version'],flush=True)
            result['status']='PASS'
            return 0
        print('BLOCKED: Windows native DLL load failed despite verified package closure.',flush=True)
        print('Reason:',result.get('error'),flush=True)
        print('DLL imports:',json.dumps(result['dll_imports'],sort_keys=True),flush=True)
        return 2
    except Exception as exc:
        result['error']=type(exc).__name__+': '+str(exc)
        print('BLOCKED:',result['error'],flush=True)
        return 2
    finally:
        (dest/'MPFR_RUNTIME_DIAGNOSTICS_V2.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        print('Diagnostics:',dest/'MPFR_RUNTIME_DIAGNOSTICS_V2.json',flush=True)

if __name__=='__main__':raise SystemExit(main())