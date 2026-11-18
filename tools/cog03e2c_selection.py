"""Independent training-only classification/feature selection controls."""
import argparse,json
from pathlib import Path
import numpy as np
from sklearn.datasets import load_wine,load_breast_cancer
from sklearn.model_selection import train_test_split
from sklearn.feature_selection import f_classif
from sklearn.linear_model import LogisticRegression
from cognitum.research.hdc_regression import Encoder,FisherSelector

def run():
 rows=[]
 for name,loader in [('wine',load_wine),('breast_cancer',load_breast_cancer)]:
    x,y=loader(return_X_y=True)
    for seed in [901,913]:
      a,b=train_test_split(np.arange(len(y)),test_size=.25,stratify=y,random_state=seed);mu=x[a].mean(0);sd=x[a].std(0);sd=np.where(sd>0,sd,1);train=(x[a]-mu)/sd;test=(x[b]-mu)/sd
      for k in [min(5,x.shape[1]),x.shape[1]]:
        sel=FisherSelector(k).fit(train,y[a]);score,_=f_classif(train,y[a]);expected=np.lexsort((np.arange(len(score)),-score))[:k];assert np.array_equal(sel.indices,expected)
        xt,xv=sel.transform(train),sel.transform(test);e=Encoder(k,128,seed,'rff');ht,hv=e.encode(xt),e.encode(xv);labels=np.unique(y[a]);proto=np.stack([ht[y[a]==v].mean(0) for v in labels]);sim=(hv@proto.T)/np.maximum(np.linalg.norm(hv,axis=1)[:,None]*np.linalg.norm(proto,axis=1),1e-12);p=labels[sim.argmax(1)]
        q=LogisticRegression(max_iter=1000).fit(xt,y[a]).predict(xv)
        for arm,pred in [('independent_hdc_centroid',p),('selected_logistic',q)]:rows.append({'dataset':name,'seed':seed,'k':k,'arm':arm,'correct':int(np.sum(pred==y[b])),'n':len(b),'selected':sel.indices.tolist(),'ranking_parity':True})
 return {'rows':rows,'native_hdlib_classification':False,'scope':'independent feature selection and classification; never test labels during fit'}
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--out',required=True);v=a.parse_args();Path(v.out).write_text(json.dumps(run(),indent=2)+'\n')
