"""Research-only paired held-out measurements; train-only normalization/calibration."""
import argparse,contextlib,hashlib,io,json,os,time
from pathlib import Path
import numpy as np
from sklearn.datasets import load_diabetes,make_blobs
from sklearn.metrics import adjusted_rand_score,normalized_mutual_info_score
from sklearn.cluster import KMeans
from sklearn.linear_model import Ridge
from sklearn.kernel_ridge import KernelRidge
from cognitum.research.hdc_regression import Encoder,Regression,split_conformal,mixture_reference,mixture_predict
from cognitum.research.hdlib_classical import load_classical,WHEEL_SHA

def data(name,seed):
    rng=np.random.default_rng(seed)
    if name=='diabetes':
        x,y=load_diabetes(return_X_y=True);ix=rng.permutation(len(y));a,b,c=np.split(ix,[265,353]);return x[a],y[a],x[b],y[b],x[c],y[c],None,None
    x=rng.uniform(-2,2,(540,5));f=lambda x:np.sin(2*x[:,0])+x[:,1]*x[:,2]+.3*x[:,3];y=f(x)+rng.normal(0,.1,len(x));ood=rng.uniform(2,4,(90,5));return x[:360],y[:360],x[360:450],y[360:450],x[450:],y[450:],ood,f(ood)

