"""Independent IID bipolar role/filler capacity pilot, not a correlated-code guarantee."""
import math
import numpy as np

def expected_signal(k):
    if k<1 or k%2!=1:raise ValueError('odd bundle size')
    return math.comb(k-1,(k-1)//2)/2**(k-1)

def independent_threshold(d,n,alpha):
    if d<1 or n<1 or not 0<alpha<1:raise ValueError('domain')
    return math.sqrt(2*math.log(n/alpha)/d)

def trial(d,k,n,trials,seed):
    if n<2 or d<1 or trials<1 or not 1<=k<=n or k%2!=1:raise ValueError('odd bundle size <= codebook')
    r=np.random.default_rng(seed);success=tie=false_accept=miss=0;signal=[];maxnoise=[];gaps=[];th=independent_threshold(d,n,.01)
    for _ in range(trials):
        fillers=(2*r.integers(0,2,(n,d),dtype=np.int8)-1);role=(2*r.integers(0,2,(k,d),dtype=np.int8)-1);idx=r.choice(n,k,False)
        bundle=np.sign((fillers[idx]*role).sum(0)).astype(np.int8);q=bundle*role[0];score=fillers.astype(np.int32)@q.astype(np.int32);true=score[idx[0]];other=np.delete(score,idx[0]);maxother=other.max();success+=int(true>maxother);tie+=int(true==maxother);signal.append(float(true/d));maxnoise.append(float(maxother/d));gaps.append(float((true-maxother)/d));miss+=int(true/d<th)
        unknown=(2*r.integers(0,2,d,dtype=np.int8)-1).astype(np.int32);false_accept+=int((fillers.astype(np.int32)@unknown).max()/d>=th)
    return dict(d=d,k=k,codebook=n,trials=trials,exact_top1=success/trials,tie_rate=tie/trials,mean_signal=float(np.mean(signal)),theory_signal=expected_signal(k),mean_max_distractor=float(np.mean(maxnoise)),mean_gap=float(np.mean(gaps)),independent_threshold=th,target_below_threshold=miss/trials,unknown_false_accept=false_accept/trials)
