"""H12 matched CPU HDC pipeline profile. Research only; no hardware or energy claim."""
import argparse,hashlib,json,os,platform,time,tempfile
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits,threadpool_info
from cognitum.research.hdc_hardware import pack
from tools.cog03f_dispatch_pilot import build

def timed(fn):
    t=time.perf_counter_ns();r=fn();return r,time.perf_counter_ns()-t

def norm(x,m,s):return np.clip((x-m)/s,-5,5).astype(np.float32,copy=False)
def fit(x,y,cal,d,seed):
    m=cal.mean(0,dtype=np.float64).astype(np.float32);s=np.maximum(cal.std(0),.05).astype(np.float32)
    w=(2*np.random.default_rng(seed).integers(0,2,(x.shape[1],d),dtype=np.int8)-1).astype(np.float32)
    b=norm(x,m,s)@w>=0;labels,ix=np.unique(y,return_inverse=True);state=np.zeros((len(labels),d),np.int32)
    np.add.at(state,ix,np.where(b,1,-1).astype(np.int32));return m,s,w,labels,state<0,state.nbytes

def pack_generated(bits):
    # Only internal threshold results, never externally supplied integer payload.
    if bits.dtype!=np.bool_ or bits.ndim!=2 or not len(bits) or not 1<=bits.shape[1]<=65536:raise ValueError('generated boolean rows')
    a=np.packbits(bits,axis=1,bitorder='little')
    if a.shape[1]%8:a=np.pad(a,((0,0),(0,(-a.shape[1])%8)))
    return np.ascontiguousarray(a).view('<u8')

def head(f,arm):return (1-2*f[4].astype(np.float32)) if arm=='dense' else (pack_generated(f[4]) if arm=='packed_generated' else pack(f[4].astype(np.uint8)))
def predict(x,f,p,native,arm,feature=None):
    m,s,w,labels,_,_=f;d=w.shape[1];r={};start=time.perf_counter_ns()
    if feature is not None:x,r['visual_features']=timed(lambda:feature(x))
    x,r['normalize']=timed(lambda:norm(x,m,s));z,r['project']=timed(lambda:x@w);b,r['threshold']=timed(lambda:z<0)
    q,r['representation']=timed(lambda:1-2*b.astype(np.float32) if arm=='dense' else (pack_generated(b) if arm=='packed_generated' else pack(b.astype(np.uint8))))
    a,r['score']=timed(lambda:(q@p.T).astype(np.int32) if arm=='dense' else native.scores(q,p,d));y,r['classify']=timed(lambda:labels[a.argmax(1)])
    r['total']=time.perf_counter_ns()-start;return y,a,r

