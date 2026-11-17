"""C11 P2 focused workflow functionality, mathematical checks and fail-closed tests."""
import copy
import itertools
import random
import unittest

from cognitum.proto import workflows_pb2 as p
from cognitum.optimization_workflows import (
    WorkflowRegistry, _finite_oracle, _solution_cost, _validate,
    make_workflow_audit, verify_workflow_frame,
)


def wire(m):
    return m.SerializeToString(deterministic=True)


def assignment():
    r=p.WorkflowRequest(schema_version=1,trace_id='assignment')
    r.assignment.workers=3;r.assignment.jobs=2
    for j in range(2):
        for w in range(3):r.assignment.edges.add(worker=w,job=j,cost=10-2*j-w)
    return r


def packing():
    r=p.WorkflowRequest(schema_version=1,trace_id='packing');r.packing.capacity=7
    for n,w,v in [('a',4,10),('b',3,9),('c',5,8)]:r.packing.items.add(id=n,weight=w,value=v)
    return r


def flow():
    r=p.WorkflowRequest(schema_version=1,trace_id='flow')
    r.flow.nodes.add(id='source',supply=2)
    r.flow.nodes.add(id='sink',supply=-2)
    r.flow.arcs.add(from_node=0,to_node=1,capacity=3,cost=4)
    return r


def scheduling():
    r=p.WorkflowRequest(schema_version=1,trace_id='scheduling')
    r.scheduling.horizon=8;r.scheduling.resources.add(id='cpu',capacity=1)
    r.scheduling.tasks.add(id='one',duration=2,resource_id='cpu',demand=1,earliest_start=0,latest_start=5)
    r.scheduling.tasks.add(id='two',duration=3,resource_id='cpu',demand=1,earliest_start=0,latest_start=5)
    r.scheduling.precedences.add(before=0,after=1)
    return r


def routing():
    r=p.WorkflowRequest(schema_version=1,trace_id='routing')
    r.routing.nodes=4
    r.routing.costs.extend(0 if i==j else abs(i-j)+1 for i in range(4) for j in range(4))
    return r


