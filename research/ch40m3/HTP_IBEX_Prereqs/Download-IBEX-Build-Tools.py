"""HTP: download only official Debian 13 Linux x86-64 Flex/Bison .deb archives.
Download-only, never installs/executes. SHA-256 pins from Debian package download pages.
"""
from __future__ import annotations
import hashlib,json,sys,urllib.request,zipfile,tempfile,shutil
from pathlib import Path
FILES=[
 {'name':'flex_2.6.4-8.2+b4_amd64.deb','sha256':'75f963765232c356d0a2fb70e780dfa9de2425aca036ec60eefb7fc98a2c905b','path':'pool/main/f/flex/flex_2.6.4-8.2%2Bb4_amd64.deb'},
 {'name':'bison_3.8.2+dfsg-1+b2_amd64.deb','sha256':'ce6eb1f7aad18850e32d223a68f54bcbe756d74f138c8ec5460ad9d220f4d335','path':'pool/main/b/bison/bison_3.8.2%2Bdfsg-1%2Bb2_amd64.deb'},
]
BASES=['https://deb.debian.org/debian/','https://ftp.de.debian.org/debian/']

def sha256(path:Path):
 h=hashlib.sha256()
 with path.open('rb') as fp:
  for block in iter(lambda:fp.read(1024*1024),b''):h.update(block)
 return h.hexdigest()

def download_one(info:dict,dest:Path):
 path=dest/info['name'];expected=info['sha256']
 if path.exists() and sha256(path)==expected:
  print('[REUSE]',path.name,flush=True);return
 for base in BASES:
  url=base+info['path'];tmp=path.with_suffix('.partial')
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'Cognitum-HTP-Reproducible-Research/1.0','Accept':'*/*'})
   with urllib.request.urlopen(req,timeout=40) as src,tmp.open('wb') as output:
    shutil.copyfileobj(src,output,length=1024*1024)
   if tmp.stat().st_size<20000:raise ValueError('Truncated or error response')
   digest=sha256(tmp)
   if digest!=expected:raise ValueError('Unexpected SHA-256 (download rejected) '+digest)
   tmp.replace(path);print('[VERIFIED]',path.name,path.stat().st_size,'bytes',flush=True)
   return
  except Exception as exc:
   print('[RETRY]',url,str(exc)[:180],flush=True)
  finally:tmp.unlink(missing_ok=True)
 raise RuntimeError('All official download routes failed for '+path.name)

def main():
 dest=Path.home()/'Documents'/'Cognitum_Offline_Solver_Libraries'/'Build_Prerequisites'
 dest.mkdir(parents=True,exist_ok=True)
 for info in FILES:download_one(info,dest)
 manifest={'protocol':'COGNITUM-IBEX-PREREQS-HTP-V1','scope':'Debian 13 trixie Linux x86_64 only; source IBEX 2.9.1 build tools; no installation','files':FILES,'notices':['m4, cmake, ninja, gcc/g++ must already exist in target Linux','checksums from Debian official package download pages']}
 (dest/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 archive=dest/'Cognitum_IBEX_Flex_Bison_Debian13_Offline.zip'
 with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
  for info in FILES:z.write(dest/info['name'],info['name'])
  z.write(dest/'manifest.json','manifest.json')
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None
  for info in FILES:assert hashlib.sha256(z.read(info['name'])).hexdigest()==info['sha256']
 (dest/(archive.name+'.sha256')).write_text(sha256(archive)+'  '+archive.name+'\n')
 print('\nUpload this ZIP to /Cognitum/Packages:',archive,flush=True)
if __name__=='__main__':main()

