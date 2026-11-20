"""Bounded reproducible scientific datasets, frozen protocols, and CPU accounting.

No file system or network I/O. Caller supplies bytes and retains those bytes.
Licensing is a declared assertion, NOT verified by the parser.
"""
import csv
import io
import json
import gc
import platform
import sys
import time
import tracemalloc
import hashlib
import numpy as np
from .ssm_stochastic import need, array, receipt
from .ssm_interop import wire, read, digest, hashid, ident, load_model, load_state, advance


def parse_data(raw):
    """Strict UTF-8 CSV: time_seconds, observation, control; bounded and finite."""
    need(type(raw) is bytes and 0 < len(raw) <= 1_000_000, 'CSV budget')
    try:
        txt=raw.decode('utf-8', 'strict')
        need(not txt.startswith('\ufeff') and '\x00' not in txt, 'noncanonical CSV')
        rows=list(csv.reader(io.StringIO(txt, newline=''), strict=True))
        need(rows[0] == ['time_seconds','observation','control'] and 65 <= len(rows) <= 4097, 'CSV schema/count')
        need(all(len(row)==3 and all(v.strip()==v and v and len(v)<=36 for v in row) for row in rows[1:]), 'CSV cell schema')
        X=np.array([[float(v) for v in row] for row in rows[1:]], dtype=float)
    except (ValueError, OverflowError, UnicodeError, csv.Error, IndexError) as exc:
        raise ValueError('invalid scientific CSV') from exc
    need(np.isfinite(X).all() and np.max(abs(X))<=1e8, 'nonfinite/range')
    t=X[:,0];dt=np.diff(t)
    need(t[0]>=0 and np.all((dt>=1e-4)&(dt<=10)) and t[-1]<=1e8, 'time order/budget')
    return X


def manifest(raw, *, source, declared_license, time_unit, observation_unit, control_unit, origin):
    x=parse_data(raw)
    need(source in ('synthetic','declared-external') and type(declared_license) is str and 1<=len(declared_license)<=64, 'source/license')
    for v in (declared_license,time_unit,observation_unit,control_unit,origin):ident(v)
    need(time_unit=='s', 'time unit must be seconds')
    return wire(dict(version=1, kind='scientific-dataset', sha256=digest(raw), count=len(x), first_time=float(x[0,0]), last_time=float(x[-1,0]), source=source, declared_license=declared_license, declared_origin=origin, license_verified=False, time_unit=time_unit, observation_unit=observation_unit, control_unit=control_unit, raw_bytes_required=True))


def validate_data(raw, manifest_raw):
    m=read(manifest_raw)
    need(set(m)=={'version','kind','sha256','count','first_time','last_time','source','declared_license','declared_origin','license_verified','time_unit','observation_unit','control_unit','raw_bytes_required'} and m['version']==1 and m['kind']=='scientific-dataset' and m['license_verified'] is False and m['raw_bytes_required'] is True, 'dataset manifest schema')
    x=parse_data(raw)
    need(m['sha256']==digest(raw) and m['count']==len(x) and m['first_time']==float(x[0,0]) and m['last_time']==float(x[-1,0]), 'dataset tamper')
    need(manifest(raw,source=m['source'],declared_license=m['declared_license'],time_unit=m['time_unit'],observation_unit=m['observation_unit'],control_unit=m['control_unit'],origin=m['declared_origin'])==manifest_raw, 'manifest canonical')
    return x


def protocol(manifest_raw, *, train_end, val_end, seed, ridge_candidates=(0.,.01,1.), improvement_ratio=.98):
    m=read(manifest_raw)
    need(m.get('kind')=='scientific-dataset' and m.get('version')==1 and type(train_end) is int and type(val_end) is int and 33<=train_end and train_end+16<=val_end and val_end+16<=m['count'], 'chronological split')
    need(type(seed) is int and 0<=seed<2**32 and type(ridge_candidates) in (list,tuple) and 1<=len(ridge_candidates)<=8 and all(type(v) in (float,int) and np.isfinite(v) and 0<=v<=100 for v in ridge_candidates), 'frozen settings')
    need(type(improvement_ratio) in (int,float) and .1<=improvement_ratio<=1., 'threshold')
    need(len(set(ridge_candidates))==len(ridge_candidates), 'duplicate parameters')
    return wire(dict(version=1,kind='frozen-experiment',dataset_manifest_sha256=digest(manifest_raw),source_sha256=m['sha256'],train_end=train_end,val_end=val_end,seed=seed,metric='one-step-rmse',ridge_candidates=[float(v) for v in ridge_candidates],improvement_ratio=float(improvement_ratio),test_selection_forbidden=True))


