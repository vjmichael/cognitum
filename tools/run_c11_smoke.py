"""C11 P1 bounded offline HiGHS functional smoke (not a benchmark)."""
from cognitum.optimization import OptimizationRegistry, verify_optimization_frame, make_optimization_audit
from cognitum.proto import optimization_pb2 as p


def run():
    r = p.OptimizeRequest(schema_version=1, backend_id='scipy-highs', timeout_ms=1000, trace_id='smoke')
    r.variables.add(name='a', lower=0, upper=3)
    r.variables.add(name='b', lower=0, upper=4)
    r.objective.sense = p.MAXIMIZE
    r.objective.terms.add(variable='a', coefficient=3)
    r.objective.terms.add(variable='b', coefficient=2)
    c = r.constraints.add(relation=p.LESS_EQUAL, rhs=7)
    c.terms.add(variable='a', coefficient=2)
    c.terms.add(variable='b', coefficient=1)
    f = r.SerializeToString(deterministic=True)
    registry = OptimizationRegistry(enabled=True)
    deny = p.OptimizeResult.FromString(registry.run_frame(f))
    assert deny.status == p.REJECTED
    print('PASS: host-gate rejection')
    res = p.OptimizeResult.FromString(registry.run_frame(f, host_authorized=True))
    assert res.status == p.VERIFIED_OPTIMAL and res.objective_value == 12
    print('PASS: HiGHS exact finite optimum')
    bf = res.SerializeToString(deterministic=True)
    receipt = p.OptimizeReceipt.FromString(verify_optimization_frame(f, bf))
    assert receipt.evidence_valid and receipt.optimality_verified
    print('PASS: independent proof recheck')
    audit = p.OptimizationAudit.FromString(make_optimization_audit(f, bf))
    assert audit.backend_id == 'scipy-highs' and audit.status == p.VERIFIED_OPTIMAL
    print('PASS: data-minimized Protobuf audit')
    r.variables[0].upper = 1_000_000
    f = r.SerializeToString(deterministic=True)
    large = p.OptimizeResult.FromString(registry.run_frame(f, host_authorized=True))
    assert large.status == p.VERIFIED_FEASIBLE and not large.optimality_verified
    print('PASS: large-domain claim remains uncertified')


if __name__ == '__main__':
    run()
