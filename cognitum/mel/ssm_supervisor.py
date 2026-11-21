"""Bounded, nonprivileged SSM math execution using existing Cognitum worker.

The existing cognitum.worker.execute uses a spawned disposable process with a
timeout and termination. It is genuine subprocess supervision, NOT a native
OS sandbox, AppContainer/Job custody, Linux cgroup custody, installed MEL
registry route or a Lu-authorized model tool. A trusted host must own all of
those external steps. The child gets only unkeyed R5/R6 numeric state and an
input; never HMAC keys, journal paths, grants, database handles or OS tokens.
Authenticated checkpoint sealing and all SQLite effects remain in host.
"""
from __future__ import annotations

import json
import math
import numpy as np

from cognitum import worker
from cognitum.research import ssm_stochastic_checkpoints as cp
from cognitum.research import ssm_stochastic_streaming as ssm

OP="ssm.fixed_duration.advance.research"
MAX_WIRE=cp.MAX_CHECKPOINT_BYTES
MAX_OUTPUT=cp.MAX_CHECKPOINT_BYTES
RELEASE_FIELDS=frozenset(("state_index","state_time",
    "observation_cutoff_time","conditioned_through_time","release_time",
    "mean","factor","covariance"))
INPUT_FIELDS=frozenset(("state","kind","end_time","increment"))


def _need(test,why):
    if not test:raise ValueError("SSM supervised math refused: "+why)


class SSMComputeFactory:
    """Trusted pure math factory. No external effects or key material."""

    def handle(self,operation,payload):
        _need(operation==OP and type(payload) is dict
              and set(payload)==INPUT_FIELDS,"closed pure math operation")
        serialized=json.dumps(payload,allow_nan=False,separators=(",",":"))
        _need(len(serialized)<=MAX_WIRE,"bounded input")
        state=cp._decode_state(payload["state"])
        kind=payload["kind"]
        t=payload["end_time"]
        _need(type(t) in (int,float) and math.isfinite(t),"finite timestamp")
        observation=payload["increment"]
        if kind=="increment":
            released=state.push(float(t),observation)
        elif kind=="watermark":
            _need(observation is None,"watermark has no observation")
            released=state.advance_watermark(float(t))
        else:
            raise ValueError("invalid SSM pure math operation")
        outputs=[{k:(v.tolist() if isinstance(v,np.ndarray) else v)
                  for k,v in x.items() if k in RELEASE_FIELDS}
                 for x in released]
        response={"state":cp._encode_state(state),"releases":outputs}
        raw=json.dumps(response,allow_nan=False,separators=(",",":"))
        _need(len(raw)<=MAX_OUTPUT,"bounded worker output")
        return response


class SupervisedSSMCompute:
    """Use existing bounded disposable subprocess; verify return before commit."""

    def __init__(self,*,timeout_ms=8000,protected_executor=None):
        _need(type(timeout_ms) is int and 100<=timeout_ms<=10000,
              "supervisor timeout budget")
        if protected_executor is not None:
            from .ssm_r4_protected import ProtectedFixedSSMExecutor
            _need(type(protected_executor) is ProtectedFixedSSMExecutor,
                  "reviewed original-operation-bound native executor only")
        self.timeout_ms=timeout_ms
        self._protected_executor=protected_executor

    def apply(self,engine,kind,end_time,increment,*,
              scope=None,stream_id=None,event_id=None):
        _need(type(engine) is ssm.FixedDurationIncrementSmoother,
              "trusted R5 engine required")
        # Do not give the child a signed checkpoint, authorization token or key.
        original=cp._encode_state(engine)
        payload={"state":original,"kind":kind,
                 "end_time":end_time,"increment":increment}
        _need(len(json.dumps(payload,allow_nan=False))<=MAX_WIRE,
              "bounded worker request")
        if self._protected_executor is None:
            status,reply=worker.execute(SSMComputeFactory,OP,payload,self.timeout_ms)
        else:
            status,reply=self._protected_executor.execute(
                SSMComputeFactory,OP,payload,self.timeout_ms,
                scope=scope,stream_id=stream_id,event_id=event_id)
        _need(status=="ok" and type(reply) is dict
              and set(reply)=={"state","releases"},
              "child failed, timed out or malformed response: "+str(status))
        result=cp._decode_state(reply["state"])
        _need(type(reply["releases"]) is list and
              len(reply["releases"])<=ssm.MAX_PENDING,
              "bounded worker output list")
        _need(np.array_equal(result._generator,engine._generator) and
              np.array_equal(result._rate,engine._rate) and
              result.duration==engine.duration and
              result.max_pending_states==engine.max_pending_states,
              "worker model authorization pin mismatch")
        if kind=="increment":
            _need(result._index==engine._index+1 and
                  result._count==engine._count+1 and
                  result._time==end_time and
                  result._watermark==end_time,
                  "worker input-to-filter progress mismatch")
        else:
            _need(kind=="watermark" and result._index==engine._index and
                  result._time==engine._time and
                  result._watermark==end_time,
                  "worker watermark progress mismatch")
        # Released output belongs to the original pending prefix and must
        # agree with the returned filter's advanced release-counter.
        expected=result._released-engine._released
        _need(expected==len(reply["releases"]) and expected>=0,
              "worker exact released-count mismatch")
        releases=[]
        for j,entry in enumerate(reply["releases"]):
            _need(type(entry) is dict and set(entry)==RELEASE_FIELDS,
                  "closed bounded release receipt")
            index=entry["state_index"]
            _need(type(index) is int and
                  index==engine._released+j and index<result._released,
                  "strict release order")
            t0=entry["state_time"]
            cutoff=entry["observation_cutoff_time"]
            through=entry["conditioned_through_time"]
            release=entry["release_time"]
            _need(all(type(x) in (int,float) and math.isfinite(x)
                      for x in (t0,cutoff,through,release)) and
                  cutoff==t0+engine.duration and
                  t0<=through<=cutoff<=release and
                  through<=result._time,
                  "bounded causal release times")
            n=engine._n
            mean=cp._vector(entry["mean"],n,"released state mean")
            root=cp._matrix(entry["factor"],(n,n),"released QR factor")
            covariance=cp._matrix(entry["covariance"],(n,n),
                                  "released covariance")
            _need(np.allclose(root@root.T,covariance,atol=1e-9,rtol=1e-8),
                  "released covariance must match QR factor")
            releases.append({"state_index":index,"state_time":t0,
                 "observation_cutoff_time":cutoff,
                 "conditioned_through_time":through,"release_time":release,
                 "mean":mean,"factor":root,"covariance":covariance})
        # The trusted host signs a new R6 checkpoint only after all checks.
        return result,tuple(releases)
