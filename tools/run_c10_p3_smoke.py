"""C10 P3 smoke: native Z3 incremental scopes + independently checked finite proof."""
import hashlib
from pathlib import Path
import sys
from cognitum.formal_backend import ApprovedBackend,SolverRegistry
from cognitum.formal_session import run_session_frame,verify_session_frame
from cognitum.proto import formal_advanced_pb2 as a,formal_backend_pb2 as b

def wire(m):return m.SerializeToString(deterministic=True)
def main():
    path=Path('/lib/x86_64-linux-gnu/libz3.so.4')
    if not path.is_file():
        print('SKIPPED: optional Z3 shared library not present');return 2
    registry=SolverRegistry((ApprovedBackend('z3-lib','z3-lib',str(path),hashlib.sha256(path.read_bytes()).hexdigest()),))
    plan=a.SessionPlan(schema_version=1,backend_id='z3-lib',trace_id='smoke-c10-p3')
    plan.variables.add(name='p',sort=b.BOOL)
    plan.steps.add(kind=a.SessionStep.ASSERT,assertion=b.Expr(variable='p'))
    plan.steps.add(kind=a.SessionStep.CHECK)
    plan.steps.add(kind=a.SessionStep.PUSH)
    plan.steps.add(kind=a.SessionStep.ASSERT,assertion=b.Expr(application=b.Application(op=b.NOT,args=[b.Expr(variable='p')])))
    plan.steps.add(kind=a.SessionStep.CHECK)
    plan.steps.add(kind=a.SessionStep.POP)
    plan.steps.add(kind=a.SessionStep.CHECK)
    frame=wire(plan);result=run_session_frame(frame,registry,host_authorized=True)
    out=a.SessionResult.FromString(result)
    if not out.completed or [x.backend_result.verdict for x in out.checkpoints]!=[b.SAT,b.UNSAT,b.SAT]:
        raise AssertionError('native incremental scopes did not hold')
    if not out.checkpoints[1].core_independently_verified:raise AssertionError('finite core not proven')
    if not a.SessionReceipt.FromString(verify_session_frame(frame,result)).evidence_valid:
        raise AssertionError('independent session receipt failed')
    plan.steps[0].label='tampered'
    if a.SessionReceipt.FromString(verify_session_frame(wire(plan),result)).evidence_valid:
        raise AssertionError('tampered plan was accepted')
    print('PASS: 5/5 C10 P3 smoke gates (SAT, scoped UNSAT, pop rollback, finite core, tamper denial)')
    return 0
if __name__=='__main__':sys.exit(main())
