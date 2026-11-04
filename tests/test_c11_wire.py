"""C11 typed native wire and end-to-end real-backend acceptance."""
from unittest.mock import patch
import unittest

from cognitum.proto import optimization_pb2 as pb
from cognitum.optimization_wire import execute, decode_result


def schedule_request():
    r=pb.ScheduleRequest(schema_version=1,horizon=8,
                         resources=["a","b"],unit="hour",timeout_ms=3000)
    r.jobs.add(name="a1",duration=2,release=0,deadline=6,
               eligible_resources=["a","b"])
    r.jobs.add(name="a2",duration=2,release=0,deadline=8,
               eligible_resources=["a","b"],after=["a1"])
    return r.SerializeToString(deterministic=True)


def allocation_request():
    r=pb.AllocationRequest(schema_version=1,unit="item",timeout_ms=3000)
    r.quantities.add(name="a",lower=0,upper=2,cost=4)
    r.quantities.add(name="b",lower=0,upper=4,cost=1)
    r.constraints.add(coefficients=[1,1],relation="ge",rhs=3)
    return r.SerializeToString(deterministic=True)


class C11WireTests(unittest.TestCase):
    def test_real_native_schedule(self):
        try:
            import ortools
        except ImportError:
            self.skipTest("OR-Tools not installed")
        req=schedule_request()
        result=decode_result("schedule",req,execute("schedule",req))
        self.assertEqual(result.status,"OPTIMAL")
        self.assertTrue(result.has_objective)
        self.assertEqual(result.makespan,4)
        self.assertEqual(len(result.assignments),2)

    def test_real_native_allocation(self):
        try:
            import scipy
        except ImportError:
            self.skipTest("SciPy not installed")
        req=allocation_request()
        result=decode_result("allocation",req,execute("allocation",req))
        self.assertEqual(result.status,"OPTIMAL")
        self.assertTrue(result.has_objective)
        self.assertEqual(result.objective,3)
        self.assertEqual(tuple(result.values),(0,3))

    def test_untrusted_modified_witness_fails(self):
        req=allocation_request()
        forged=pb.AllocationResult(schema_version=1,status="OPTIMAL",values=[0,0],
                                   objective=0,has_objective=True)
        from hashlib import sha256
        forged.request_sha256=sha256(req).hexdigest()
        with self.assertRaises(ValueError):
            decode_result("allocation",req,
                          forged.SerializeToString(deterministic=True))
        req=schedule_request()
        forged_s=pb.ScheduleResult(schema_version=1,status="OPTIMAL",
                                   makespan=2,has_objective=True,
                                   request_sha256=sha256(req).hexdigest())
        forged_s.assignments.add(name="a1",resource="a",start=0,end=2)
        forged_s.assignments.add(name="a2",resource="a",start=0,end=2)
        with self.assertRaises(ValueError):
            decode_result("schedule",req,
                          forged_s.SerializeToString(deterministic=True))

    def test_feasible_witness_not_independent_optimality_certificate(self):
        # A submitted valid but suboptimal allocation passes the exact
        # feasibility/objective checker. Neither the string OPTIMAL nor a
        # solver-reported bound is independently verified by this facade.
        req=allocation_request()
        from hashlib import sha256
        alternative=pb.AllocationResult(
            schema_version=1,status="FEASIBLE",values=[2,4],
            objective=12,has_objective=True,
            request_sha256=sha256(req).hexdigest())
        decoded=decode_result("allocation",req,
                              alternative.SerializeToString(deterministic=True))
        self.assertEqual(decoded.status,"FEASIBLE")
        self.assertEqual(tuple(decoded.values),(2,4))

    def test_modified_witness_wrong_exact_objective_rejected(self):
        req=allocation_request()
        from hashlib import sha256
        tampered=pb.AllocationResult(
            schema_version=1,status="OPTIMAL",values=[2,4],
            objective=11,has_objective=True,
            request_sha256=sha256(req).hexdigest())
        with self.assertRaisesRegex(ValueError,"invalid allocation result witness"):
            decode_result("allocation",req,
                          tampered.SerializeToString(deterministic=True))

    def test_nonfeasible_results_have_no_solution(self):
        from hashlib import sha256
        req=allocation_request()
        reply=pb.AllocationResult(schema_version=1,status="INFEASIBLE",
                                  request_sha256=sha256(req).hexdigest(),
                                  has_objective=True,objective=4)
        with self.assertRaises(ValueError):
            decode_result("allocation",req,
                          reply.SerializeToString(deterministic=True))

    def test_noncanonical_and_unknown_messages_rejected(self):
        req=schedule_request()
        for frame in (b"",req+b"\x98\x06\x01",
                      req+b"\x08\x01",b"\x0a\xff",b"x"*16385):
            with self.subTest(frame=frame[:10]),self.assertRaises(ValueError):
                execute("schedule",frame)
        with self.assertRaises(ValueError):
            execute("unknown",req)
        with self.assertRaises(ValueError):
            execute("allocation",schedule_request())

    def test_zero_timeout_and_unsafe_units_rejected(self):
        req=pb.ScheduleRequest()
        req.ParseFromString(schedule_request())
        req.timeout_ms=0
        with self.assertRaises(ValueError):
            execute("schedule",req.SerializeToString(deterministic=True))
        req.timeout_ms=1000
        req.unit="whichever"
        with self.assertRaises(ValueError):
            execute("schedule",req.SerializeToString(deterministic=True))

    def test_no_code_or_authorization_fields(self):
        for cls in (pb.ScheduleRequest,pb.AllocationRequest):
            names={f.name for f in cls.DESCRIPTOR.fields}
            for forbidden in ("code","script","python","host_permission","authorization","shell"):
                self.assertNotIn(forbidden,names)


if __name__=="__main__":
    unittest.main()
