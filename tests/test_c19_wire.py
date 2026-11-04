"""C19 typed real Ripser persistence Protobuf source and result checks."""
from math import cos,sin,pi
import unittest

from cognitum.topology_rips import snapshot_hash
from cognitum.proto import topology_pb2 as pb
from cognitum.topology_wire import execute,verify

def fixture():
    coords=tuple((float(cos(2*pi*i/16)),float(sin(2*pi*i/16)))
                 for i in range(16))
    q=pb.Query(schema_version=1,source_id="ring",
        snapshot_sha256=snapshot_hash(coords),coordinate_unit="metres",
        metric="euclidean",filtration="vietoris_rips",
        maximum_scale=2.2,maximum_homology_dimension=1,max_points=64)
    for x,y in coords:q.points.add(values=[x,y])
    return q.SerializeToString(deterministic=True)

class C19WireTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:import ripser,numpy,scipy
        except ImportError:raise unittest.SkipTest("optional real ripser/scipy unavailable")

    def test_typed_circle_and_essential_intervals(self):
        req=fixture()
        reply=verify(req,execute(req))
        self.assertEqual(reply.status,"OK")
        self.assertEqual(reply.input_points,16)
        self.assertTrue(reply.has_h0_mst_check)
        self.assertGreater(reply.longest_finite_h1,.5)
        self.assertTrue(any(not x.has_finite_death for x in reply.intervals))
        self.assertEqual(len(reply.request_sha256),64)

    def test_forged_persistence_and_source_rejected(self):
        req=fixture()
        out=pb.Result()
        out.ParseFromString(execute(req))
        out.longest_finite_h1=999
        with self.assertRaises(ValueError):
            verify(req,out.SerializeToString(deterministic=True))
        query=pb.Query()
        query.ParseFromString(req)
        query.points[1].values[0]+=1
        with self.assertRaises(ValueError):
            execute(query.SerializeToString(deterministic=True))

    def test_noncanonical_unknown_and_oversized_query(self):
        req=fixture()
        for bad in (b"",req+b"\x98\x06\x01",req+b"\x08\x01",
                    b"\x0a\xff",b"x"*20001):
            with self.subTest(raw=bad[:6]),self.assertRaises(ValueError):
                execute(bad)

if __name__=="__main__":
    unittest.main()