def compare(x,t,y,truth,cal,native,ds,batches,name,repeats=9,feature=None,images=None):
    rows=[];train=[]
    for d in ds:
        f,ft=timed(lambda:fit(x,y,cal,d,1201));heads={};prep={}
        for a in ('dense','packed','packed_generated'):heads[a],prep[a]=timed(lambda:head(f,a))
        m,s,w,labels,bits,state_bytes=f
        train.append(dict(workload=name,d=d,classes=len(labels),train_n=len(x),fit_ns=ft,prepare_ns=prep,accumulator_bytes=state_bytes,projection_bytes=w.nbytes,normalization_bytes=m.nbytes+s.nbytes,head_bytes={k:v.nbytes for k,v in heads.items()}))
        for b in batches:
            if not 1<=b<=len(t):raise ValueError('batch')
            src=t[:b] if feature is None else images[:b];ref,rr,_=predict(src,f,heads['dense'],native,'dense',feature);ts={a:[] for a in heads}
            for a in heads:
                pred,scores,_=predict(src,f,heads[a],native,a,feature);np.testing.assert_array_equal(scores,rr);np.testing.assert_array_equal(pred,ref)
            for rep in range(repeats):
                for a in (tuple(heads) if rep%2==0 else tuple(reversed(heads))):
                    pred,scores,st=predict(src,f,heads[a],native,a,feature);np.testing.assert_array_equal(scores,rr);np.testing.assert_array_equal(pred,ref);ts[a].append(st)
            for a,ms in ts.items():
                stages={k:{'median_ms':float(np.median([v[k] for v in ms])/1e6),'p95_ms':float(np.percentile([v[k] for v in ms],95)/1e6),'samples_ns':[v[k] for v in ms]} for k in ms[0]}
                rows.append(dict(workload=name,dimension=d,batch=b,classes=len(labels),arm=a,score_parity=True,prediction_hash=hashlib.sha256(ref.tobytes()).hexdigest(),score_hash=hashlib.sha256(rr.tobytes()).hexdigest(),accuracy=float(np.mean(ref==truth[:b])),stages=stages,head_bytes=heads[a].nbytes,shared_projection_bytes=w.nbytes,shared_normalization_bytes=m.nbytes+s.nbytes,query_operand_bytes=b*d*4 if a=='dense' else b*((d+63)//64)*8,score_output_bytes=b*len(labels)*4))
    return rows,train

def run(quick=False,data=None,weights=None,visual_cached_only=False):
    from sklearn.datasets import load_digits
    from sklearn.model_selection import train_test_split
    d=load_digits();x,t,y,truth=train_test_split(d.data.astype(np.float32),d.target,test_size=.25,stratify=d.target,random_state=1201);rows=[];training=[];assets={};visual=[]
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=os.name=='nt') as td,threadpool_limits(limits=1):
        native,meta=build(td)
        def add(*args,**kw):
            a,b=compare(*args,**kw);rows.extend(a);training.extend(b)
        add(x,t,y,truth,x,native,(256,1024) if quick else (256,512,1024,2048,4096,10000),(1,16) if quick else (1,16,128,450),'digits_features',3 if quick else 9)
        if not quick:
            rng=np.random.default_rng(1201)
            for k in (64,256):
                yy=np.repeat(np.arange(k),4);xx=rng.normal(size=(len(yy),64)).astype(np.float32);tt=rng.normal(size=(128,64)).astype(np.float32)
                add(xx,tt,yy,np.arange(128)%k,xx,native,(1024,4096,10000),(1,16,128),f'synthetic_{k}_classes')
        print('feature workloads complete',len(rows),flush=True)
        if data is not None or weights is not None:
            if data is None or weights is None:raise ValueError('both data and weights required')
            import torch
            from tools.cog03f2_core50 import read_sample,digest
            from tools.cog03e2g_cifar import RGBMobileNet,WEIGHT_SHA
            if digest(weights)!=WEIGHT_SHA:raise ValueError('checkpoint mismatch')
            torch.set_num_threads(1);(samples,assets),load=timed(lambda:read_sample(data));assets['checkpoint_sha256']=WEIGHT_SHA;assets['archive_read_validate_crop_ns']=load
            tr=[(k,v[1]) for k,v in sorted(samples.items()) if k[0]=='train' and k[1]=='C'];te=[(k,v[1]) for k,v in sorted(samples.items()) if k[0]=='test' and k[1]=='C'];train_im=np.stack([v for _,v in tr]).transpose(0,3,1,2);test_im=np.stack([v for _,v in te]).transpose(0,3,1,2);yy=np.array([k[3] for k,_ in tr]);tt=np.array([k[3] for k,_ in te]);sess=np.array([k[2] for k,_ in tr]);cal=train_im[sess==sess.min()]
            for variant in ('fp32','ptq'):
                m,init=timed(lambda:RGBMobileNet(weights,variant,cal))
                def feature(im):
                    f,q=m.batch(im);return f.astype(np.float32) if q is None else (f.astype(np.float32)-q[1])*q[0]
                xf,tns=timed(lambda:feature(train_im));tf,vns=timed(lambda:feature(test_im));visual.append(dict(variant=variant,init_ns=init,training_extraction_ns=tns,heldout_extraction_ns=vns,train_images=len(tr),test_images=len(te)))
                add(xf,tf,yy,tt,xf[sess==sess.min()],native,(256,512,1024,4096),(1,16,115),f'core50_{variant}_cached')
                if not visual_cached_only:add(xf,tf,yy,tt,xf[sess==sess.min()],native,(1024,4096),(1,16),f'core50_{variant}_image_to_class',3,feature=feature,images=test_im)
                print('visual complete',variant,len(rows),flush=True)
        return dict(scope='research-only; one CPU thread; warm resident heads; model init and training separate; decoded cropped images to label for visual arms; no query file IO, energy, or physical claims; array bytes not entire process RSS',rows=rows,training=training,visual_extraction=visual,assets=assets,build=meta,platform=platform.platform(),python=platform.python_version(),numpy=np.__version__,threadpools=threadpool_info(),native_capabilities=native.capabilities)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--quick',action='store_true');p.add_argument('--visual-cached-only',action='store_true');p.add_argument('--data');p.add_argument('--weights');p.add_argument('--out',required=True);a=p.parse_args();r=run(a.quick,a.data,a.weights,a.visual_cached_only);Path(a.out).write_text(json.dumps(r,indent=2)+'\n',encoding='utf8');print('completed',len(r['rows']),'timing rows,',len(r['training']),'training rows')
