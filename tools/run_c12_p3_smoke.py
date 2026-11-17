"""Five offline C12 P3 functional checks: not a benchmark campaign."""
from cognitum.proto import planning_stochastic_pb2 as sp
from cognitum.proto import planning_structured_pb2 as tp
from cognitum.planning_stochastic import run,verify
from cognitum.planning_structured import run_htn,verify_htn,run_temporal,verify_temporal
from tests.test_c12_p3_stochastic import example
from tests.test_c12_p3_structured import htn,temporal,wire


def main():
    count=0
    for method, iterations, proof in [(sp.FINITE_HORIZON_BELLMAN,0,True),
                                       (sp.UCT_MCTS,80,False)]:
        q=example(method,iterations);frame=wire(q)
        answer=run(frame,enabled=True,host_authorized=True)
        r=verify(frame,answer)
        assert r.evidence_valid and r.optimality_verified==proof
        count+=1
    q=htn();frame=wire(q);answer=run_htn(frame,enabled=True,host_authorized=True)
    assert verify_htn(frame,answer).optimality_verified
    count+=1
    for deadline, infeasible in [(0,False),(9,True)]:
        q=temporal();q.actions[2].latest_finish=deadline
        frame=wire(q);answer=run_temporal(frame,enabled=True,host_authorized=True)
        assert verify_temporal(frame,answer).evidence_valid
        assert (tp.TemporalResult.FromString(answer).status==tp.VERIFIED_TEMPORAL_INFEASIBLE)==infeasible
        count+=1
    print(f'PASS: C12 P3 advanced planning smoke {count}/{count} functional scenarios')

if __name__=='__main__':main()
