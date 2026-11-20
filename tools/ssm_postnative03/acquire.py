"""Acquire official UCI source archives and deterministic chronological excerpts."""
import csv, hashlib, io, json, sys, urllib.request, zipfile
from datetime import datetime, timedelta
from pathlib import Path

SOURCES = [
    ('uci374',374,'appliances+energy+prediction.zip','energydata_complete.csv',
     ['date','T1','T2','T_out','RH_1','Appliances'],'C5VC8G','Luis Candanedo'),
    ('uci501',501,'beijing+multi+site+air+quality+data.zip',
     'PRSA_Data_Aotizhongxin_20130301-20170228.csv',
     ['year','month','day','hour','PM2.5','TEMP','PRES','WSPM'],'C5RK5G','Song Chen')]
def digest(raw): return hashlib.sha256(raw).hexdigest()
def member(raw,target):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        for k in z.namelist():
            if k.split('/')[-1]==target and z.getinfo(k).file_size<48000000:
                return z.read(k),k
        for k in z.namelist():
            if k.lower().endswith('.zip') and z.getinfo(k).file_size<50000000:
                with zipfile.ZipFile(io.BytesIO(z.read(k))) as inner:
                    for n in inner.namelist():
                        if n.split('/')[-1]==target and inner.getinfo(n).file_size<48000000:
                            return inner.read(n),k+'::'+n
    raise ValueError('expected source member absent '+target)
def acquire(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False);(out/'fixtures').mkdir()
    manifest={'version':1,'license':'CC BY 4.0 (dataset-specific UCI pages)','entries':[]}
    for slug,num,archive,target,cols,doi,author in SOURCES:
        url='https://archive.ics.uci.edu/static/public/'+str(num)+'/'+archive
        req=urllib.request.Request(url,headers={'User-Agent':'Cognitum-scientific-data-audit/1.0'})
        with urllib.request.urlopen(req,timeout=90) as r: raw=r.read(64000001)
        expected_archive = {'uci374':'2fccf354445d886e7917620b0195db1f3e3e34d5a067a93b844694a4c561255a',
                            'uci501':'b04da438b2f331ac0ffd45aebdfec0d20d2367feb5f6948c4b1f7ce1191e33c4'}
        if digest(raw)!=expected_archive[slug]: raise ValueError('upstream archive changed since independently preserved first acquisition')
        if len(raw)>64000000 or not zipfile.is_zipfile(io.BytesIO(raw)):
            raise ValueError('unexpected source archive')
        content,path=member(raw,target)
        reader=csv.DictReader(io.StringIO(content.decode('utf-8-sig')))
        if any(c not in reader.fieldnames for c in cols): raise ValueError('source columns: '+repr(reader.fieldnames)+' wanted '+repr(cols))
        o=io.StringIO(newline='');w=csv.DictWriter(o,fieldnames=cols,lineterminator='\n')
        w.writeheader();prev=None;missing=0;count=0
        for row in reader:
            if count>=6144: break
            if slug=='uci374':
                dt=datetime.strptime(row['date'],'%Y-%m-%d %H:%M:%S')
                step=timedelta(minutes=10)
            else:
                dt=datetime(*[int(row[c]) for c in ('year','month','day','hour')])
                step=timedelta(hours=1)
            if prev is not None and dt-prev!=step: raise ValueError('gapped source time')
            prev=dt;selected={k:row[k] for k in cols}
            missing+=sum(v.strip().upper() in ('','NA') for v in selected.values())
            w.writerow(selected);count+=1
        if count!=6144: raise ValueError('source truncated')
        excerpt=o.getvalue().encode('utf-8')
        (out/'fixtures'/(slug+'.csv')).write_bytes(excerpt)
        (out/(slug+'_original.zip')).write_bytes(raw)
        manifest['entries'].append({
            'id':slug,'url':url,'doi':'https://doi.org/10.24432/'+doi,
            'author':author,'archive_sha256':digest(raw),'archive_bytes':len(raw),
            'source_member':path,'source_member_sha256':digest(content),
            'source_member_bytes':len(content),
            'source_member_git_blob':hashlib.sha1(b'blob '+str(len(content)).encode()+b'\0'+content).hexdigest(),
            'excerpt_sha256':digest(excerpt),'excerpt_rows':count,
            'missing_selected_cells':missing,'columns':cols,
            'transform':'first 6144 chronological observations, selected original columns, no interpolation'})
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    print(json.dumps(manifest['entries'],indent=2))
if __name__=='__main__': acquire(sys.argv[1])
