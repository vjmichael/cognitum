"""Bounded real-data protocol for C2C. Fetch only explicit pinned public research
fixtures on opt-in --acquire, verify Git blob hashes, never fetch during import.
No original-author accuracy reproduction claim: independent propagation-style
histogram, gap-collapsed gappy pair and predeclared shared classifier protocols.
"""
import argparse, hashlib, io, json, math, os, sys, time
from pathlib import Path
import urllib.request
from collections import Counter
import numpy as np
from cognitum.research.hdc_frontier_encoders import NysHD, StreamedNysHD
from cognitum.research.hdc_structured_encoders import gappy_pair_counts, propagation_counts, polygon_encode
from cognitum.research.hdc_encoders import CodebookSpec

PROMOTER=('https://raw.githubusercontent.com/kanishkanandhkumar/BioML-Promoter-Predictor/5aa31b0be28dabed563028ec80d37a33746f972e/bioinfo_pipeline/data/promoters.data','4b876802b3955fce66670521a7146ae3609e9dfc')
MUTAG_ROOT='https://raw.githubusercontent.com/AntonioLonga/PytorchGeometricTutorial/2d0f1911e76a6e777cb2f64b4a66cc8c6f5ef485/Tutorial5/data/TU/MUTAG/raw/'
MUTAG={'MUTAG_A.txt':'b5cabc1d3779d78c11b7e13a4f7476b176a25d0d','MUTAG_graph_indicator.txt':'74f6d678d71ce8dba6f46f7ead258d8a0e5eb8bd','MUTAG_graph_labels.txt':'cd9a9c8228cd1ae63df2dd0570f026cb37e1c472','MUTAG_node_labels.txt':'cc11ed9757bb51b132cef754a7f32624ffb7d236'}


def blob(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()


def acquire_file(path,url,sha,acquire):
    if not path.exists():
        if not acquire:raise FileNotFoundError(path)
        req=urllib.request.Request(url,headers={'User-Agent':'Cognitum-research-fixtures'})
        with urllib.request.urlopen(req,timeout=30) as data:b=data.read(1_000_001)
        if len(b)>1_000_000 or blob(b)!=sha:raise ValueError('unexpected fixture: '+path.name)
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b)
    b=path.read_bytes()
    if blob(b)!=sha:raise ValueError('fixture blob mismatch: '+path.name)
    return b


def promoter_rows(b):
    labels=[];records=[];ids=[]
    for line in b.decode('ascii').splitlines():
        a,i,s=map(str.strip,line.split(','));s=s.upper()
        if a not in ('+','-') or not len(s)==57 or set(s)-set('ACGT'):raise ValueError('Promoter rows')
        labels.append(int(a=='+'));records.append(s);ids.append(i)
    if len(records)!=106 or len(set(ids))!=106 or sum(labels)!=53:raise ValueError('Promoter dataset shape')
    return records,np.asarray(labels),ids


def mutag_rows(data):
    indicator=np.fromstring(data['MUTAG_graph_indicator.txt'].decode(),sep=' ',dtype=np.int64)-1
    y=np.fromstring(data['MUTAG_graph_labels.txt'].decode(),sep=' ',dtype=np.int64)
    nodes=np.fromstring(data['MUTAG_node_labels.txt'].decode(),sep=' ',dtype=np.int64)
    edges=np.array([[int(x)-1 for x in l.split(',')] for l in data['MUTAG_A.txt'].decode().splitlines()],dtype=np.int64)
    if len(y)!=188 or set(y)!= {-1,1} or len(nodes)!=3371 or len(edges)!=7442 or len(nodes)!=len(indicator) or np.any((indicator<0)|(indicator>=len(y))) or np.any((nodes<0)|(nodes>6)) or np.any((edges<0)|(edges>=len(nodes))) or np.any(indicator[edges[:,0]]!=indicator[edges[:,1]]):raise ValueError('MUTAG structure')
    out=[]
    for i in range(len(y)):
        ids=np.flatnonzero(indicator==i);a=np.zeros((len(ids),len(ids)),bool)
        e=edges[indicator[edges[:,0]]==i];idx=np.searchsorted(ids,e);a[idx[:,0],idx[:,1]]=True
        if not np.array_equal(a,a.T) or np.any(np.diag(a)) or int(a.sum())!=len(e):raise ValueError('undirected source')
        out.append((a,nodes[ids]))
    return out,(y==1).astype(np.int64),list(range(len(y)))