def evaluate(raw,manifest_raw,protocol_raw, *, expected_protocol_sha256):
    need(hashid(expected_protocol_sha256)==digest(protocol_raw), 'protocol pin mismatch')
    x=validate_data(raw,manifest_raw);p=read(protocol_raw)
    need(set(p)=={'version','kind','dataset_manifest_sha256','source_sha256','train_end','val_end','seed','metric','ridge_candidates','improvement_ratio','test_selection_forbidden'} and p['version']==1 and p['kind']=='frozen-experiment' and p['dataset_manifest_sha256']==digest(manifest_raw) and p['source_sha256']==digest(raw) and p['test_selection_forbidden'] is True, 'frozen protocol mismatch')
    need(protocol(manifest_raw,train_end=p['train_end'],val_end=p['val_end'],seed=p['seed'],ridge_candidates=p['ridge_candidates'],improvement_ratio=p['improvement_ratio'])==protocol_raw, 'protocol canonical')
    n=len(x);a,b=p['train_end'],p['val_end']
    # Forecast target is strictly the *next* observation. No boundary target crosses splits.
    D=np.column_stack((np.ones(n-1),x[:-1,1],x[:-1,2]));y=x[1:,1]
    train=(D[:a-1],y[:a-1]);val=(D[a:b-1],y[a:b-1]);test=(D[b:n-1],y[b:n-1]);need(all(len(z[0])>=15 for z in (train,val,test)),'split bounds')
    z=[]
    for lam in p['ridge_candidates']:
        X,v=train;H=X.T@X+lam*np.diag([0,1,1]);s=np.linalg.svd(H,compute_uv=False)
        need(s[-1]>1e-12*s[0], 'rank-deficient identification')
        beta=np.linalg.solve(H,X.T@v)
        val_loss=float(np.mean((val[0]@beta-val[1])**2));z.append((val_loss,lam,beta))
    _,lam,beta=min(z,key=lambda e:(e[0],e[1]));T,truth=test;forecast=T@beta
    rmse=float(np.sqrt(np.mean((forecast-truth)**2)));base=float(np.sqrt(np.mean((T[:,1]-truth)**2)))
    return receipt(dataset_sha256=digest(raw),manifest_sha256=digest(manifest_raw),protocol_sha256=digest(protocol_raw),coefficients=beta,selected_ridge=lam,validation_rmse=float(np.sqrt(min(z,key=lambda e:(e[0],e[1]))[0])),test_rmse=rmse,persistence_rmse=base,relative_improvement=float(1-rmse/base) if base>0 else None,falsified=bool(rmse>p['improvement_ratio']*base),test_count=len(T),train_count=len(train[0]),val_count=len(val[0]),test_not_used_for_fitting=True,model_selection_validation_only=True)


def machine_profile(model_raw, state_raw, inputs, *, repeats=3, max_wall_ms=10000, max_peak_bytes=8_000_000):
    """Measure actual bounded local recurrence invocations, not a hardware benchmark.
    tracemalloc is Python allocations only; OS/GPU RSS and energy are *not* measured.
    """
    load_model(model_raw);s=load_state(model_raw,state_raw);u=array(inputs,2)
    need(1<=len(u)<=256 and u.shape[1]==len(load_model(model_raw)['input_units']) and type(repeats) is int and 2<=repeats<=10 and type(max_wall_ms) is int and 10<=max_wall_ms<=60000 and type(max_peak_bytes) is int and 100000<=max_peak_bytes<=128_000_000,'resource profile')
    gc.collect();timings=[];cpu=[];peaks=[];ids=[]
    for _ in range(repeats):
        tracemalloc.start();wall=time.perf_counter_ns();proc=time.process_time_ns()
        z=advance(model_raw,state_raw,u,digest(state_raw),s['step'])
        cpu.append((time.process_time_ns()-proc)/1e6);timings.append((time.perf_counter_ns()-wall)/1e6)
        _,peak=tracemalloc.get_traced_memory();tracemalloc.stop();peaks.append(peak);ids.append(digest(z['state']))
    need(len(set(ids))==1, 'nondeterministic replay')
    need(max(timings)<=max_wall_ms and max(peaks)<=max_peak_bytes, 'resource budget exceeded')
    return receipt(first_invocation_ms=timings[0],repeats_ms=timings[1:],cpu_ms=cpu,peak_python_bytes=peaks,source_model_sha256=digest(model_raw),state_sha256=digest(state_raw),output_state_sha256=ids[0],python_version=sys.version.split()[0],platform=platform.platform(),numpy_version=np.__version__,repeats=repeats,measurement_scope='wall+process-CPU+Python-tracemalloc; no RSS/GPU/energy',performance_baseline=False)
