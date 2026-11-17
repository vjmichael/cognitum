"""C13 P2 bounded functional smoke; never a runtime benchmark."""
from pathlib import Path
import importlib.util
from cognitum.proto import probability_backend_pb2 as q
from cognitum.probability_backend import (run_graph_frame, verify_graph_receipt,
                                           make_graph_audit, WorkerPolicy, sha256_file, worker_source)
from tests.test_c13_probability import example

def check(cond, name):
    if not cond: raise AssertionError(name)
    print('PASS:', name)

def ask(kind=q.REFERENCE_EXACT, query=q.GRAPH_JOINT_POSTERIOR, *, enabled=True, authorized=True, worker_policy=None):
    req=q.GraphRequest(schema_version=1,inference=example(),backend=kind,query=query)
    raw=req.SerializeToString(deterministic=True)
    out=run_graph_frame(raw,enabled=enabled,host_authorized=authorized,worker_policy=worker_policy)
    return raw,out,q.GraphResult.FromString(out)

def main():
    raw,out,res=ask()
    check(res.status==q.GRAPH_SUCCESS and verify_graph_receipt(raw,out).exact_reference_certified, 'exact posterior, independent receipt')
    raw,out,res=ask(query=q.GRAPH_MAP)
    check(list(res.map_states)==[0] and res.map_probability=='4/5', 'MAP assignment and rational score')
    raw,out,res=ask(enabled=False)
    check(res.status==q.GRAPH_REJECTED, 'disabled host gate')
    raw,out,res=ask(authorized=False)
    check(res.status==q.GRAPH_REJECTED, 'unauthorized host gate')
    raw,out,res=ask()
    audit=make_graph_audit(raw,out)
    check(audit.exact_reference_certified and audit.result_sha256, 'metadata-only audit and receipt')
    raw,out,res=ask(kind=q.PGMPY_VARIABLE_ELIMINATION)
    check(res.status==q.GRAPH_UNKNOWN and res.reason_code=='PGMPY_WORKER_DISABLED', 'default-off third-party runtime')
    if importlib.util.find_spec('pgmpy') is None:
        print('SKIPPED: installed pgmpy engine execution (package not available)')
    else:
        import sys
        from importlib import metadata
        from cognitum import probability_backend as b
        policy=WorkerPolicy(sys.executable,sha256_file(Path(sys.executable).resolve()),
                            sha256_file(worker_source()),sha256_file(Path(b.__file__).resolve()),
                            metadata.version('pgmpy'),True)
        raw,out,res=ask(kind=q.PGMPY_VARIABLE_ELIMINATION,worker_policy=policy)
        check(res.status==q.GRAPH_SUCCESS and verify_graph_receipt(raw,out).numeric_cross_checked, 'real pgmpy VE')
    return 0

if __name__=='__main__':raise SystemExit(main())
