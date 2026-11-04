"""C19 real-library point-cloud shape baseline vs persistent H1.

Synthetic circle vs filled disk is a diagnostic task, not an empirical
application or claim that TDA improves arbitrary geometry/embeddings.
Strict holdout: fit only on earlier generated shapes, later seeds are held out.
"""
from dataclasses import dataclass,asdict
from hashlib import sha256
from math import pi,sin,cos,sqrt
from time import perf_counter

from .topology_rips import TopologyQuery,compute,snapshot_hash

@dataclass(frozen=True)
class ShapeMetric:
    model:str
    train_accuracy:float
    holdout_accuracy:float
    heldout_count:int
    runtime_ms:float

@dataclass(frozen=True)
class ShapeBenchmark:
    status:str
    counts:tuple[int,int]
    results:tuple[ShapeMetric,...]
    feature_reference:str
    limitations:tuple[str,...]=(
        "synthetic_circles_vs_disks_not_real_domain_generalization",
        "geometry_and_spectral_incumbents_must_be_compared",
        "seed_holdout_is_not_independent_external_source",
        "no_Lu_transformer_A_B_or_real_user_task_acceptance",
    )

def fixture(label,seed,n=24):
    import numpy as np
    rng=np.random.default_rng(seed)
    angle=rng.uniform(0,2*pi,n)
    radial=rng.uniform(.05,1.,n)**.5 if label==0 else np.ones(n)
    noise=rng.normal(0,.015,n)
    points=tuple((float((r+e)*cos(a)),float((r+e)*sin(a)))
                 for r,a,e in zip(radial,angle,noise))
    return points

def features(points):
    import numpy as np
    from scipy.spatial.distance import pdist,squareform
    X=np.asarray(points,dtype=float)
    center=X.mean(axis=0)
    centered=X-center
    r=np.sqrt(np.sum(centered**2,axis=1))
    # Competent geometry: radial dispersion, covariance eccentricity, mean NN.
    cov=np.cov(centered.T)
    eigen=np.linalg.eigvalsh(cov)
    dist=squareform(pdist(X))
    np.fill_diagonal(dist,float("inf"))
    nearest=float(np.mean(np.min(dist,axis=1)))
    geometric=(float(np.std(r)),float(np.mean(r)),nearest,
               float(eigen[0]/max(eigen[-1],1e-9)))
    # Spectral incumbent: smallest normalized graph Laplacian eigenvalues
    # using a fixed distance-scale Gaussian kernel, not GT labels.
    ds=pdist(X)
    bandwidth=max(float(np.median(ds)),1e-6)
    sq=squareform(ds)
    W=np.exp(-(sq/bandwidth)**2)
    np.fill_diagonal(W,0)
    degrees=np.sum(W,axis=1)
    lap=np.eye(len(points))-W/np.sqrt(np.outer(degrees,degrees))
    spectral=tuple(float(x) for x in np.linalg.eigvalsh(lap)[1:4])
    q=TopologyQuery("synthetic_fixture",snapshot_hash(points),"unitless",
                    "euclidean","vietoris_rips",2.,1,points)
    out=compute(q)
    if out.status!="OK":raise RuntimeError("real Ripser backend absent")
    h1=sorted((x.death-x.birth for x in out.intervals
               if x.dimension==1 and x.death is not None),reverse=True)
    topology=(float(h1[0]) if h1 else 0.,
              float(sum(h1[:3])),
              float(len(h1)))
    return geometric,spectral,topology

def benchmark(ntrain=24,ntest=12):
    if not 12<=ntrain<=40 or not 8<=ntest<=24:
        raise ValueError("bounded benchmark sizes")
    import numpy as np
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression
    sets={"geometry":[],"geometry_spectral":[],"geometry_topology":[],
          "geometry_spectral_topology":[]}
    labels=[]
    start=perf_counter()
    for i in range(ntrain+ntest):
        label=i%2
        x=fixture(label,10000+i)
        geometry,spectral,topology=features(x)
        values={
            "geometry":geometry,
            "geometry_spectral":geometry+spectral,
            "geometry_topology":geometry+topology,
            "geometry_spectral_topology":geometry+spectral+topology,
        }
        for name,value in values.items():sets[name].append(value)
        labels.append(label)
    results=[]
    Y=np.asarray(labels)
    for name,X in sets.items():
        start_fit=perf_counter()
        A=np.asarray(X)
        clf=make_pipeline(StandardScaler(),
            LogisticRegression(C=1.,max_iter=500,random_state=0))
        clf.fit(A[:ntrain],Y[:ntrain])
        results.append(ShapeMetric(name,
            float(clf.score(A[:ntrain],Y[:ntrain])),
            float(clf.score(A[ntrain:],Y[ntrain:])),
            ntest,round((perf_counter()-start_fit)*1000,3)))
    return ShapeBenchmark("MEASURED_SYNTHETIC_ONLY",(ntrain,ntest),
        tuple(results),"Ripser H1 + SciPy Euclidean geometry/spectrum")
