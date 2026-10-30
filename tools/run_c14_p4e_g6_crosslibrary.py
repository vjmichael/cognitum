"""G6 *development-only* uploaded-source DoWhy numerical comparison.

Not a production capability. This deliberately does not alter or bypass the
production DoWhy 0.14 version gate or Lu host authorization requirements.
For a user-provided DoWhy main snapshot with __version__=0.0.0, verify genuine
API behavior and cross-check with P2A and optionally EconML on the same data.

Usage: python tools/run_c14_p4e_g6_crosslibrary.py \
    --source-root /path/to/dowhy-main --python /path/to/env/bin/python \
    --report /path/to/evidence.json
"""
from __future__ import annotations
import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time

MAX_REPLY = 16384
MAX_FRAME = 131072
SOURCE_BACKEND = 'dowhy-uploaded-source-research-only'
SOURCE_ASSURANCE = 'NUMERIC_COMPARISON_NOT_CAUSAL_PROOF'
SOURCE_VERSION = '0.0.0'  # exact placeholder in user-supplied main snapshot


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_development_receipt(raw, reply):
    """Independent request binding and numerical match; NOT a release receipt."""
    from cognitum import causal_dowhy_backend as b, causal_estimation as ref
    from cognitum.proto import causal_dowhy_pb2 as d
    try:
        request, model, total, buckets = b._parse(raw)
        out = ref._decode(reply, d.DoWhyResult)
        expected = b._preflight(request, model, total, buckets)
        if (out.schema_version != 1 or out.request_sha256 != hashlib.sha256(raw).digest()
            or out.trace_id != request.estimation.trace_id or out.backend_id != SOURCE_BACKEND
            or out.backend_version != SOURCE_VERSION or out.status != d.DOWHY_EFFECT_ESTIMATED
            or out.reason_code != 'SOURCE_SNAPSHOT_NOT_RELEASE_ATTESTED'
            or out.assurance != SOURCE_ASSURANCE
            or out.total_observations != total or not out.numeric_crosschecked
            or out.method != request.method or out.refutation != request.refutation):
            return False
        actual = Fraction(out.estimated_ate)
        reference = Fraction(out.exact_standardized_reference_ate)
        error = Fraction(out.absolute_reference_difference)
        if (reference != expected or abs(float(actual-expected)) > b.COMPARISON_TOLERANCE
            or abs(float(error - abs(actual - expected))) > 1e-8):
            return False
        if request.refutation == d.DOWHY_PLACEBO_PERMUTATION:
            if (not out.refutation_executed or out.refutation_reason_code != 'PLACEBO_DIAGNOSTIC_ONLY'
                or not math.isfinite(float(out.refutation_estimated_effect))):
                return False
        elif out.refutation_executed:
            return False
        return True
    except Exception:
        return False


def child(source_root):
    """Execute actual user-supplied DoWhy Python source in -I isolated interpreter.

    WARNING: -I is Python import isolation, not OS-level sandboxing. This tool
    is for explicit offline scientific tests with a trusted researcher only.
    """
    source = Path(source_root).resolve(strict=True)
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(source))
    sys.path.insert(0, str(root))
    from cognitum import causal_dowhy_backend as b
    from cognitum.proto import causal_dowhy_pb2 as d
    import numpy as np
    import pandas as pd
    import networkx as nx
    import dowhy
    if dowhy.__version__ != SOURCE_VERSION:
        raise ValueError('UPLOADED_SOURCE_PLACEHOLDER_MISMATCH')
    from dowhy import CausalModel
    raw = sys.stdin.buffer.read(MAX_FRAME + 1)
    if len(raw) > MAX_FRAME:
        raise ValueError('REQUEST_FRAME_TOO_LARGE')
    req, model, total, buckets = b._parse(raw)
    expected = b._preflight(req, model, total, buckets)
    if req.method != d.DOWHY_BACKDOOR_LINEAR_REGRESSION:
        raise ValueError('METHOD_UNSUPPORTED')
    nodes = list(req.estimation.identification.model.endogenous)
    noise = list(req.estimation.identification.model.exogenous)
    g = nx.DiGraph()
    for i in range(len(nodes)):
        g.add_node(f'v{i}', observed='yes')
    for j in range(len(noise)):
        g.add_node(f'u{j}', observed='no')
    for i, node in enumerate(nodes):
        for p in node.parents:
            g.add_edge(f'v{p}',f'v{i}')
        for u in node.noise:
            g.add_edge(f'u{u}',f'v{i}')
    rows=[]
    for row in req.estimation.observations:
        rows.extend([list(row.states)] * row.count)
    df=pd.DataFrame(rows,columns=[f'v{i}' for i in range(len(nodes))],dtype=int)
    base=req.estimation.identification
    m=CausalModel(data=df,treatment=f'v{base.treatment}',outcome=f'v{base.target}',
                  graph='\n'.join(nx.generate_gml(g)), proceed_when_unidentifiable=False)
    identified=m.identify_effect(proceed_when_unidentifiable=False)
    chosen=set(identified.get_backdoor_variables() or [])
    supplied={f'v{i}' for i in base.adjustment}
    if chosen != supplied:
        raise ValueError('IDENTIFICATION_ADJUSTMENT_DISAGREEMENT')
    estimate=m.estimate_effect(identified,method_name='backdoor.linear_regression',
             control_value=0,treatment_value=1,target_units='ate',
             test_significance=False,confidence_intervals=False)
    value=float(estimate.value)
    if not math.isfinite(value) or abs(value-float(expected))>b.COMPARISON_TOLERANCE:
        raise ValueError('REFERENCE_NUMERIC_DISAGREEMENT')
    result=d.DoWhyResult(schema_version=1,request_sha256=hashlib.sha256(raw).digest(),
             trace_id=req.estimation.trace_id, backend_id=SOURCE_BACKEND,
             backend_version=SOURCE_VERSION, status=d.DOWHY_EFFECT_ESTIMATED,
             reason_code='SOURCE_SNAPSHOT_NOT_RELEASE_ATTESTED',
             method=req.method,refutation=req.refutation,graph_criterion_checked=True,
             numeric_crosschecked=True, estimated_ate=format(value,'.12g'),
             exact_standardized_reference_ate=str(expected),
             absolute_reference_difference=format(abs(value-float(expected)),'.12g'),
             total_observations=total,assurance=SOURCE_ASSURANCE)
    if req.refutation == d.DOWHY_PLACEBO_PERMUTATION:
        placebo=m.refute_estimate(identified,estimate,method_name='placebo_treatment_refuter',
            placebo_type='permute',random_state=int(req.random_seed%(2**32)),num_simulations=10)
        value=float(placebo.new_effect)
        if not math.isfinite(value):
            raise ValueError('NONFINITE_PLACEBO')
        result.refutation_executed=True
        result.refutation_estimated_effect=format(value,'.12g')
        result.refutation_reason_code='PLACEBO_DIAGNOSTIC_ONLY'
    sys.stdout.buffer.write(result.SerializeToString(deterministic=True))


