"""C10 native typed-Protobuf admission and safe result semantics."""
from hashlib import sha256
import unittest

from cognitum.proto import formal_pb2 as pb
from cognitum.formal_wire import execute, decode_result


def make(backend="exhaustive", impossible=False):
    req=pb.VerifyRequest(schema_version=1,backend=backend,timeout_ms=1000)
    req.variables.add(name="x",lower=-1,upper=3)
    a=req.constraints.add(relation="eq",rhs=2)
    a.terms.add(name="x",coefficient=1)
    if impossible:
        b=req.constraints.add(relation="eq",rhs=3)
        b.terms.add(name="x",coefficient=1)
    return req.SerializeToString(deterministic=True)


class C10WireTests(unittest.TestCase):
    def test_exact_sat_and_unsat_verification(self):
        sat=make()
        r=decode_result(execute(sat),sat)
        self.assertEqual(r.status,"SAT")
        self.assertEqual(tuple(r.witness),(2,))
        self.assertEqual(r.request_sha256,sha256(sat).hexdigest())
        unsat=make(impossible=True)
        d=decode_result(execute(unsat),unsat)
        self.assertEqual(d.status,"UNSAT_EXHAUSTIVE")
        self.assertFalse(d.witness)

    def test_replay_and_tampering_rejected(self):
        req=make()
        frame=execute(req)
        with self.assertRaises(ValueError):
            decode_result(frame,make(impossible=True))
        forged=pb.VerifyResult()
        forged.ParseFromString(frame)
        forged.witness[0]=3
        with self.assertRaises(ValueError):
            decode_result(forged.SerializeToString(deterministic=True),req)
        forged.ParseFromString(frame)
        forged.status="UNSAT_EXHAUSTIVE"
        forged.ClearField("witness")
        with self.assertRaises(ValueError):
            decode_result(forged.SerializeToString(deterministic=True),req)

    def test_canonical_request_and_schema_fail_closed(self):
        req=make()
        for invalid in (b"",b"\x0a\xff",req+b"\x98\x06\x01",
                        req+b"\x08\x01",b"x"*16385):
            with self.subTest(frame=invalid[:8]),self.assertRaises(ValueError):
                execute(invalid)
        bad=pb.VerifyRequest(schema_version=2,backend="exhaustive",timeout_ms=1000)
        bad.variables.add(name="x",lower=0,upper=1)
        with self.assertRaises(ValueError):
            execute(bad.SerializeToString(deterministic=True))

    def test_no_arbitrary_smtlib_or_host_grants(self):
        fields={f.name for f in pb.VerifyRequest.DESCRIPTOR.fields}
        self.assertNotIn("script",fields)
        self.assertNotIn("grants",fields)
        self.assertNotIn("permission",fields)
        self.assertNotIn("python_code",fields)


if __name__=="__main__":
    unittest.main()
