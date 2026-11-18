"""Pinned native compressed learners and custom inference, paired inputs.
One benchmark child per dataset/seed/dimension; logical retained numeric
payload is distinct from process peak RSS and per-arm training workspace.
"""
import argparse,hashlib,json,time,io
from pathlib import Path
import numpy as np
import torch
from torchhd import classifiers
from torch.utils.data import DataLoader,TensorDataset
from tools.cog03e1_pilot import dataset,state_native,payload
from cognitum.research.hdc_learning import cosine_scores
from cognitum.research.hdc_compressed_learning import PackedTernary,PackedLevels,SparseRows,PackedFold,quant_train,lehdc_train,sparse_train


def run(name,seed,d,epochs):
    torch.set_num_threads(1)
    a,y,b,t,lo,scale,split=dataset(name,seed);c=int(y.max())+1;f=a.shape[1];at,bt=torch.tensor(a),torch.tensor(b);loader=DataLoader(TensorDataset(at,torch.tensor(y)),batch_size=32,shuffle=False);rows=[]
    scale_bytes=lo.nbytes+scale.nbytes
    def record(arm,s,train,infer,bytes_,**kw):
        p=s.argmax(1);assert len(p)==len(t) and np.isfinite(s).all();rows.append(dict(arm=arm,correct=int((p==t).sum()),n=len(t),dataset=name,seed=seed,d=d,split=split,train_seconds=train,infer_seconds=infer,retained_numeric_bytes=int(bytes_+scale_bytes),prediction_sha256=hashlib.sha256(p.astype('<i8').tobytes()).hexdigest(),**kw));return p
    def native_state(m):return sum(v.nbytes for v in state_native(m).values())+(m.chunk_keys.numel()*m.chunk_keys.element_size() if hasattr(m,'chunk_keys') else 0)
    fixed=dict(n_levels=16,min_level=0,max_level=1)
    for label,cls,kw in [('vanilla',classifiers.Vanilla,{}),('comp',classifiers.CompHD,{'chunks':4}),('sparse_dim',classifiers.SparseHD,{'epochs':epochs,'sparsity':.75,'sparsity_type':'dimension'}),('sparse_class',classifiers.SparseHD,{'epochs':epochs,'sparsity':.75,'sparsity_type':'class'}),('quant',classifiers.QuantHD,{'epochs':epochs}),('lehdc',classifiers.LeHDC,{'epochs':epochs,'dropout_rate':0.})]:
        torch.manual_seed(seed);m=cls(f,d,c,**fixed,**kw);keys=getattr(m,'feat_keys',None) or m.keys;e=PackedLevels(keys.weight.detach().numpy(),m.levels.weight.detach().numpy());h=m.encoder(at).detach().numpy();g=m.encoder(bt).detach().numpy();start=time.perf_counter();m.fit(loader);train=time.perf_counter()-start;m.eval();start=time.perf_counter();s=m(bt).detach().numpy();infer=time.perf_counter()-start;w=m.model.weight.detach().numpy();native_inference_bytes=keys.weight.numel()*keys.weight.element_size()+m.levels.weight.numel()*m.levels.weight.element_size()+w.nbytes+(m.chunk_keys.numel()*m.chunk_keys.element_size() if hasattr(m,'chunk_keys') else 0)+scale_bytes;p=record('native_'+label,s,train,infer,native_state(m),native_inference_numeric_bytes=native_inference_bytes,zero_fraction=float((w==0).mean()),scope='complete native training state, including shadow/count if present')
        start=time.perf_counter();enc=e.encode(b);encode_seconds=time.perf_counter()-start;assert np.array_equal(enc,g)
        if label=='comp':
            k=PackedFold(m.chunk_keys.numpy());start=time.perf_counter();fg=k.fold(enc);# fitted counts are integer, bounded to int16 for this inference fixture
            assert np.array_equal(w,w.astype('int16'));wc=w.astype('int16');sc=cosine_scores(fg,wc.astype('float64'));elapsed=time.perf_counter()-start;record('packed_comp',sc,0,encode_seconds+elapsed,e.bytes+wc.nbytes+k.bytes,encoder_bytes=e.bytes,prototype_bytes=wc.nbytes,encoder_scratch_lower_bound_bytes=9*d,encoded_query_batch_bytes=enc.nbytes,disagreements=int((sc.argmax(1)!=p).sum()),score_max_error=float(np.max(np.abs(sc-s))),scope='packed levels, int16 folded prototype, chunk sign bits; full-score reference uses float64')
        elif label.startswith('sparse'):
            start=time.perf_counter();cw=sparse_train(h,y,c,epochs=epochs,sparsity=.75,mode='dimension' if label=='sparse_dim' else 'class');ct=time.perf_counter()-start;bank=SparseRows(cw);start=time.perf_counter();sc=bank.scores(enc.astype('float32'));elapsed=time.perf_counter()-start;dense=cosine_scores(g,cw);assert np.allclose(sc,dense,atol=1e-7);record('custom_'+label,sc,ct,encode_seconds+elapsed,e.bytes+bank.bytes,zero_fraction=float((cw==0).mean()),encoder_bytes=e.bytes,prototype_bytes=bank.bytes,encoder_scratch_lower_bound_bytes=9*d,encoded_query_batch_bytes=enc.nbytes,dense_disagreements=int((sc.argmax(1)!=dense.argmax(1)).sum()),scope='corrected training; exact sparse inference; not native prediction equivalence')
        elif label in ('quant','lehdc'):
            trainer=quant_train if label=='quant' else lehdc_train;start=time.perf_counter();shadow,cw=trainer(h,y,c,epochs=epochs);ct=time.perf_counter()-start;bank=PackedTernary(cw);start=time.perf_counter();sc=bank.scores(PackedTernary(enc));elapsed=time.perf_counter()-start;assert np.array_equal(sc,enc.astype('int32')@cw.astype('int32').T);record('packed_'+label,sc,ct,encode_seconds+elapsed,e.bytes+bank.bytes,encoder_bytes=e.bytes,prototype_bytes=bank.bytes,encoder_scratch_lower_bound_bytes=9*d,encoded_query_batch_bytes=enc.nbytes,zero_fraction=float((cw==0).mean()),disagreements=int((sc.argmax(1)!=p).sum()),native_weight_disagreements=int((cw!=w).sum()),shadow_bytes=shadow.nbytes,scope='preencoded custom training, packed encoder/full query+ternary dot')
        else:
            start=time.perf_counter();sc=cosine_scores(enc.astype('float32'),w);elapsed=time.perf_counter()-start;record('packed_vanilla',sc,0,encode_seconds+elapsed,e.bytes+w.nbytes,encoder_bytes=e.bytes,prototype_bytes=w.nbytes,encoder_scratch_lower_bound_bytes=9*d,encoded_query_batch_bytes=enc.nbytes,disagreements=int((sc.argmax(1)!=p).sum()),scope='packed encoder and dense prototype')
    if name!='synthetic':
        from sklearn.linear_model import LogisticRegression
        from sklearn.svm import SVC
        for label,m in [('logistic',LogisticRegression(max_iter=1000,random_state=seed)),('rbf_svm',SVC(C=1.,gamma='scale',decision_function_shape='ovr'))]:
            start=time.perf_counter();m.fit(a,y);ct=time.perf_counter()-start;start=time.perf_counter();p=m.predict(b);elapsed=time.perf_counter()-start;arrays={k:v for k,v in vars(m).items() if isinstance(v,np.ndarray)};s=np.eye(c)[p];record(label,s,ct,elapsed,sum(v.nbytes for v in arrays.values()),scope='fitted ndarray state; metadata excluded')
    return rows


def main():
    p=argparse.ArgumentParser();p.add_argument('--quick',action='store_true');p.add_argument('--dataset',default='digits',choices=['digits','wine']);p.add_argument('--seed',type=int,default=811);p.add_argument('--dimension',type=int,default=128);p.add_argument('--out',required=True);args=p.parse_args();rows=run('synthetic' if args.quick else args.dataset,args.seed,64 if args.quick else args.dimension,4);info={}
    try:
        import resource
        info={'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'address_space_limit':resource.getrlimit(resource.RLIMIT_AS)[0]}
    except ImportError:pass
    Path(args.out).write_text(json.dumps({'rows':rows,'process':info},indent=2)+'\n',encoding='utf8')
if __name__=='__main__':main()