def run(wheel,quick=False):
    native=load_classical(wheel);R=native['regression'];C=native['clustering'];G=native['graph'];from hdlib.vector import Vector
    rows=[];clustering=[];graphs=[];parity=[]
    for name in (['synthetic'] if quick else ['diabetes','synthetic']):
      for seed in ([901] if quick else [901,913]):
        x,y,cal,ycal,t,yt,ood,yood=data(name,seed);mu=x.mean(0);sd=x.std(0);sd=np.where(sd>0,sd,1);x,cal,t=[(a-mu)/sd for a in (x,cal,t)];ood=None if ood is None else (ood-mu)/sd;ym=y.mean();ys=max(y.std(),1e-12);yn=(y-ym)/ys
        for d in ([32] if quick else [64,256]):
          e=Encoder(x.shape[1],d,seed);rff=Encoder(x.shape[1],d,seed,'rff');h,hc,ht=[e.encode(a) for a in (x,cal,t)];ho=None if ood is None else e.encode(ood)
          def record(arm,fit,pred,arrays,enc=0):
            start=time.perf_counter();model=fit();fit_time=time.perf_counter()-start;start=time.perf_counter();pc,pt=pred(model);elapsed=time.perf_counter()-start
            po=None if ood is None else pred(model,True);pt=np.asarray(pt)*ys+ym;pc=np.asarray(pc)*ys+ym;po=None if po is None else np.asarray(po)*ys+ym;rad=split_conformal(ycal,pc);err=pt-yt
            row={'dataset':name,'seed':seed,'dim':d,'arm':arm,'n_train':len(y),'n_cal':len(ycal),'n_test':len(yt),'rmse':float(np.sqrt(np.mean(err**2))),'mae':float(np.mean(abs(err))),'coverage90':float(np.mean(abs(err)<=rad)),'interval_width':2*rad,'ood_rmse':None if po is None else float(np.sqrt(np.mean((po-yood)**2))),'ood_coverage90':None if po is None else float(np.mean(abs(po-yood)<=rad)),'fit_seconds':fit_time,'cal_test_predict_seconds':elapsed,'model_numeric_bytes':int(arrays(model)+enc+mu.nbytes+sd.nbytes+24)};assert np.isfinite(pt).all();rows.append(row);return model,pt
          for kind in ('associative','lms','ridge'):
            record('hdc_'+kind,lambda:Regression(kind,epochs=5).fit(h,yn),lambda m,o=False:m.predict(ho) if o else (m.predict(hc),m.predict(ht)),lambda m:m.nbytes,e.nbytes)
          record('same_encoded_sklearn_ridge',lambda:Ridge(alpha=1,fit_intercept=False).fit(h,yn),lambda m,o=False:m.predict(ho) if o else (m.predict(hc),m.predict(ht)),lambda m:m.coef_.nbytes,e.nbytes)
          record('rff_ridge',lambda:Regression('ridge').fit(rff.encode(x),yn),lambda m,o=False:m.predict(rff.encode(ood)) if o else (m.predict(rff.encode(cal)),m.predict(rff.encode(t))),lambda m:m.nbytes,rff.nbytes)
          record('raw_ridge',lambda:Ridge(alpha=1).fit(x,yn),lambda m,o=False:m.predict(ood) if o else (m.predict(cal),m.predict(t)),lambda m:m.coef_.nbytes+8)
          record('rbf_kernel_ridge',lambda:KernelRidge(alpha=.1,gamma=1/x.shape[1],kernel='rbf').fit(x,yn),lambda m,o=False:m.predict(ood) if o else (m.predict(cal),m.predict(t)),lambda m:m.dual_coef_.nbytes+m.X_fit_.nbytes)
          # Explicit seeded common initial arrays; native constructor itself draws unseeded cluster vectors.
          initial=np.random.default_rng(seed+1).choice([-1.,1.],(3,d));rate=.5/d
          def actual():
            m=R.RegressionModel(d,x.shape[1],k_models=3,iterations=5,learning_rate=rate);m.encoder.base_hypervectors=e.w.copy();m.encoder.biases=e.b.copy();m.cluster_models_int=[v.copy() for v in initial];m.cluster_models_b=[Vector(vtype='bipolar',vector=v.copy()) for v in initial];
            with contextlib.redirect_stdout(io.StringIO()):m.fit(x,yn)
            return m
          m,p=record('hdlib_reghd',actual,lambda m,o=False:m.predict(ood) if o else (m.predict(cal),m.predict(t)),lambda m:sum(v.nbytes for v in m.cluster_models_int+m.regression_models_int)+sum(v.vector.nbytes for v in m.cluster_models_b+m.regression_models_b),e.nbytes)
          cr,wr=mixture_reference(h,yn,initial,5,rate);ref=mixture_predict(ht,cr,wr)*ys+ym;diff=float(np.max(abs(ref-p)));parity.append({'dataset':name,'seed':seed,'dim':d,'max_prediction_error':diff,'cluster_max_error':float(np.max(abs(cr-np.stack(m.cluster_models_int)))),'weight_max_error':float(np.max(abs(wr-np.stack(m.regression_models_int))))});assert diff<1e-8
    for seed in ([901] if quick else [901,913]):
        x,y=make_blobs(n_samples=180,n_features=5,centers=3,cluster_std=1.3,random_state=seed);idx=np.random.default_rng(seed).permutation(len(y));a,b=idx[:120],idx[120:];m=C.ClusteringModel(3,5,size=128,max_iter=15,seed=seed)
        with contextlib.redirect_stdout(io.StringIO()):m.fit(x[a])
        p=m.predict(x[b]);h=np.sign(x[b]@m.projection_matrix_);c=np.stack([v.vector for v in m.centroids_]);s=(h@c.T)/np.maximum(np.linalg.norm(h,axis=1)[:,None]*np.linalg.norm(c,axis=1),1e-12);assert np.array_equal(p,np.argmax(s,axis=1))
        for arm,pred in [('hdlib',p),('raw_kmeans',KMeans(n_clusters=3,n_init=10,random_state=seed).fit(x[a]).predict(x[b])),('encoded_kmeans',KMeans(n_clusters=3,n_init=10,random_state=seed).fit(np.sign(x[a]@m.projection_matrix_)).predict(h))]:clustering.append({'seed':seed,'arm':arm,'ari':adjusted_rand_score(y[b],pred),'nmi':normalized_mutual_info_score(y[b],pred),'n':len(b)})
        edges={('a','b',1),('b','c',1),('c','d',1),('d','a',1)};g=G.GraphModel(size=2048,directed=True,seed=seed);g.fit(edges);tp=fp=fn=tn=0
        for u in 'abcd':
          for v in 'abcd':
            if u==v:continue
            got,dist,th=g.edge_exists(u,v,1,threshold=.65);truth=(u,v,1) in edges;tp+=bool(got and truth);fp+=bool(got and not truth);fn+=bool(not got and truth);tn+=bool(not got and not truth)
        graphs.append({'seed':seed,'tp':tp,'fp':fp,'fn':fn,'tn':tn,'threshold':.65,'exact_set_oracle':True})
    return {'schema':'cognitum.cog03e2c.pilot.v1','wheel_sha256':WHEEL_SHA,'normal_model_import_used':False,'classification_dependency_gate':'blocked; quantum imports required','rows':rows,'native_parity':parity,'clustering':clustering,'graphs':graphs,'production_enabled':False}
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--wheel',required=True);a.add_argument('--out',required=True);a.add_argument('--quick',action='store_true');v=a.parse_args();Path(v.out).write_text(json.dumps(run(v.wheel,v.quick),indent=2,allow_nan=False)+'\n')
