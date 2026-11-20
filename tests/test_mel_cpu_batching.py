"""Planner properties and negative controls without importing benchmark harnesses."""
import unittest
from dataclasses import replace
try:
    import numpy
    import google.protobuf
except ModuleNotFoundError:
    raise unittest.SkipTest('optional scientific dependencies absent')

from cognitum.registry import Registry
from cognitum.mel import admission as a,native as n,cpu_batching as b


class CpuBatchPlannerTests(unittest.TestCase):
    def setUp(self):
        self.reg=Registry()
        self.reg.install(n.NativeVFAPlugin,enabled=True)
        for op in n.OP:self.reg.nominate(op,n.NAME)
        self.scope=a.Scope('batch-test','w','u','turn')
        self.route=next(x for x in a.routes() if x.operation=='vfa.evaluate')
        self.f=n.gaussian([[0.]],[[1.]],[1.],constant=0.,
            axes=[('x','1')],domain=[(-1.,1.)],output_unit='1')
        self.parent=n.make_call(self.route.public_name,self.f,n.points(self.f,[[-.5],[0.],[.25]]),'test',self.scope.turn)
        key,*_=b.describe(self.parent)
        self.cal=b.Calibration(self.route.operation,key,'f'*64,'a'*40,'fixture',
            tuple(b.Estimate(k,100.+k,.1,1000*k) for k in b.SIZES[self.route.operation]))
        self.limits=a.Limits(calls=3,timeout_ms=10000)
        self.budget=b.Budget(100000,20000,1000.,1.,100000)

    def plan(self,limits=None,budget=None,cal=None,scope=None,**options):
        return b.plan_cpu(self.reg,scope or self.scope,self.route,self.parent,limits or self.limits,
            budget or self.budget,cal or self.cal,**dict({'allow_research':True},**options))

    def test_partition_canonical_and_no_authority(self):
        raw=b.wire(self.parent)
        plan=self.plan()
        self.assertFalse(plan.execution_authorized)
        self.assertEqual(plan.parent_sha256,b.digest(raw))
        self.assertEqual([(p.start,p.stop) for p in plan.parts],[(0,2),(2,3)])
        points=[]
        for q in plan.parts:
            self.assertEqual(q.request.function.wire,self.f.wire)
            self.assertEqual(q.request_sha256,b.digest(b.wire(q.request)))
            points.extend(q.request.points.message().body.points.coordinates)
        self.assertEqual(points,[-.5,0.,.25])
        self.assertEqual(b.wire(self.parent),raw)
        self.assertEqual(plan,self.plan())

    def test_adapt_to_hard_limit_or_measured_peak_target(self):
        for plan in (self.plan(limits=replace(self.limits,points=1)),
                     self.plan(budget=replace(self.budget,max_items_per_call=1)),
                     self.plan(budget=replace(self.budget,estimated_peak_bytes=1000))):
            self.assertEqual(len(plan.parts),3)
            self.assertEqual(plan.total_work,6)
            self.assertEqual(plan.total_result_reserve_bytes,3*self.limits.result_bytes)

    def test_fail_closed(self):
        for fn in (lambda:self.plan(allow_research=False),
                   lambda:self.plan(preference='gpu'),
                   lambda:self.plan(scope=replace(self.scope,turn='other')),
                   lambda:self.plan(cal=replace(self.cal,workload_key='0'*64)),
                   lambda:self.plan(limits=replace(self.limits,calls=1)),
                   lambda:self.plan(limits=replace(self.limits,work=1)),
                   lambda:self.plan(limits=replace(self.limits,request_bytes=1)),
                   lambda:self.plan(budget=replace(self.budget,total_result_reserve_bytes=1)),
                   lambda:self.plan(budget=replace(self.budget,total_request_bytes=1)),
                   lambda:self.plan(budget=replace(self.budget,estimated_elapsed_ms=1.)),
                   lambda:self.plan(budget=replace(self.budget,estimated_cpu_s=0.)),
                   lambda:self.plan(budget=replace(self.budget,estimated_peak_bytes=1))):
            with self.subTest(fn=fn):
                with self.assertRaises(ValueError):fn()
        self.reg.enable(n.NAME,False)
        with self.assertRaises(ValueError):self.plan()


if __name__=='__main__':unittest.main()