def canonical(name,root):
    """Optional source-derived compact offline fixture. Whole-file digest pins
    the transferred representation, verified against connector-derived checks.
    Do not claim these are the byte-identical source files.
    """
    p=root/(name+'-canonical.txt');b=p.read_bytes()
    expected={'promoter':0x4afcc062ff06e0c1,'mutag':0x919c4abad903d105}[name]
    h=14695981039346656037
    for v in b:h=((h^v)*1099511628211)%(2**64)
    if h!=expected:raise ValueError('canonical transfer mismatch')
    rows=[];y=[]
    alphabet='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_'
    for line in b.decode('ascii').splitlines():
        y.append(int(line[0]=='+'))
        if line[0] not in '+-':raise ValueError('label')
        if name=='promoter':
            if len(line)!=58 or set(line[1:])-set('ACGT'):raise ValueError('sequence')
            rows.append(line[1:])
        else:
            lab,edges=line[1:].split(':');n=len(lab);a=np.zeros((n,n),bool)
            if len(edges)%2:raise ValueError('edge pairs')
            for i in range(0,len(edges),2):
                u,v=alphabet.index(edges[i]),alphabet.index(edges[i+1])
                if not 0<=u<v<n or a[u,v]:raise ValueError('edge')
                a[u,v]=a[v,u]=True
            rows.append((a,np.array(list(map(int,lab)),np.int64)))
    if len(rows)!={'promoter':106,'mutag':188}[name]:raise ValueError('row count')
    if name=='mutag' and (sum(len(a) for a,_ in rows),sum(int(a.sum())//2 for a,_ in rows))!=(3371,3721):raise ValueError('graph totals')
    return rows,np.asarray(y),list(range(len(rows))),{'canonical_fnv64':format(h,'016x'),'canonical_sha256':hashlib.sha256(b).hexdigest(),'source_blob_ids':{'promoters.data':PROMOTER[1]} if name=='promoter' else MUTAG}


def fixtures(name,root,acquire):
    if name=='promoter':
        b=acquire_file(root/'promoters.data',*PROMOTER,acquire)
        rows,y,ids=promoter_rows(b);return rows,y,ids,{'promoters.data':PROMOTER[1]}
    if name=='mutag':
        data={f:acquire_file(root/f,MUTAG_ROOT+f,v,acquire) for f,v in MUTAG.items()}
        rows,y,ids=mutag_rows(data);return rows,y,ids,MUTAG
    raise ValueError('dataset')


def split(y,seed):
    r=np.random.default_rng(seed);test=[];train=[]
    for c in sorted(set(y)):
        ids=r.permutation(np.flatnonzero(y==c));k=max(1,round(len(ids)*.2))
        train.extend(ids[k:]);test.extend(ids[:k])
    return np.asarray(sorted(train)),np.asarray(sorted(test))


def counts(rows,name):
    if name=='promoter':return [gappy_pair_counts(s,2,2) for s in rows]
    w=np.random.default_rng(997).normal(size=(8,7))
    return [propagation_counts(a,y,w,steps=3,width=.5) for a,y in rows]


def group_split(counts_by_row,y,seed):
    """Hold out entire identical normalized-count groups, including label
    conflicts. Greedy predefined balance objective, no accuracy-based selection.
    """
    groups={}
    for i,c in enumerate(counts_by_row):
        g=math.gcd(*c.values());signature=tuple(sorted((k,v//g) for k,v in c.items()))
        groups.setdefault(signature,[]).append(i)
    groups=list(groups.values());r=np.random.default_rng(seed)
    groups=[groups[i] for i in r.permutation(len(groups))]
    target=np.bincount(y,minlength=2)*.2;chosen=np.zeros(2);take=[]
    def cost(x):return float(np.sum(((x-target)/np.maximum(target,1))**2))
    for ids in groups:
        v=np.bincount(y[ids],minlength=2)
        if cost(chosen+v)<cost(chosen):take+=ids;chosen+=v
    test=np.array(sorted(take),dtype=np.int64);train=np.setdiff1d(np.arange(len(y)),test)
    if len(set(y[test]))<2 or len(set(y[train]))<2:raise ValueError('group split class coverage')
    return train,test


def vectorize(rows,keys):
    return np.asarray([[r.get(k,0) for k in keys] for r in rows],np.float64)


def normal(x):return x/np.maximum(np.linalg.norm(x,axis=1,keepdims=True),1e-15)


def packed_features(model,c):
    b=np.unpackbits(model.packed(c),axis=1,count=model.dimension,bitorder="little").astype(bool) if isinstance(model,StreamedNysHD) else model.bits(c)
    return 1.-2.*b.astype(np.float64)


def fit_score(x,y,q,epochs=20):
    """Same bounded normalized perceptron refinement for all prototype arms."""
    x=normal(x);q=normal(q);labels=np.unique(y)
    w=np.stack([x[y==v].sum(0) for v in labels]);r=np.random.default_rng(2928)
    for _ in range(epochs):
        for i in r.permutation(len(y)):
            j=int(np.argmax(normal(w)@x[i]));k=int(np.searchsorted(labels,y[i]))
            if j!=k:w[k]+=x[i]*.2;w[j]-=x[i]*.2
    return labels[np.argmax(q@normal(w).T,axis=1)],w,labels


def measure(name,rows,y,seed,arm,dimension=1024,payload_cap=0,grouped=False):
    t=time.perf_counter();c=counts(rows,name);train,test=group_split(c,y,seed) if grouped else split(y,seed)
    keys=sorted(set().union(*(c[i].keys() for i in train)))
    x=normal(vectorize([c[i] for i in train],keys));q=normal(vectorize([c[i] for i in test],keys));ty=y[train]
    rng=np.random.default_rng(seed+1);land_ids=sorted(rng.choice(len(x),min(64,len(x)),replace=False));z=x[land_ids]
    start=time.perf_counter(); model_arrays={};meta={'arm':arm,'dataset':name,'dimension':dimension,'seed':seed,'keys':keys,'normalized_counts':True,'propagation_seed':997,'gappy_pair':[2,2]}
    if arm=='kernel-ridge':
        # Full normalized PSD kernel, fixed regularization, no test tuning.
        labels=np.unique(ty);target=(ty[:,None]==labels).astype(float)
        weights=np.linalg.solve(x@x.T+.1*np.eye(len(x)),target);pred=lambda:labels[np.argmax((q@x.T)@weights,axis=1)];model_arrays={'train':x,'weights':weights,'labels':labels}
    elif arm=='direct-prototype':
        prediction,w,labels=fit_score(x,ty,q);pred=lambda:prediction;model_arrays={'weights':w,'labels':labels}
    else:
        if arm not in ('nystrom','resident','streamed'):raise ValueError('arm')
        root=StreamedNysHD.fit(z@z.T,dimension,seed)
        if payload_cap and arm in ('resident','streamed'):
            # Model-only admission based on train-derived sizes before encoding/testing.
            # 4096 bytes covers NumPy container overhead; exact serialized cap enforced later.
            base=z.nbytes+root.inverse_root.nbytes+np.unique(ty).nbytes+len(json.dumps(meta,separators=(',',':')).encode())+4096
            step=8*(len(np.unique(ty))+(len(z) if arm=='resident' else 0))
            dimension=min(dimension,(payload_cap-base)//step)
            if dimension<1:raise ValueError('model cap too small')
            meta['dimension']=dimension;root=StreamedNysHD(root.inverse_root,dimension,seed)
        ct=x@z.T;cq=q@z.T
        if arm=='nystrom':
            fx=ct@root.inverse_root;fq=cq@root.inverse_root;model=root
        elif arm=='resident':
            model=NysHD.fit(z@z.T,dimension,seed);fx=packed_features(model,ct);fq=packed_features(model,cq)
        else:
            model=root;fx=packed_features(model,ct);fq=packed_features(model,cq)
        prediction,w,labels=fit_score(fx,ty,fq);pred=lambda:prediction;model_arrays={'landmarks':z,'inverse_root':model.inverse_root,'weights':w,'labels':labels}
        if arm=='resident':model_arrays['projection']=model.projection
    # Include exact feature dictionary and metadata in the portable snapshot size.
    built=time.perf_counter();predictions=pred();ended=time.perf_counter()
    buf=io.BytesIO();np.savez(buf,**model_arrays,descriptor=np.frombuffer(json.dumps(meta,separators=(',',':')).encode(),np.uint8));serialized=len(buf.getbuffer())
    if payload_cap and serialized>payload_cap:raise ValueError('serialized model cap exceeded')
    try:
        import resource
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform=='darwin':peak/=1024
    except ImportError:peak=None
    return {'dataset':name,'arm':arm,'seed':seed,'dimension':dimension,'payload_cap':payload_cap,'grouped':grouped,'identical_feature_test_rows':sum(any(np.array_equal(v,u) for u in x) for v in q),'n_train':len(train),'n_test':len(test),'correct':int((predictions==y[test]).sum()),'predictions':predictions.tolist(),'test_ids':test.tolist(),'train_ids':train.tolist(),'landmark_ids':[int(train[i]) for i in land_ids] if arm in ('nystrom','resident','streamed') else [],'numeric_payload_bytes':sum(a.nbytes for a in model_arrays.values()),'serialized_snapshot_bytes':serialized,'feature_seconds':start-t,'build_and_predict_seconds':built-start,'final_score_seconds':ended-built,'peak_rss_kib':peak,'split_sha256':hashlib.sha256(train.astype('<i8').tobytes()+test.astype('<i8').tobytes()).hexdigest()}


def main():
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--acquire',action='store_true');p.add_argument('--canonical',action='store_true');p.add_argument('--grouped',action='store_true');p.add_argument('--payload-cap',type=int,default=0);p.add_argument('--dataset',choices=['promoter','mutag'],required=True);p.add_argument('--arm',choices=['resident','streamed','nystrom','kernel-ridge','direct-prototype'],required=True);p.add_argument('--seed',type=int,default=52811);p.add_argument('--dimension',type=int,default=1024);p.add_argument('--address-limit-mib',type=int,default=0);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.address_limit_mib:
        import resource
        size=a.address_limit_mib*1024**2;resource.setrlimit(resource.RLIMIT_AS,(size,size))
    t=time.perf_counter();rows,y,ids,source=canonical(a.dataset,a.data) if a.canonical else fixtures(a.dataset,a.data,a.acquire);loaded=time.perf_counter();out=measure(a.dataset,rows,y,a.seed,a.arm,a.dimension,a.payload_cap,a.grouped);out.update({'source_blobs':source,'dataset_load_seconds':loaded-t,'address_limit_mib':a.address_limit_mib,'scope':'independent real-data kernel protocol; not original full paper or exact authors split'})
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,indent=2)+'\n',encoding='utf8');print(a.dataset,a.arm,out['correct'],'/',out['n_test'])

if __name__=='__main__':main()
