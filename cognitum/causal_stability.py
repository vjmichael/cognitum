"""C14 P3E: deterministic bounded resampling stability of *undirected* PC skeletons.

Resample edge frequency is NOT P(edge causal), posterior probability, or a
confidence interval. The permuted-null mode is a statistical negative control,
not a guarantee of no associations in finite samples.
"""
from __future__ import annotations
import hashlib
import math
import struct
import time
from cognitum.causal_discovery import _parse as parse_discovery, run_discovery_frame
from cognitum.causal_estimation import _decode
from cognitum.proto import causal_discovery_pb2 as d, causal_stability_pb2 as s

FRAME_MAX = 180000
LIMITS = ('OBSERVATIONAL_UNDIRECTED_SKELETON_ONLY;SELECTION_FREQUENCY_NOT_POSTERIOR;'
          'GAUSSIAN_CI_MARKOV_FAITHFULNESS_NOT_VERIFIED;NULL_SHUFFLE_NOT_CAUSAL_TEST;'
          'SAME_NUMERICAL_RUNTIME_REQUIRED_FOR_BITWISE_REPLAY')


def _parse(raw):
    if not isinstance(raw, bytes) or not raw or len(raw) > FRAME_MAX:
        raise ValueError('INVALID_STABILITY_FRAME')
    req = _decode(raw, s.StabilityRequest)
    if (req.schema_version != 1 or not req.trace_id or not req.HasField('source_request') or
        req.trace_id != req.source_request.trace_id or
        req.source_request.method != d.REFERENCE_PC_STABLE_SKELETON or
        req.mode not in (s.SUBSAMPLE_WITHOUT_REPLACEMENT,s.BOOTSTRAP_WITH_REPLACEMENT,
                         s.SUBSAMPLE_PERMUTED_NULL) or
        not 2 <= req.repetitions <= 16 or
        not 60 <= req.rows_per_replicate <= len(req.source_request.observations) or
        not 1 <= req.total_test_budget <= 4000 or
        not 1 <= req.total_timeout_ms <= 30000):
        raise ValueError('INVALID_STABILITY_REQUEST')
    parse_discovery(req.source_request.SerializeToString(deterministic=True))
    if req.mode == s.SUBSAMPLE_PERMUTED_NULL:
        if req.permuted_variable >= len(req.source_request.variable_ids):
            raise ValueError('INVALID_PERMUTATION_COLUMN')
    elif req.permuted_variable:
        raise ValueError('PERMUTATION_COLUMN_ONLY_FOR_NULL')
    # Validate cost *before* running: a single request cannot ask for work beyond
    # the admission budget. Runtime may consume less because of early CI stops.
    if req.repetitions > req.total_test_budget:
        raise ValueError('INSUFFICIENT_TOTAL_TEST_BUDGET')
    return req


