"""User-uploaded CORe50 sample, session-disjoint pilot. No network or asset extraction.
Depth color renderings are not metric depth. Never fuse unmatched frames.
"""
import argparse,csv,hashlib,io,json,re,tarfile,time,zipfile
from pathlib import Path
import numpy as np
from PIL import Image

NAME=re.compile(r'(train|test)/img/([CD])_(\d{2})_(\d{2})_(\d{3})\.png')

def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()

def csv_boxes(path):
    out={}
    with open(path,newline='',encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            n=r['Filename'];key=Path(n).stem
            if key in out:raise ValueError('duplicate CSV frame')
            out[key]=(int(r['class']),tuple(int(r[k]) for k in ('xmin','ymin','xmax','ymax')))
    return out

def crop_box(image,box):
    x,y,X,Y=box
    if X-x!=127 or Y-y!=127 or x<-1 or y<-1 or X>350 or Y>350:raise ValueError(f'invalid crop {box}')
    # Official bounds are inclusive; PIL uses a half-open interval and pads outside image.
    return image.crop((x,y,X+1,Y+1))

def image_array(im):return np.asarray(im.convert('RGB').resize((128,128),Image.Resampling.BILINEAR),dtype=np.uint8)

def read_sample(root):
    root=Path(root);paths=[root/n for n in ('CORe50-samples.tar','bbox.zip','core50_train.csv','core50_test.csv')]
    meta={p.name:digest(p) for p in paths};boxes={s:csv_boxes(root/f'core50_{s}.csv') for s in ('train','test')};data={};tag_disagreements=0;pairs={s:{k:set() for k in 'CD'} for s in boxes}
    with zipfile.ZipFile(paths[1]) as z,tarfile.open(paths[0]) as t:
        if z.testzip():raise ValueError('bad bbox archive')
        files={m.name:m for m in t.getmembers() if m.isfile()};cache={}
        for n,m in sorted(files.items()):
            a=NAME.fullmatch(n)
            if not a:continue
            split,k,s,o,f=a.groups();s,o,f=map(int,(s,o,f));key=(s,o,f)
            if key in pairs[split][k]:raise ValueError('duplicate image')
            pairs[split][k].add(key)
            ann=json.load(t.extractfile(files[n.replace('/img/','/ann/')+'.json']))
            tags={v['name']:v['value'] for v in ann['tags']}
            if tags['im_id']!=f'{s:02}_{o:02}_{f:03}' or int(tags['object id'])!=o:raise ValueError('annotation identity mismatch')
            tag_disagreements+=int(int(tags['session'])!=s)
            with Image.open(t.extractfile(m)) as im:
                if im.size!=(350,350):raise ValueError('unexpected image size')
                full=image_array(im);crop=None
                if k=='C':
                    stem=Path(n).stem;label,box=boxes[split][stem]
                    path=f'bbox/s{s}/CropC_o{o}.txt'
                    if path not in cache:
                        cache[path]={int(line.split(':')[0][5:]):tuple(map(int,line.split(':')[1].split())) for line in z.read(path).decode().splitlines() if line.strip()}
                    if label!=o or box!=cache[path][f]:raise ValueError('RGB bbox/CSV mismatch')
                    crop=image_array(crop_box(im,box))
                data[(split,k,s,o,f)]=(full,crop)
    train={v[2] for v in data if v[0]=='train'};test={v[2] for v in data if v[0]=='test'}
    if train&test:raise ValueError('session leakage')
    for split,nc,nd in [('train',377,356),('test',115,147)]:
        if (len(pairs[split]['C']),len(pairs[split]['D']))!=(nc,nd):raise ValueError('sample population mismatch')
    return data,dict(assets=meta,train_sessions=sorted(train),test_sessions=sorted(test),pairs={s:len(v['C']&v['D']) for s,v in pairs.items()},rgb_bbox_matches=492,session_tag_disagreements=tag_disagreements)

def features(images):
    # Same 16x16 RGB display-pixel features per HDC and conventional head.
    return np.stack([np.asarray(Image.fromarray(a).resize((16,16),Image.Resampling.BILINEAR),dtype=np.float32).reshape(-1)/255 for a in images])

def pack(a):return np.packbits(a>=0,axis=-1,bitorder='little')

def predict_packed(q,p):
    tab=np.array([i.bit_count() for i in range(256)],dtype=np.uint8)
    return tab[np.bitwise_xor(q[:,None,:],p[None,:,:])].sum(-1).argmin(1)

def evaluate(x,y,g,t,truth,seed,view,dimension=None):
    sessions=sorted(set(g));first=x[g==sessions[0]];mean=first.mean(0,dtype=np.float64).astype('float32');scale=np.maximum(first.std(0),.05).astype('float32')
    x=np.clip((x-mean)/scale,-5,5);t=np.clip((t-mean)/scale,-5,5)
    width=x.shape[1];classes=50;rows=[];rng=np.random.default_rng(seed)
    if dimension:
        # Seed-regenerable projection; temporary dense workspace is explicitly not retained packed head storage.
        w=(2*rng.integers(0,2,(width,dimension),dtype=np.int8)-1).astype(np.float32)
        x=np.where(x@w>=0,1,-1).astype(np.int16);t=pack(t@w);state=np.zeros((classes,dimension),np.int16);workspace=w.nbytes+x.nbytes+t.nbytes
    else:
        state=np.zeros((classes,width),np.float32);workspace=x.nbytes+t.nbytes
    counts=np.zeros(classes,np.int32);best={}
    for s in sessions:
        ix=g==s
        np.add.at(state,y[ix]-1,x[ix]);np.add.at(counts,y[ix]-1,1)
        seen=np.flatnonzero(counts);valid=np.isin(truth-1,seen)
        if dimension:
            p=pack(state[seen]);pred=seen[predict_packed(t,p)]+1;inference=p.nbytes
        else:
            p=state[seen]/counts[seen,None];p=p.astype(np.float32);dist=((t[:,None,:]-p[None,:,:])**2).sum(-1);pred=seen[dist.argmin(1)]+1;inference=p.nbytes
        correct=(pred==truth);per={int(c):float(correct[truth==c].mean()) for c in np.unique(truth[valid])};old=set(per)&set(best)
        forgetting=float(np.mean([best[c]-per[c] for c in old])) if old else 0.
        for c,a in per.items():best[c]=max(best.get(c,0.),a)
        rows.append(dict(seed=seed,view=view,dimension=dimension,session=int(s),seen_classes=len(seen),test_n=len(truth),covered_n=int(valid.sum()),accuracy=float(correct.mean()),covered_accuracy=float(correct[valid].mean()) if valid.any() else None,macro_covered=float(np.mean(list(per.values()))) if per else None,forgetting=forgetting,training_state_bytes=state.nbytes+counts.nbytes+mean.nbytes+scale.nbytes+(8 if dimension else 0),inference_head_bytes=inference+seen.astype(np.uint8).nbytes+mean.nbytes+scale.nbytes+(8 if dimension else 0),projection_and_operand_workspace_bytes=workspace))
    return rows

def run(root,weights=None):
    data,meta=read_sample(root);rows=[];features_log=[]
    for view,k,crop in [('rgb_full','C',False),('rgb_crop','C',True),('depth_display','D',False)]:
        a=[(v,data[v][int(crop)]) for v in sorted(data) if v[1]==k];tr=[(v,x) for v,x in a if v[0]=='train'];te=[(v,x) for v,x in a if v[0]=='test'];y=np.array([v[3] for v,_ in tr]);g=np.array([v[2] for v,_ in tr]);truth=np.array([v[3] for v,_ in te]);ai=np.stack([x for _,x in tr]);bi=np.stack([x for _,x in te]);views=[(view+'_pixels',features(ai),features(bi))]
        if weights and k=='C':
            import torch
            from tools.cog03e2g_cifar import RGBMobileNet,WEIGHT_SHA
            if digest(weights)!=WEIGHT_SHA:raise ValueError('wrong pretrained checkpoint')
            torch.set_num_threads(1);cal=ai[g==min(g)].transpose(0,3,1,2)
            for variant in ('fp32','ptq'):
                start=time.perf_counter();m=RGBMobileNet(weights,variant,cal);a_,q=m.batch(ai.transpose(0,3,1,2));b_,r=m.batch(bi.transpose(0,3,1,2));assert q==r
                if q:a_=(a_.astype(np.float32)-q[1])*q[0];b_=(b_.astype(np.float32)-q[1])*q[0]
                views.append((view+'_'+variant,a_.astype(np.float32),b_.astype(np.float32)));features_log.append(dict(view=view,variant=variant,pretrained=True,sha256=WEIGHT_SHA,seconds=time.perf_counter()-start,fit_calibration_session=int(min(g))))
        for name,x,t in views:
            rows.extend(evaluate(x,y,g,t,truth,1201,name))
            for seed in (1201,1207,1213):
                for d in (256,512,1024,4096):rows.extend(evaluate(x,y,g,t,truth,seed,name,d))
    return dict(metadata=meta,rows=rows,pretrained_executed=bool(weights),feature_records=features_log,scope='Sample only; official session split; per-session supervised prototype updates; same pixel features by view; depth display not metric depth; no matched test pairs, no fusion; retained numerical state excludes projection workspace and CNN; no full CORe50 claim')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',required=True);p.add_argument('--weights');p.add_argument('--out',required=True);a=p.parse_args();r=run(a.data,a.weights);Path(a.out).write_text(json.dumps(r,indent=2)+'\n');print('rows',len(r['rows']),r['metadata'])
