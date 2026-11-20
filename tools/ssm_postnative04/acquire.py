"""Acquire byte-pinned CC BY 4.0 UCI multisite sensor data; no silent repair.

Offline: --archive /path/to/original.zip. Online CI: exact UCI URL, 8MB bound.
Only emits observational excerpts if original archive, nested zip, source-member
and every derived excerpt hash all match the frozen independently checked table.
"""
import argparse
import csv
from hashlib import sha256
from io import BytesIO, StringIO
import json
from pathlib import Path
from urllib.request import Request, urlopen
import zipfile

URL='https://archive.ics.uci.edu/static/public/501/beijing+multi+site+air+quality+data.zip'
ROOT=Path(__file__).resolve().parents[2]
MANIFEST=ROOT/'research_tests/ssm_postnative04/data/sources.json'
SHA='3f47ec84d49d9a169124f3c9778a87c42f10f910b334a4faf906bf76774112f3'
LIMIT=12*1024*1024

def need(ok,why):
    if not ok:raise ValueError(why)

def sha(b):return sha256(b).hexdigest()

def emit(raw,out,manifest_raw=None,retain_archive=False):
    """Deterministic first 6,144 rows from original official nested source ZIP."""
    if manifest_raw is None:manifest_raw=MANIFEST.read_bytes()
    need(sha(manifest_raw)==SHA,'manifest changed');d=json.loads(manifest_raw)
    need(type(raw) is bytes and len(raw)<LIMIT and sha(raw)==d['outer_archive_sha256'],'original archive SHA')
    outer=zipfile.ZipFile(BytesIO(raw));inner_raw=outer.read(d['nested_zip_member']);need(sha(inner_raw)==d['nested_zip_sha256'],'nested archive SHA')
    inner=zipfile.ZipFile(BytesIO(inner_raw));out=Path(out);out.mkdir(parents=True,exist_ok=True)
    for entry in d['entries']:
        member=inner.read(entry['source_member']);need(sha(member)==entry['source_member_sha256'],'site member SHA')
        reader=csv.DictReader(StringIO(member.decode('utf-8-sig')));rows=[next(reader) for _ in range(entry['rows'])]
        output=StringIO(newline='');writer=csv.DictWriter(output,fieldnames=entry['columns'],lineterminator='\n');writer.writeheader()
        writer.writerows([{k:r[k] for k in entry['columns']} for r in rows])
        derived=output.getvalue().encode('utf-8')
        need(sha(derived)==entry['excerpt_sha256'] and len(derived)==entry['excerpt_bytes'],'site row-wise identity')
        (out/entry['data_excerpt']).write_bytes(derived)
    receipt={'source_url':URL,'source_archive_sha256':sha(raw),'nested_archive_sha256':sha(inner_raw),'dataset_id':'UCI-501','license':'CC BY 4.0',
             'dataset_doi':'https://doi.org/10.24432/C5RK5G','rows_verified':sum(x['rows'] for x in d['entries']),
             'sites':{e['site']:e['excerpt_sha256'] for e in d['entries']},'upstream_publisher_signature_verified':False,'author_attribution_required':True}
    (out/'acquisition.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    if retain_archive:(out/'source_archive.zip').write_bytes(raw)
    return receipt

def main():
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path);p.add_argument('--out',type=Path,default=ROOT/'research_tests/ssm_postnative04/data');p.add_argument('--retain-archive',action='store_true');args=p.parse_args()
    if args.archive:raw=args.archive.read_bytes()
    else:
        req=Request(URL,headers={'User-Agent':'Cognitum-PostNative04-reproducible-data-research/1.0'})
        with urlopen(req,timeout=60) as response:raw=response.read(LIMIT+1)
    print(json.dumps(emit(raw,args.out,retain_archive=args.retain_archive),indent=2))
if __name__=='__main__':main()
