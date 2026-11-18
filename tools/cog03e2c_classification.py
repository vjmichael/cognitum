"""Classical hdlib source isolation, outer hold-out and exact cosine oracle."""
import argparse,json,sys,os,multiprocessing as mp
from pathlib import Path
import numpy as np
from sklearn.datasets import load_iris,load_wine
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from cognitum.research.hdlib_classical import load_classifier,WHEEL_SHA

# multiprocessing spawn imports this entry module before unpickling native tasks.
# Only the explicit research stepwise child receives the vetted classical loader.
if __name__ == '__mp_main__' and os.environ.get('COG03E2C_CLASSIFIER_SPAWN_WHEEL'):
    load_classifier(os.environ['COG03E2C_CLASSIFIER_SPAWN_WHEEL'])

def run(wheel,quick=False,stepwise=False):
    _,Cls=load_classifier(wheel)
    from hdlib.vector import Vector
    rows=[];selections=[]
    for name in (['iris'] if quick else ['iris','wine']):
      x,y=(load_iris(return_X_y=True) if name=='iris' else load_wine(return_X_y=True));labels=np.array([str(v) for v in y])
      for seed in ([931] if quick else [931,937]):
        a,b=train_test_split(np.arange(len(y)),test_size=.3,stratify=y,random_state=seed)
        scaler=StandardScaler().fit(x[a]);tr=scaler.transform(x[a]);te=scaler.transform(x[b]);ya=labels[a];yb=labels[b]
        for dim in ([128] if quick else [128,512]):
          m=Cls(size=dim,levels=8);m.fit(tr.tolist(),ya.tolist(),seed=seed)
          # Avoid native fit(all)+test_indices leakage. Sum training-only point vectors.
          classes=sorted(m.classes);p=np.stack([np.sum([m.space.space[f'point_{i}'].vector for i in range(len(ya)) if ya[i]==c],axis=0) for c in classes]);vectors=[Vector(vtype='bipolar',vector=v,tags={c}) for c,v in zip(classes,p)]
          # Upstream encoder defaults out-of-range and last interval to level 0; preserve and report.
          h=[m._encode_point(v.tolist()) for v in te];pred=[m._predict_vector(v,vectors)[0] for v in h];hv=np.stack([v.vector for v in h]);s=(hv@p.T)/np.maximum(np.linalg.norm(hv,axis=1)[:,None]*np.linalg.norm(p,axis=1),1e-12);oracle=np.array(classes)[np.argmax(s,axis=1)]
          # Zero-vector ties are ambiguous in upstream; independently compare nondegenerate rows.
          valid=(np.linalg.norm(hv,axis=1)>0)&np.all(np.linalg.norm(p,axis=1)>0);assert np.array_equal(np.array(pred)[valid],oracle[valid])
          raw=LogisticRegression(max_iter=2000).fit(tr,ya).predict(te)
          rows.append({'dataset':name,'seed':seed,'dim':dim,'n':len(b),'native_correct':int(np.sum(np.array(pred)==yb)),'logistic_correct':int(np.sum(raw==yb)),'oracle_cases':int(valid.sum()),'oracle_disagreements':0,'out_of_range_values':int(np.count_nonzero((te<m.min_value)|(te>m.max_value))),'fit_train_only':True})
        # Execute actual native stepwise scorer on outer training only. Its internal folds
        # share fitted level bounds; not a leakage-free inner CV or deterministic seed.
        candidates=[{i} for i in range(min(4,tr.shape[1]))];scores=[]
        m=Cls(size=128,levels=4)
        for c in candidates:
            f,score=m._stepwise_regression_iter(c,tr.tolist(),ya.tolist(),cv=3);scores.append([int(next(iter(f))),float(score)])
        selections.append({'dataset':name,'seed':seed,'native_single_feature_scores':scores,'outer_test_excluded':True,'inner_encoding_shared':True,'native_rng_unseeded':True})
    native_stepwise=None
    if stepwise:
        # Run the actual upstream feature selection method on outer-training Iris.
        # Force portable spawn in the CLI; hidden quantum imports are not stubbed.
        x,y=load_iris(return_X_y=True);a,b=train_test_split(np.arange(len(y)),test_size=.3,stratify=y,random_state=931)
        z=StandardScaler().fit(x[a]).transform(x[a]);labels=[str(v) for v in y[a]]
        os.environ['COG03E2C_CLASSIFIER_SPAWN_WHEEL']=str(Path(wheel).resolve())
        try:
            m=Cls(size=128,levels=4);imp,sc,best,count=m.stepwise_regression(z.tolist(),[str(i) for i in range(z.shape[1])],labels,cv=3,method='backward',n_jobs=1,threshold=0.)
        finally:os.environ.pop('COG03E2C_CLASSIFIER_SPAWN_WHEEL',None)
        native_stepwise={'importance':imp,'scores':sc,'best_importance':best,'models':count,'outer_test_excluded':True,'inner_encoding_shared':True,'native_rng_unseeded':True,'start_method':mp.get_start_method()}
    return {'native_stepwise':native_stepwise,'wheel_sha256' :WHEEL_SHA,'class_source_isolated':True,'normal_import':False,'quantum_imported':any(k.startswith('qiskit') or k=='mthree' for k in sys.modules),'rows':rows,'selection':selections}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wheel',required=True);p.add_argument('--out',required=True);p.add_argument('--quick',action='store_true');p.add_argument('--stepwise',action='store_true');a=p.parse_args();mp.set_start_method('spawn');Path(a.out).write_text(json.dumps(run(a.wheel,a.quick,a.stepwise),indent=2,allow_nan=False)+'\n',encoding='utf8')