def compare(source_root,python,*,refutation=True,include_econml=True):
    """Explicit developer-run comparison. No model-selected paths or host action."""
    from tests.test_c14_dowhy_adapter import make_request
    from cognitum import causal_dowhy_backend as b, causal_estimation as ref
    from cognitum.proto import causal_dowhy_pb2 as d
    req=make_request(homogenous=True,refutation=refutation)
    raw=req.SerializeToString(deterministic=True)
    _, model,total,buckets=b._parse(raw)
    expected=b._preflight(req,model,total,buckets)
    here=Path(__file__).resolve()
    src=Path(source_root).resolve(strict=True)
    worker_src=src / 'dowhy' / '__init__.py'
    if not worker_src.is_file() or SOURCE_VERSION not in worker_src.read_text():
        raise ValueError('SOURCE_NOT_EXPECTED_SNAPSHOT')
    start=time.monotonic()
    result=subprocess.run([str(Path(python).absolute()),'-I',str(here),'--child',
                           '--source-root',str(src)],input=raw,
                           stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30,check=True)
    if len(result.stdout)>MAX_REPLY:
        raise ValueError('OVERSIZE_CHILD_RESULT')
    verified=verify_development_receipt(raw,result.stdout)
    if not verified:
        raise AssertionError('DEVELOPMENT_RECEIPT_INVALID')
    parsed=d.DoWhyResult.FromString(result.stdout)
    # Production receipt must reject untagged development evidence.
    assert not b.verify_dowhy_receipt(raw,result.stdout).numeric_verified
    payload={
        'source_zip_version_certified':False,
        'source_version_declared':SOURCE_VERSION,
        'backend':'DoWhy uploaded main snapshot (UNVERIFIED tag)',
        'backend_source_init_sha256':digest(worker_src),
        'request_sha256':hashlib.sha256(raw).hexdigest(),
        'request_count':total,
        'reference_exact_ate':str(expected),
        'dowhy_ate':float(parsed.estimated_ate),
        'dowhy_placebo_effect':float(parsed.refutation_estimated_effect) if refutation else None,
        'dowhy_dev_receipt_verified':verified,
        'production_v014_receipt_verified':False,
        'elapsed_s_dowhy_subprocess':round(time.monotonic()-start,5),
        'model_assumptions_empirically_proven':False,
    }
    if include_econml:
        # Same data and estimand, not identical finite-sample estimator.
        import numpy as np
        from econml.dml import LinearDML
        from sklearn.linear_model import LinearRegression,LogisticRegression
        rows=[]
        for row in req.estimation.observations:
            rows.extend([list(row.states)] * row.count)
        data=np.asarray(rows,dtype=float)
        z=data[:,0].reshape(-1,1)
        estimator=LinearDML(model_y=LinearRegression(),model_t=LogisticRegression(max_iter=1000),
                            discrete_treatment=True,random_state=42,cv=3)
        estimator.fit(data[:,2],data[:,1],X=z)
        effects=[float(x) for x in estimator.effect(np.asarray([[0.],[1.]]))]
        econml_ate=float(np.mean(estimator.effect(z)))
        if any(not math.isfinite(x) for x in (*effects,econml_ate)):
            raise ValueError('NONFINITE_ECONML')
        payload.update(econml_linear_dml_conditional_effects=effects,
                       econml_mean_effect=econml_ate,
                       dowhy_econml_absolute_difference=abs(payload['dowhy_ate']-econml_ate),
                       methods_equal_by_construction=False)
    return payload


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--child',action='store_true',help='development-only subprocess')
    parser.add_argument('--source-root',required=True)
    parser.add_argument('--python',default=sys.executable)
    parser.add_argument('--report',type=Path)
    parser.add_argument('--no-econml',action='store_true')
    args=parser.parse_args()
    if args.child:
        child(args.source_root)
        return
    result=compare(args.source_root,args.python,include_econml=not args.no_econml)
    out=json.dumps(result,indent=2,sort_keys=True)+'\n'
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(out)
    print(out)


if __name__=='__main__':
    main()
