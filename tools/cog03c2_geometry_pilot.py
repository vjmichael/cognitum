"""Fixed synthetic 5x5 central-pixel learning/decoding geometry pilot.
Not a replication of the entire Poduval et al. study, or a natural-image test.
"""
import json
from pathlib import Path
import numpy as np
from cognitum.research.hdc_frontier_encoders import GaussianPhase


def main(out):
    rows=[];points=np.array(list(np.ndindex(5,5)),dtype=np.float64)
    for seed in (52711,52729,52747,52769,52783):
        rng=np.random.default_rng(seed);train=rng.integers(0,2,(400,25));test=rng.integers(0,2,(400,25));labels=train[:,12]
        for width in (.125,.5,1.,2.,4.):
            enc=GaussianPhase.sample(1024,np.array([width,width]),seed);basis=enc.encode(points)
            a=train.astype(np.float32)@basis;b=test.astype(np.float32)@basis
            c=np.stack([a[labels==k].sum(0) for k in (0,1)]);pred=np.argmax((b@c.conj().T).real/np.linalg.norm(c,axis=1),axis=1)
            raw=(b@basis.conj().T).real/1024;decoded=raw>raw.mean(1,keepdims=True)
            rows.append(dict(seed=seed,width=width,class_correct=int(np.sum(pred==test[:,12])),class_n=len(test),pixel_correct=int(np.sum(decoded==test)),pixel_n=test.size,center_decoded=int(np.sum(decoded[:,12]==test[:,12]))))
    Path(out).write_text(json.dumps({'rows':rows,'oracle':'direct central pixel and raw input recover all labels and pixels; geometry characterization only'},indent=2)+'\n')
if __name__=='__main__':
    import sys
    main(sys.argv[1])
