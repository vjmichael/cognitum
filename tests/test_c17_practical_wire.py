"""C17 typed real SciPy Kalman/HMM Protobuf and forged-output testing."""
import unittest
from hashlib import sha256
from cognitum.proto import temporal_practical_pb2 as pb
from cognitum.temporal_practical_wire import execute,verify


def state_request():
    req=pb.FilterRequest(
        schema_version=1,units=["metres","celsius"],origin_id="sensor_run",
        provenance_kind="measured",quality_declared="unverified",
        kind="constant_velocity",process_variance_per_second=.03,
        measurement_variance=.2,prior_variance=1.,
        innovation_gate_sigma=3.,max_forecast_ms=30000,
        forecast_time_ms=14000)
    for i in range(12):
        req.samples.add(time_ms=1000*i,
                        values=[float(i),20.+i*.1],
                        observed=[i!=4,True],
                        source_id="camera",observation_id="sample_"+str(i))
    return req.SerializeToString(deterministic=True)


def hmm_request():
    req=pb.HMMRequest(
        schema_version=1,state_names=["normal","alarm"],prior=[.9,.1],
        sampling_interval_ms=1000,model_source="prepared_model",
        alert_probability=.65)
    req.transition_rows.add(values=[.95,.05])
    req.transition_rows.add(values=[.05,.95])
    req.emission_rows.add(values=[.95,.05])
    req.emission_rows.add(values=[.05,.95])
    for i in range(12):
        req.observations.add(time_ms=i*1000,category=0 if i<6 else 1,
                             observed=True,source_id="camera",
                             observation_id="obs_"+str(i))
    return req.SerializeToString(deterministic=True)


class C17WireTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy,scipy
        except ImportError:
            raise unittest.SkipTest("optional SciPy/NumPy temporal backend not installed")

    def test_real_multichannel_kalman_result_and_missing_mask(self):
        raw=state_request()
        out=verify("kalman",raw,execute("kalman",raw))
        self.assertEqual(out.status,"OK")
        self.assertEqual(out.missing_count,1)
        self.assertEqual(out.forecast_time_ms,14000)
        self.assertEqual(len(out.forecast_mean),2)
        self.assertEqual(len(out.points),12)
        self.assertFalse(out.points[4].has_innovation[0])
        self.assertTrue(out.points[4].has_innovation[1])
        self.assertEqual(out.request_sha256,sha256(raw).hexdigest())

    def test_real_hmm_transition_and_provenance(self):
        raw=hmm_request()
        out=verify("hmm",raw,execute("hmm",raw))
        self.assertEqual(out.status,"OK")
        self.assertEqual(out.probable_states[0],"normal")
        self.assertEqual(out.probable_states[-1],"alarm")
        self.assertTrue(any(out.change_alerts))

    def test_forged_kalman_and_hmm_rejected(self):
        raw=state_request()
        out=pb.FilterResult()
        out.ParseFromString(execute("kalman",raw))
        out.forecast_mean[0]+=100.
        with self.assertRaises(ValueError):
            verify("kalman",raw,out.SerializeToString(deterministic=True))
        raw=hmm_request()
        result=pb.HMMResult()
        result.ParseFromString(execute("hmm",raw))
        result.probable_states[0]="alarm"
        with self.assertRaises(ValueError):
            verify("hmm",raw,result.SerializeToString(deterministic=True))

    def test_noncanonical_frame_and_wrong_masks_fail_closed(self):
        raw=state_request()
        for bad in (b"",raw+b"\x98\x06\x01",raw+b"\x08\x01",
                    b"\x0a\xff",b"!"*200001):
            with self.subTest(bad=bad[:10]),self.assertRaises(ValueError):
                execute("kalman",bad)
        req=pb.FilterRequest()
        req.ParseFromString(raw)
        req.samples[0].observed.pop()
        with self.assertRaises(ValueError):
            execute("kalman",req.SerializeToString(deterministic=True))
        req.ParseFromString(raw)
        req.samples[1].time_ms=0
        with self.assertRaises(ValueError):
            execute("kalman",req.SerializeToString(deterministic=True))

    def test_model_authority_not_in_contract(self):
        for cls in (pb.FilterRequest,pb.HMMRequest):
            names={field.name for field in cls.DESCRIPTOR.fields}
            for name in ("python","code","shell","host_grant","camera_open","weights_path"):
                self.assertNotIn(name,names)


if __name__=="__main__":
    unittest.main()