def _compute(req, raw, *, clock=time.monotonic):
    import numpy as np
    from numpy.random import Generator, PCG64
    seed = int(req.fixed_seed)
    rng = Generator(PCG64(seed))
    base = req.source_request
    source = [list(row.values) for row in base.observations]
    nrows, nvars = len(source), len(base.variable_ids)
    start = clock()
    counts = {(a,b):0 for a in range(nvars) for b in range(a+1,nvars)}
    out = s.StabilityResult(schema_version=1,request_sha256=hashlib.sha256(raw).digest(),
        trace_id=req.trace_id,mode=req.mode,status=s.STABILITY_INCONCLUSIVE,
        reason_code='NOT_COMPUTED',assumptions_and_limits=LIMITS)
    total = 0
    for ordinal in range(req.repetitions):
        remaining_ms = int((req.total_timeout_ms / 1000 - (clock()-start)) * 1000)
        if remaining_ms <= 0 or total >= req.total_test_budget:
            out.status = s.STABILITY_RESOURCE_LIMIT
            out.reason_code = 'TOTAL_RESOURCE_LIMIT'
            return out  # NO partial graphs or resamples published
        # Full-array draw order is intentional: it binds reproducibility to PCG64
        # and this NumPy implementation, both named in the dossier.
        indices = rng.choice(nrows, size=req.rows_per_replicate,
                             replace=req.mode==s.BOOTSTRAP_WITH_REPLACEMENT).tolist()
        rows = [source[i][:] for i in indices]
        if req.mode == s.SUBSAMPLE_PERMUTED_NULL:
            col = req.permuted_variable
            shuffled = rng.permutation(req.rows_per_replicate)
            prior = [row[col] for row in rows]
            for pos, j in enumerate(shuffled):
                rows[pos][col] = prior[int(j)]
        child = d.DiscoveryRequest()
        child.CopyFrom(base)
        del child.observations[:]
        for row in rows:
            child.observations.add(values=row)
        child.max_tests = min(base.max_tests, req.total_test_budget-total)
        child.timeout_ms = min(base.timeout_ms, req.total_timeout_ms)  # replay-stable; outer deadline separate
        child_raw = child.SerializeToString(deterministic=True)
        reply = run_discovery_frame(child_raw,host_authorized=True,enabled=True)
        got = _decode(reply,d.DiscoveryResult)
        if got.status != d.CANDIDATE_SKELETON_COMPUTED:
            # The reference might run out of tests, time out, or hit degenerate
            # covariance after a resampling. Such an attempt is inconclusive.
            out.status = (s.STABILITY_RESOURCE_LIMIT if got.status == d.DISCOVERY_RESOURCE_LIMIT
                          else s.STABILITY_BACKEND_UNAVAILABLE if got.status == d.DISCOVERY_BACKEND_UNAVAILABLE
                          else s.STABILITY_INCONCLUSIVE)
            out.reason_code = 'REPLICATE_' + (got.reason_code if len(got.reason_code)<64 else 'FAILED')
            return out
        if (clock()-start)*1000 > req.total_timeout_ms:
            out.status=s.STABILITY_RESOURCE_LIMIT
            out.reason_code='TOTAL_RESOURCE_LIMIT'
            return out
        total += got.tests_executed
        for e in got.undirected_edges:
            counts[(e.first,e.second)]+=1
        dig = hashlib.sha256(b''.join(struct.pack('>I',i) for i in indices)).digest()
        got.wall_ns=0  # timing is not a deterministic replay input
        stable_reply=got.SerializeToString(deterministic=True)
        out.replicates.add(ordinal=ordinal,draw_indices_sha256=dig,
            reference_request_sha256=hashlib.sha256(child_raw).digest(),
            result_sha256=hashlib.sha256(stable_reply).digest(),tests_executed=got.tests_executed)
    out.completed_repetitions=req.repetitions
    out.total_tests=total
    for (a,b), count in sorted(counts.items()):
        out.edges.add(first=a,second=b,selection_count=count,
                      selection_fraction=format(count/req.repetitions,'.12g'))
    out.status=s.STABILITY_COMPUTED
    out.reason_code='DESCRIPTIVE_REPLICATE_EDGE_FREQUENCIES_ONLY'
    return out


def run_stability_frame(raw, *, host_authorized=False, enabled=False):
    start=time.monotonic_ns()
    out=s.StabilityResult(schema_version=1,
        request_sha256=hashlib.sha256(raw if isinstance(raw,bytes) else b'').digest(),
        status=s.STABILITY_REJECTED,reason_code='INVALID_STABILITY_FRAME',
        assumptions_and_limits=LIMITS)
    try:
        req=_parse(raw)
        out.trace_id=req.trace_id
        if not host_authorized: raise ValueError('HOST_AUTHORIZATION_REQUIRED')
        if not enabled: raise ValueError('STABILITY_DISABLED')
        out=_compute(req,raw)
    except (ValueError,TypeError) as exc:
        reason=str(exc)
        out.reason_code=reason if reason.isupper() and len(reason)<100 else 'INVALID_STABILITY_REQUEST'
    except (ImportError,ModuleNotFoundError):
        out.status=s.STABILITY_BACKEND_UNAVAILABLE
        out.reason_code='NUMPY_RUNTIME_UNAVAILABLE'
    except Exception:
        out.status=s.STABILITY_INCONCLUSIVE
        out.reason_code='STABILITY_RUNTIME_FAILURE'
    if out.status!=s.STABILITY_COMPUTED:
        del out.edges[:]
        del out.replicates[:]
        out.completed_repetitions=0
        out.total_tests=0
    out.wall_ns=time.monotonic_ns()-start
    return out.SerializeToString(deterministic=True)


def stability_receipt(raw,reply):
    receipt=s.StabilityReceipt(
        request_sha256=hashlib.sha256(raw if isinstance(raw,bytes) else b'').digest(),
        result_sha256=hashlib.sha256(reply if isinstance(reply,bytes) else b'').digest(),
        reason_code='NOT_VERIFIED')
    try:
        req=_parse(raw)
        got=_decode(reply,s.StabilityResult)
        if got.status!=s.STABILITY_COMPUTED or got.request_sha256!=receipt.request_sha256:
            return receipt
        expected=_compute(req,raw)
        if expected.status!=s.STABILITY_COMPUTED:
            return receipt
        expected.wall_ns=got.wall_ns
        if expected.SerializeToString(deterministic=True)==got.SerializeToString(deterministic=True):
            receipt.exact_resampling_replay=True
            receipt.reason_code='SAME_RUNTIME_STATISTICAL_REPLAY_ONLY'
    except Exception:
        pass
    return receipt
