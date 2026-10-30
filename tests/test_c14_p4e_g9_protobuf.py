"""G9 research-only capability is typed, replayable, and never an authority source."""
import unittest
from cognitum import causal_interval_comparison as wired
from cognitum.proto import causal_interval_comparison_pb2 as pb


def request(scenario='observed_heterogeneous', seed=1001):
    return pb.IntervalComparisonRequest(schema_version=1,trace_id='test-trace',
        scenario=scenario,seed=seed,sample_size=300,bootstrap_resamples=199,
        confidence=.95)

class G9WireTests(unittest.TestCase):
    def test_real_proto_round_trip(self):
        a=request()
        self.assertEqual(pb.IntervalComparisonRequest.FromString(a.SerializeToString()),a)
    def test_accepts_bounded_synthetic_request(self):
        a=request();result,receipt=wired.calculate(a)
        self.assertTrue(wired.verify(a,result,receipt))
        self.assertTrue(result.research_only)
        self.assertFalse(result.host_authorized)
        self.assertFalse(receipt.host_authenticated)
        self.assertEqual(len(result.methods),6)
    def test_confounder_does_not_expose_causal_point_interval(self):
        a=request('hidden_confounder');result,receipt=wired.calculate(a)
        self.assertTrue(wired.verify(a,result,receipt))
        self.assertTrue(all(not x.point_interval_available for x in result.methods))
    def test_no_overlap_does_not_expose_point_interval(self):
        a=request('no_overlap');result,receipt=wired.calculate(a)
        self.assertTrue(wired.verify(a,result,receipt))
        self.assertTrue(all(not x.point_interval_available for x in result.methods))
    def test_replay_rejects_tampered_interval(self):
        a=request();out,receipt=wired.calculate(a);out.methods[0].upper=99
        self.assertFalse(wired.verify(a,out,receipt))
    def test_replay_rejects_other_request(self):
        a=request();out,receipt=wired.calculate(a)
        self.assertFalse(wired.verify(request(seed=1111),out,receipt))
    def test_replay_rejects_forged_host_authority(self):
        a=request();out,receipt=wired.calculate(a);receipt.host_authenticated=True
        self.assertFalse(wired.verify(a,out,receipt))
    def test_rejects_invalid_resource_budget(self):
        a=request();a.bootstrap_resamples=100000
        with self.assertRaises(ValueError):wired.calculate(a)

if __name__=='__main__':unittest.main()