class C11WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.registry=WorkflowRegistry(enabled=True)

    def call(self,req):
        data=wire(req)
        resultdata=self.registry.run_frame(data,host_authorized=True)
        result=p.WorkflowResult.FromString(resultdata)
        receipt=p.WorkflowReceipt.FromString(verify_workflow_frame(data,resultdata))
        return data,result,resultdata,receipt

    def test_assignment_real_scipy_optimum(self):
        data,res,out,check=self.call(assignment())
        self.assertEqual((res.status,res.objective_value),(p.VERIFIED_OPTIMAL,15))
        self.assertTrue(check.evidence_valid and check.optimality_verified)
        self.assertIn('scipy-',res.backend_version)

    def test_packing_real_highs_optimum(self):
        _,res,_,check=self.call(packing())
        self.assertEqual((res.status,res.objective_value),(p.VERIFIED_OPTIMAL,19))
        self.assertEqual(sorted(res.solution.packed_indices),[0,1])
        self.assertTrue(check.optimality_verified)

    def test_min_cost_flow_real_network_simplex(self):
        _,res,_,check=self.call(flow())
        self.assertEqual((res.status,res.objective_value),(p.VERIFIED_OPTIMAL,8))
        self.assertIn('networkx-',res.backend_version)
        self.assertTrue(check.optimality_verified)

    def test_scheduling_real_highs_and_precedence(self):
        _,res,_,check=self.call(scheduling())
        self.assertEqual((res.status,res.objective_value),(p.VERIFIED_OPTIMAL,5))
        self.assertTrue(check.optimality_verified)

    def test_routing_networkx(self):
        _,res,_,check=self.call(routing())
        self.assertEqual((res.status,res.objective_value),(p.VERIFIED_OPTIMAL,10))
        self.assertEqual(res.solution.tour[0],0)
        self.assertEqual(res.solution.tour[-1],0)
        self.assertTrue(check.optimality_verified)

    def test_heuristic_route_suboptimal_not_certified(self):
        # Known counterexample: NetworkX greedy 62, exact independent TSP optimum 60.
        matrix=[[0,15,18,15,15],[15,0,17,19,7],[18,17,0,6,17],
                [15,19,6,0,16],[15,7,17,16,0]]
        req=p.WorkflowRequest(schema_version=1,trace_id='route-regression')
        req.routing.nodes=5
        req.routing.costs.extend(x for row in matrix for x in row)
        _,result,_,check=self.call(req)
        self.assertEqual(result.objective_value,62)
        self.assertEqual(_finite_oracle(req)[0],60)
        self.assertEqual(result.status,p.VERIFIED_FEASIBLE)
        self.assertTrue(check.evidence_valid)
        self.assertFalse(check.optimality_verified)

    def test_all_five_audits_hide_values(self):
        for req in (assignment(),packing(),flow(),scheduling(),routing()):
            with self.subTest(kind=req.WhichOneof('problem')):
                frame,res,out,check=self.call(req)
                audit=p.WorkflowAudit.FromString(make_workflow_audit(frame,out))
                self.assertTrue(audit.backend_id.startswith(req.WhichOneof('problem')+':'))
                self.assertEqual(audit.status,res.status)
                self.assertEqual(audit.witness_verified,res.witness_verified)
                self.assertEqual(audit.optimality_verified,check.optimality_verified)
                self.assertFalse(audit.host_approved)

    def test_host_gate_and_disable(self):
        req=assignment();data=wire(req)
        out=p.WorkflowResult.FromString(self.registry.run_frame(data))
        self.assertEqual(out.status,p.REJECTED)
        self.registry.disable()
        out=p.WorkflowResult.FromString(self.registry.run_frame(data,host_authorized=True))
        self.assertEqual(out.status,p.REJECTED)
        self.assertEqual(out.reason_code,'REGISTRY_DISABLED')

    def test_sparse_assignment_infeasible_verified(self):
        r=assignment();r.assignment.ClearField('edges');r.assignment.edges.add(worker=0,job=0,cost=3)
        _,res,_,check=self.call(r)
        self.assertEqual(res.status,p.VERIFIED_INFEASIBLE)
        self.assertTrue(check.optimality_verified)

    def test_infeasible_schedule_cycle(self):
        r=scheduling();r.scheduling.precedences.add(before=1,after=0)
        _,res,_,check=self.call(r)
        self.assertEqual(res.status,p.VERIFIED_INFEASIBLE)
        self.assertTrue(check.evidence_valid)

    def test_big_assignment_feasible_not_certified(self):
        r=assignment();r.assignment.workers=10;r.assignment.jobs=9;r.assignment.ClearField('edges')
        for j in range(9):
            for w in range(10):r.assignment.edges.add(worker=w,job=j,cost=abs(w-j))
        _,res,_,check=self.call(r)
        self.assertEqual(res.status,p.VERIFIED_FEASIBLE)
        self.assertTrue(check.evidence_valid)
        self.assertFalse(check.optimality_verified)

    def test_big_packing_feasible_not_certified(self):
        r=packing();r.packing.ClearField('items');r.packing.capacity=10
        for i in range(15):r.packing.items.add(id=f'part{i}',weight=1,value=i+1)
        _,res,_,check=self.call(r)
        self.assertEqual(res.status,p.VERIFIED_FEASIBLE)
        self.assertFalse(check.optimality_verified)

    def test_big_flow_feasible_not_certified(self):
        r=flow();r.flow.arcs[0].capacity=5000
        _,res,_,check=self.call(r)
        self.assertEqual(res.status,p.VERIFIED_FEASIBLE)
        self.assertFalse(check.optimality_verified)

    def test_no_solver_answer_does_not_fabricate_optimum(self):
        self.registry.backends['packing:scipy-highs']=lambda *args:(None,'LIMIT','synthetic')
        _,res,_,check=self.call(packing())
        self.assertEqual(res.status,p.UNKNOWN)
        self.assertFalse(check.evidence_valid)

    def test_forged_solution_rejected_by_checker_and_audit(self):
        req=packing();data,res,_,_=self.call(req)
        res.solution.packed_indices.append(2)
        forged=wire(res)
        check=p.WorkflowReceipt.FromString(verify_workflow_frame(data,forged))
        self.assertFalse(check.evidence_valid)
        with self.assertRaises(ValueError):make_workflow_audit(data,forged)

    def test_forged_optimality_rejected(self):
        req=packing();req.packing.ClearField('items');req.packing.capacity=12
        for i in range(14):req.packing.items.add(id=f'part{i}',weight=1,value=i)
        data,res,_,_=self.call(req)
        self.assertEqual(res.status,p.VERIFIED_FEASIBLE)
        res.status=p.VERIFIED_OPTIMAL;res.optimality_verified=True;res.exact_states_checked=123
        check=p.WorkflowReceipt.FromString(verify_workflow_frame(data,wire(res)))
        self.assertFalse(check.evidence_valid)

    def test_forged_host_approval_rejected(self):
        req=assignment();data,res,_,_=self.call(req)
        res.host_approved=True
        check=p.WorkflowReceipt.FromString(verify_workflow_frame(data,wire(res)))
        self.assertFalse(check.evidence_valid)

    def test_request_result_binding_rejected(self):
        req=assignment();data,res,_,_=self.call(req)
        req.assignment.edges[0].cost=99
        check=p.WorkflowReceipt.FromString(verify_workflow_frame(wire(req),wire(res)))
        self.assertFalse(check.evidence_valid)

    def test_invalid_packing_duplicates(self):
        r=packing();r.packing.items.add(id='a',weight=1,value=2)
        _,res,_,_=self.call(r)
        self.assertEqual(res.status,p.REJECTED)

    def test_invalid_flow_unbalanced(self):
        r=flow();r.flow.nodes[1].supply=-1
        _,res,_,_=self.call(r)
        self.assertEqual(res.status,p.REJECTED)

    def test_invalid_route_asymmetry(self):
        r=routing();r.routing.costs[1]+=1
        _,res,_,_=self.call(r)
        self.assertEqual(res.status,p.REJECTED)

    def test_invalid_schedule_resource(self):
        r=scheduling();r.scheduling.tasks[0].demand=9
        _,res,_,_=self.call(r)
        self.assertEqual(res.status,p.REJECTED)

    def test_wrong_scope_and_resource_overload_rejected(self):
        r=scheduling();a=p.WorkflowSolution()
        a.starts.add(index=0,value=0);a.starts.add(index=1,value=0)
        with self.assertRaises(ValueError):_solution_cost(r,a)

    def test_flow_conservation_rejected(self):
        r=flow();a=p.WorkflowSolution();a.flows.add(index=0,value=1)
        with self.assertRaises(ValueError):_solution_cost(r,a)

    def test_tour_revisit_rejected(self):
        r=routing();a=p.WorkflowSolution();a.tour.extend([0,1,1,3,0])
        with self.assertRaises(ValueError):_solution_cost(r,a)

    def test_wrong_workflow_type_rejected(self):
        req=p.WorkflowRequest(schema_version=1,trace_id='none')
        _,res,_,_=self.call(req)
        self.assertEqual(res.status,p.REJECTED)

    def test_resource_time_limit_rejected(self):
        req=assignment();req.timeout_ms=6000
        _,res,_,_=self.call(req)
        self.assertEqual(res.status,p.REJECTED)

    def test_optional_cpsat_backend_absent_or_functional(self):
        r=scheduling();r.backend_id='ortools-cpsat'
        _,res,_,receipt=self.call(r)
        if res.status==p.UNKNOWN:
            self.assertFalse(receipt.evidence_valid)
            self.assertEqual(res.reason_code,'BACKEND_UNAVAILABLE_OR_FAILED')
        else:
            self.assertEqual(res.status,p.VERIFIED_OPTIMAL)
            self.assertTrue(receipt.optimality_verified)
        self.assertEqual(res.backend_id,'scheduling:ortools-cpsat')

    def test_reject_arbitrary_backend_and_wrong_type_backend(self):
        r=assignment();r.backend_id='some/../python-script'
        _,res,_,_=self.call(r)
        self.assertEqual(res.status,p.REJECTED)
        r.backend_id='ortools-cpsat'
        _,res,_,_=self.call(r)
        self.assertEqual(res.status,p.REJECTED)

    def test_finite_oracle_proves_infeasibility_even_backend_unknown(self):
        r=flow();r.flow.arcs[0].capacity=1
        self.registry.backends['flow:networkx-simplex']=lambda *args:(None,'LIMIT','synthetic')
        _,res,_,check=self.call(r)
        self.assertEqual(res.status,p.VERIFIED_INFEASIBLE)
        self.assertTrue(check.optimality_verified)

    def test_model_attempt_to_forge_receipt_status_rejected(self):
        r=routing();data,res,_,_=self.call(r)
        res.status=p.VERIFIED_FEASIBLE
        res.optimality_verified=True
        chk=p.WorkflowReceipt.FromString(verify_workflow_frame(data,wire(res)))
        self.assertFalse(chk.evidence_valid)

    def test_random_packing_independent_brute_force(self):
        rnd=random.Random(2711)
        for trial in range(16):
            req=p.WorkflowRequest(schema_version=1,trace_id='rnd')
            req.packing.capacity=rnd.randint(0,12)
            vals=[]
            for i in range(5):
                w=rnd.randint(0,8);v=rnd.randint(-5,15)
                req.packing.items.add(id=f'item{i}',weight=w,value=v);vals.append((w,v))
            _,res,_,check=self.call(req)
            best=max(sum(v for i,(w,v) in enumerate(vals) if mask>>i&1)
                     for mask in range(32) if sum(w for i,(w,v) in enumerate(vals) if mask>>i&1)<=req.packing.capacity)
            self.assertEqual(res.objective_value,best)
            self.assertTrue(check.optimality_verified)

    def test_random_assignment_independent_brute_force(self):
        rnd=random.Random(3711)
        for trial in range(12):
            req=p.WorkflowRequest(schema_version=1,trace_id='rand')
            req.assignment.workers=4;req.assignment.jobs=3
            costs={}
            for j in range(3):
                for w in range(4):
                    c=rnd.randint(-6,14);costs[(w,j)]=c
                    req.assignment.edges.add(worker=w,job=j,cost=c)
            _,res,_,check=self.call(req)
            best=min(sum(costs[(w,j)] for j,w in enumerate(perm)) for perm in itertools.permutations(range(4),3))
            self.assertEqual(res.objective_value,best)
            self.assertTrue(check.optimality_verified)


if __name__=='__main__':unittest.main()
