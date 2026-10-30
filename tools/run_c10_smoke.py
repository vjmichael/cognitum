"""C10 bounded functionality smoke. Deterministic exact assertions, no benchmarks."""
from cognitum.formal_solver import solve_frame, verify_frame, prove_frame, verify_property_frame
from cognitum.proto import formal_pb2 as pb


def wire(value):
    return value.SerializeToString(deterministic=True)


def constraint(request, left, right, bound):
    a=request.atoms.add()
    a.difference.left, a.difference.right, a.difference.bound = left, right, bound


def check(request, want):
    binary=wire(request)
    result=solve_frame(binary)
    assert pb.SolveResult.FromString(result).status == want
    assert pb.CheckResult.FromString(verify_frame(binary,result)).evidence_valid


def main():
    # 1. exact mixed Boolean/integer witness
    req=pb.SolveRequest(schema_version=1,integer_variables=['x'])
    req.boolean_variables.append('allow')
    req.atoms.add(boolean_name='allow')
    constraint(req,'x','$ZERO',2)
    req.clauses.add(literals=[1,2])
    check(req,pb.SAT)

    # 2. unsatisfiable difference cycle with checkable exhaustive certificate
    req=pb.SolveRequest(schema_version=1,integer_variables=['x','y'])
    constraint(req,'x','y',0);constraint(req,'y','x',-1)
    req.clauses.add(literals=[1]);req.clauses.add(literals=[2])
    check(req,pb.UNSAT)

    # 3. explicit budget exhaustion never reports false UNSAT
    req=pb.SolveRequest(schema_version=1,max_assignments=1,boolean_variables=['flag'])
    req.atoms.add(boolean_name='flag');req.clauses.add(literals=[1])
    result=solve_frame(wire(req))
    assert pb.SolveResult.FromString(result).status==pb.UNKNOWN
    assert not pb.CheckResult.FromString(verify_frame(wire(req),result)).evidence_valid

    # 4. vacuous proof identified as inconsistent assumptions
    req=pb.SolveRequest(schema_version=1,boolean_variables=['ok'])
    req.atoms.add(boolean_name='ok')
    req.clauses.add(literals=[1]);req.clauses.add(literals=[-1])
    prop=pb.PropertyRequest(assumptions=req,required_literal=1)
    result=prove_frame(wire(prop))
    assert pb.PropertyResult.FromString(result).verdict==pb.INCONSISTENT_ASSUMPTIONS
    assert pb.CheckResult.FromString(verify_property_frame(wire(prop),result)).evidence_valid

    # 5. property counterexample is a tangible model, not a guessed assertion
    req=pb.SolveRequest(schema_version=1,boolean_variables=['ok'])
    req.atoms.add(boolean_name='ok')
    prop=pb.PropertyRequest(assumptions=req,required_literal=1)
    result=prove_frame(wire(prop))
    assert pb.PropertyResult.FromString(result).verdict==pb.COUNTEREXAMPLE
    assert pb.CheckResult.FromString(verify_property_frame(wire(prop),result)).evidence_valid
    print('PASS: C10 5/5 bounded SAT/UNSAT/UNKNOWN/property smoke checks')


if __name__=='__main__': main()
