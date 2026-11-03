"""Safely extract the original SHA-pinned archive once for research-only UID tests."""
import hashlib,os,shutil,zipfile,pathlib,tempfile
HERE=pathlib.Path(__file__).resolve().parents[1]
SRC=HERE/'assets'/'Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip'
PIN='9e713b102982ea09fecbcfbd27bccf55d56808188bfc3e5be1ba76922000ae6b'
DST=HERE/'baseline'
def main():
 if hashlib.sha256(SRC.read_bytes()).hexdigest()!=PIN:raise ValueError('Original frozen source trust root changed')
 if DST.exists():
  if not (DST/'CH_C14_35/trust35.py').is_file():raise ValueError('Existing baseline incomplete; refuse overwrite')
  print('Existing original CH39 baseline present. Remove explicitly if a clean reset is needed.')
  return
 temp=pathlib.Path(tempfile.mkdtemp(prefix='ch40g-original-baseline-',dir=HERE))
 try:
  with zipfile.ZipFile(SRC) as z:
   for info in z.infolist():
    n=pathlib.PurePosixPath(info.filename)
    if n.is_absolute() or '..' in n.parts or chr(92) in info.filename or info.filename.startswith('/'):
     raise ValueError('Unsafe archive path')
    mode=(info.external_attr>>16)&0xFFFF
    if mode&0o170000==0o120000:raise ValueError('Refuse source symlink')
    target=temp.joinpath(*n.parts)
    if info.is_dir():target.mkdir(exist_ok=True,parents=True);continue
    target.parent.mkdir(parents=True,exist_ok=True)
    with z.open(info) as inp,target.open('xb') as out:shutil.copyfileobj(inp,out)
  temp.rename(DST)
  print('Original source extracted from pinned archive for live UID lab:',DST)
 finally:
  if temp.exists():shutil.rmtree(temp)
if __name__=='__main__':main()
