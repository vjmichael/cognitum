"""C12 request and result wire contracts with real graph backend."""
import unittest
from hashlib import sha256

from cognitum.proto import planning_pb2 as pb
from cognitum.planning_wire import execute,decode_result


def request(algorithm="dijkstra"):
    req=pb.PlanRequest(schema_version=1,facts=["home","fuel","work","done"],
        initial=["home","fuel"],goal=["done"],goal_forbids=["home"],
        horizon=3,risk_budget=2,algorithm=algorithm)
    req.actions.add(name="travel",requires=["home","fuel"],
        add=["work"],delete=["home"],cost=2,risk=1)
    req.actions.add(name="finish",requires=["work"],
        add=["done"],delete=["work"],cost=2,risk=1)
    req.actions.add(name="direct",requires=["home"],
        add=["done"],delete=["home"],cost=9,risk=2)
    return req.SerializeToString(deterministic=True)


class C12WireTests(unittest.TestCase):
    def test_graph_solver_end_to_end(self):
        try:
            import networkx
        except ImportError:
            self.skipTest("NetworkX not installed")
        for algo in ("dijkstra","astar","bfs","dag_dp"):
            with self.subTest(algo=algo):
                raw=request(algo)
                result=decode_result(raw,execute(raw))
                self.assertTrue(result.has_result)
                self.assertIn(result.status,("OPTIMAL","FEASIBLE"))
                self.assertEqual(result.total_cost,9 if algo=="bfs" else 4)
                self.assertEqual(result.request_sha256,sha256(raw).hexdigest())

    def test_forged_plan_and_tamper_rejected(self):
        raw=request()
        from cognitum.planning_wire import pb as out
        result=out.PlanResult(schema_version=1,status="OPTIMAL",
            has_result=True,actions=["finish"],final_state=["done"],
            total_cost=2,total_risk=0,backend="networkx_dijkstra",
            request_sha256=sha256(raw).hexdigest())
        with self.assertRaises(ValueError):
            decode_result(raw,result.SerializeToString(deterministic=True))
        result.ClearField("actions")
        result.actions.extend(["travel","finish"])
        result.total_cost=99
        with self.assertRaises(ValueError):
            decode_result(raw,result.SerializeToString(deterministic=True))

    def test_forged_no_plan_is_not_accepted(self):
        raw=request()
        res=pb.PlanResult(schema_version=1,status="UNREACHABLE_EXHAUSTIVE",
            actions=["direct"],request_sha256=sha256(raw).hexdigest(),
            backend="networkx_dijkstra")
        with self.assertRaises(ValueError):
            decode_result(raw,res.SerializeToString(deterministic=True))

    def test_noncanonical_and_unsafe_request_fails_closed(self):
        raw=request()
        for invalid in (b"",raw+b"\x98\x06\x01",raw+b"\x08\x01",
                        b"\x0a\xff",b"!"*16385):
            with self.subTest(raw=invalid[:12]),self.assertRaises(ValueError):
                execute(invalid)
        req=pb.PlanRequest()
        req.ParseFromString(raw)
        req.algorithm="mcts_eval_code"
        with self.assertRaises(ValueError):
            execute(req.SerializeToString(deterministic=True))
        self.assertNotIn("shell",{f.name for f in pb.PlanAction.DESCRIPTOR.fields})
        self.assertNotIn("permissions",{f.name for f in pb.PlanRequest.DESCRIPTOR.fields})


if __name__=="__main__":
    unittest.main()
