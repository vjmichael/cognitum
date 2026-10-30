"""Narrow C10 P2 local Z3 shared-library integration smoke (no benchmark)."""
from pathlib import Path
import hashlib
import os
import sys
from cognitum.formal_backend import ApprovedBackend,SolverRegistry,verify_backend_frame
from cognitum.proto import formal_backend_pb2 as p

def wire(m):return m.SerializeToString(deterministic=True)

def main():
    candidate=os.environ.get('COGNITUM_SMOKE_Z3_LIB','/lib/x86_64-linux-gnu/libz3.so.4')
    path=Path(candidate)
    if not path.is_file():
        print('SKIPPED: No Z3 shared library available for optional integration smoke')
        return 2
    approved=ApprovedBackend('z3-lib','z3-lib',str(path),hashlib.sha256(path.read_bytes()).hexdigest())
    reg=SolverRegistry((approved,))
    cases=[(p.GT,'x','2',p.SAT),(p.LE,'x','0',p.SAT)]
    for kind,name,bound,want in cases:
        request=p.BackendRun(schema_version=1,backend_id='z3-lib')
        request.variables.add(name=name,sort=p.INT)
        root=request.assertions.add().application;root.op=kind;root.args.add().variable=name;root.args.add().integer.decimal=bound
        payload=wire(request)
        result=reg.run_frame(payload,host_authorized=True)
        obj=p.BackendResult.FromString(result)
        rec=p.VerificationReceipt.FromString(verify_backend_frame(payload,result))
        if obj.verdict!=want or not rec.evidence_valid:raise AssertionError('invalid real Z3 witness')
    r=p.BackendRun(schema_version=1,backend_id='z3-lib')
    r.variables.add(name='x',sort=p.INT)
    for kind,bound in [(p.GT,'2'),(p.LT,'0')]:
        a=r.assertions.add().application;a.op=kind;a.args.add().variable='x';a.args.add().integer.decimal=bound
    result=reg.run_frame(wire(r),host_authorized=True)
    if p.BackendResult.FromString(result).verification!=p.UNSAT_NOT_PROVEN:raise AssertionError('UNSAT must remain unverified')
    reg.disable()
    if p.BackendResult.FromString(reg.run_frame(wire(r),host_authorized=True)).verdict!=p.REJECTED:
        raise AssertionError('kill switch missing')
    print('PASS: 4/4 focused Z3 shared-library smoke scenarios; UNSAT is not a proof')
    return 0

if __name__=='__main__':sys.exit(main())
