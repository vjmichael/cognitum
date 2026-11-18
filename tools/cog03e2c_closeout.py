"""Train-only tuning and matched numeric-state budget comparisons; CPU research only."""
import argparse,json,contextlib,io,time
from pathlib import Path
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.kernel_ridge import KernelRidge
from cognitum.research.hdc_regression import Regression,split_conformal,mixture_reference,mixture_predict
from cognitum.research.hdc_regression_closeout import ScaledEncoder,PackedRegHD,StreamingRidge
from cognitum.research.hdlib_classical import load_classical,WHEEL_SHA
from tools.cog03e2c_pilot import data

def run(wheel,quick=False):
    native=load_classical(wheel)['regression'];from hdlib.vector import Vector
    rows=[];parity=[]
    for name in (['synthetic'] if quick else ['diabetes','synthetic']):
      for seed in ([901] if quick else [901,913]):
        x,y,cal,ycal,t,yt,ood,yood=data(name,seed);mu=x.mean(0);sd=np.where(x.std(0)>0,x.std(0),1);x,cal,t=[(a-mu)/sd for a in (x,cal,t)];ood=None if ood is None else (ood-mu)/sd;ym=y.mean();ys=max(y.std(),1e-12);yn=(y-ym)/ys;ix=np.random.default_rng(seed+71).permutation(len(x));tr,va=ix[:int(.8*len(x))],ix[int(.8*len(x)):]
        def record(arm,d,predict,model_bytes,train_bytes,budget=None,**kw):
            pc,pt=predict(cal)*ys+ym,predict(t)*ys+ym;rad=split_conformal(ycal,pc);err=pt-yt;po=None if ood is None else predict(ood)*ys+ym
            assert np.isfinite(pt).all() and (budget is None or train_bytes<=budget)
            rows.append(dict(dataset=name,seed=seed,arm=arm,dim=d,n=len(t),rmse=float(np.sqrt(np.mean(err**2))),mae=float(np.mean(abs(err))),coverage90=float(np.mean(abs(err)<=rad)),width90=2*rad,ood_rmse=None if po is None else float(np.sqrt(np.mean((po-yood)**2))),model_numeric_bytes=int(model_bytes+mu.nbytes+sd.nbytes+16),explicit_training_bound_bytes=int(train_bytes),budget=budget,**kw))
        def choose(kind,d,budget=None):
            options=[]
            for scale in (.2,.5,1.,2.):
              for alpha in (.01,.1,1.,10.):
                e=ScaledEncoder(x.shape[1],d,seed,kind,scale)
                if budget is None:
                    h=e.encode(x[tr]);hm=h.mean(0);m=Regression('ridge',alpha=alpha).fit(h-hm,yn[tr]);p=m.predict(e.encode(x[va])-hm)
                else:
                    m=StreamingRidge(e,alpha,budget).fit(x[tr],yn[tr]);p=m.predict(x[va])
                options.append((float(np.mean((p-yn[va])**2)),scale,alpha))
            _,scale,alpha=min(options);return scale,alpha
        for d in ([32] if quick else [64,256]):
          for kind in ('reghd','rff'):
            scale,alpha=choose(kind,d);e=ScaledEncoder(x.shape[1],d,seed,kind,scale);h=e.encode(x);hm=h.mean(0);m=Regression('ridge',alpha=alpha).fit(h-hm,yn)
            # Uncapped batch arm: upper bound not claimed; count materialized H + model only.
            record(kind+'_tuned_ridge',d,lambda a:m.predict(e.encode(a)-hm),e.nbytes+m.nbytes+hm.nbytes,h.nbytes+e.nbytes+m.nbytes+hm.nbytes,scale=scale,alpha=alpha,training_bound_kind='partial batch arrays, no cap')
          # Actual native binary versus independent packed binary. Preserve raw scale defect;
          # gain calibration uses training only, separate conformal calibration set untouched.
          e=ScaledEncoder(x.shape[1],d,seed,'reghd');init=np.random.default_rng(seed+1).choice([-1.,1.],(3,d));rate=.5/d
          m=native.RegressionModel(d,x.shape[1],k_models=3,iterations=5,learning_rate=rate);m.encoder.base_hypervectors=e.w.copy();m.encoder.biases=e.b.copy();m.cluster_models_int=[v.copy() for v in init];m.cluster_models_b=[Vector(vtype='bipolar',vector=v.copy()) for v in init]
          with contextlib.redirect_stdout(io.StringIO()):m.fit(x[tr],yn[tr])
          c,w=mixture_reference(e.encode(x[tr]),yn[tr],init,5,rate);m.set_quantized_prediction_mode(True);packed=PackedRegHD(c,w);err=float(np.max(np.abs(m.predict(t)-packed.predict(e.encode(t)))));assert err<1e-8
          record('native_binary_packed_parity',d,lambda a:packed.predict(e.encode(a)),e.nbytes+packed.nbytes,e.nbytes+c.nbytes+w.nbytes+packed.nbytes,training_bound_kind='partial persistent arrays, no cap');packed.calibrate(e.encode(x[va]),yn[va]);record('packed_calibrated',d,lambda a:packed.predict(e.encode(a)),e.nbytes+packed.nbytes,e.nbytes+c.nbytes+w.nbytes+packed.nbytes,training_bound_kind='partial persistent arrays, no cap')
          record('mixture_float',d,lambda a:mixture_predict(e.encode(a),c,w),e.nbytes+c.nbytes+w.nbytes,e.nbytes+c.nbytes+w.nbytes,training_bound_kind='partial persistent arrays, no cap');parity.append(dict(dataset=name,seed=seed,dim=d,queries=len(t),max_error=err,packed_head_bytes=packed.nbytes,dense_head_bytes=c.nbytes+w.nbytes))
        for budget in ([8192] if quick else [8192,32768]):
          # Account for common preprocessing state in the total budget; data and implicit BLAS allocations excluded.
          common=mu.nbytes+sd.nbytes+16;avail=budget-common
          for kind in ('reghd','rff'):
            d=max(k for k in range(1,257) if 8*(x.shape[1]+1)*k+8*(4*k*k+16*k+16)<=avail);scale,alpha=choose(kind,d,avail);m=StreamingRidge(ScaledEncoder(x.shape[1],d,seed,kind,scale),alpha,avail).fit(x,yn);record(kind+'_streaming',d,m.predict,m.nbytes,m.numeric_bound+common,budget,scale=scale,alpha=alpha,training_bound_kind='explicit numeric workspace estimate')
          # Matched cap baseline: ordinary linear ridge is far below cap.
          dim=x.shape[1];bound=8*(4*dim*dim+16*dim+16)+common;assert bound<=budget
          options=[(np.mean((Ridge(alpha=a).fit(x[tr],yn[tr]).predict(x[va])-yn[va])**2),a) for a in (.01,.1,1.,10.)];alpha=min(options)[1];r=Ridge(alpha=alpha).fit(x,yn);record('raw_ridge',dim,r.predict,r.coef_.nbytes+8,bound,budget,alpha=alpha,training_bound_kind='explicit estimated solver arrays; library internals excluded')
    return {'schema':'cognitum.cog03e2c.closeout.v1','wheel_sha256':WHEEL_SHA,'rows':rows,'quantized_parity':parity,'budget_scope':'explicit numeric arrays estimate; external data, framework, BLAS workspaces and temporary process allocations excluded','production_enabled':False}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wheel',required=True);p.add_argument('--out',required=True);p.add_argument('--quick',action='store_true');a=p.parse_args();Path(a.out).write_text(json.dumps(run(a.wheel,a.quick),indent=2,allow_nan=False)+'\n',encoding='utf8')
