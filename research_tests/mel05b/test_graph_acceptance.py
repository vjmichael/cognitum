"""Native integration cases. Requires exact MEL-05A + MEL-04B checkout."""
from dataclasses import replace
import pytest
from cognitum.mel import cooperation as g, native as n, engines as e, engines_pb2 as ep
from cognitum.mel import verified_graph as vg, uncertainty_pb2 as pb
from research_tests.mel04b.test_cooperation import S, fixture_plan, setup

TOL=(('kan',(1e-6,)),('vfa',(1e-6,)),('base',(1e-12,)))


def test_real_three_engine_guarded_graph():
    p=fixture_plan(); h,t=setup(p)
    try:
        v=vg.execute_verified(h,p,t,TOL)
        assert v.status=='verified' and v.reserved_calls==4
        w=pb.GraphWitness.FromString(v.witness)
        assert w.plan_sha256.hex()==p.identity and w.represented_inputs_only
        nodes={x.node_id:x for x in w.nodes}
        assert list(nodes['query'].hamming_distance)==[2,0,0]
        assert list(nodes['query'].best_index)==[1,2]
        assert nodes['query'].lossy_history
        assert len(nodes['kan'].samples)==3
        assert vg.replay(p,v.outcome,TOL,v.witness)
        with pytest.raises(ValueError):vg.replay(p,v.outcome,TOL,v.witness+b'\x00')
    finally:h.close()


def test_ambiguous_threshold_suppresses_publication():
    f=n.gaussian([[0.]],[[1.]],[-1.],constant=1.,axes=[('x','1')],domain=[(-2000.,2000.)],output_unit='1')
    p=g.Plan('ambiguous',S,(g.Seed('seed',n.points(f,[[1000.]])),g.Vfa('value','seed',f),g.Threshold('bits','value',1.,'1')),g.Budget(step_ms=5000))
    h,t=setup(p)
    try:
        v=vg.execute_verified(h,p,t,(('value',(1e-12,)),))
        assert v.status=='verification_refused' and v.outcome is None and v.witness is None
        assert v.reserved_calls==1
    finally:h.close()


def test_wrong_tolerance_and_receipt_refused():
    p=fixture_plan();h,t=setup(p)
    try:
        raw=g.execute(h,p,t);assert raw.status=='completed'
        with pytest.raises(ValueError):vg.verify_graph(p,raw,TOL[:-1])
        with pytest.raises(ValueError):vg.verify_graph(p,replace(raw,plan_sha256='0'*64),TOL)
        bad=replace(raw,nodes=(replace(raw.nodes[0],object_sha256='0'*64),)+raw.nodes[1:])
        with pytest.raises(ValueError):vg.verify_graph(p,bad,TOL)
        with pytest.raises(ValueError):vg.verify_graph(p,raw,(('kan',(0.,)),)+TOL[1:])
    finally:h.close()


def test_exact_threshold_lift_preserves_loss():
    f=n.gaussian([],[],[],constant=1.,axes=[('bit0','1')],domain=[(-1.,2.)],output_unit='1')
    p=g.Plan('lift',S,(g.Seed('seed',n.points(f,[[0.],[1.]])),g.Threshold('bits','seed',1.,'1'),g.Lift('lift','bits',2,1),g.Vfa('v','lift',f)),g.Budget(step_ms=5000))
    h,t=setup(p)
    try:
        guarded=vg.execute_verified(h,p,t,(('v',(0.,)),))
        assert guarded.status=='verified'
        w=pb.GraphWitness.FromString(guarded.witness);nodes={x.node_id:x for x in w.nodes}
        assert nodes['bits'].verified_packed_bits==b'\x02'
        assert nodes['v'].lossy_history
    finally:h.close()
