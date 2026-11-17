"""Focused C11 P2 real-library workflow smoke; not a benchmark or host admission test."""
from cognitum.optimization_workflows import WorkflowRegistry, make_workflow_audit, verify_workflow_frame
from cognitum.proto import workflows_pb2 as p


def main():
    reg=WorkflowRegistry(enabled=True)
    examples=[]
    a=p.WorkflowRequest(schema_version=1,trace_id='c11p2-assignment')
    a.assignment.workers=2;a.assignment.jobs=2
    for w,j,c in [(0,0,1),(1,0,4),(0,1,5),(1,1,2)]:
        a.assignment.edges.add(worker=w,job=j,cost=c)
    examples.append(('assignment',a,3))
    a=p.WorkflowRequest(schema_version=1,trace_id='c11p2-packing')
    a.packing.capacity=5
    for ident,weight,value in [('A',2,4),('B',3,8),('C',5,7)]:a.packing.items.add(id=ident,weight=weight,value=value)
    examples.append(('packing',a,12))
    a=p.WorkflowRequest(schema_version=1,trace_id='c11p2-flow')
    a.flow.nodes.add(id='origin',supply=2);a.flow.nodes.add(id='target',supply=-2)
    a.flow.arcs.add(from_node=0,to_node=1,capacity=2,cost=3)
    examples.append(('flow',a,6))
    a=p.WorkflowRequest(schema_version=1,trace_id='c11p2-scheduling')
    a.scheduling.horizon=6;a.scheduling.resources.add(id='machine',capacity=1)
    a.scheduling.tasks.add(id='cut',duration=2,resource_id='machine',demand=1,earliest_start=0,latest_start=3)
    a.scheduling.tasks.add(id='paint',duration=2,resource_id='machine',demand=1,earliest_start=0,latest_start=4)
    a.scheduling.precedences.add(before=0,after=1)
    examples.append(('scheduling',a,4))
    a=p.WorkflowRequest(schema_version=1,trace_id='c11p2-routing')
    a.routing.nodes=3;a.routing.costs.extend([0,2,2,2,0,2,2,2,0])
    examples.append(('routing',a,6))
    for kind,req,expected in examples:
        frame=req.SerializeToString(deterministic=True)
        denied=p.WorkflowResult.FromString(reg.run_frame(frame))
        assert denied.status==p.REJECTED
        result_frame=reg.run_frame(frame,host_authorized=True)
        result=p.WorkflowResult.FromString(result_frame)
        receipt=p.WorkflowReceipt.FromString(verify_workflow_frame(frame,result_frame))
        audit=p.WorkflowAudit.FromString(make_workflow_audit(frame,result_frame))
        assert result.status==p.VERIFIED_OPTIMAL, (kind,result.reason_code)
        assert result.objective_value==expected,(kind,result.objective_value,expected)
        assert receipt.evidence_valid and receipt.optimality_verified
        assert audit.backend_id.startswith(kind+':') and not audit.host_approved
        print('PASS:',kind,'real solver, typed receipt and audit')

if __name__=='__main__':main()
