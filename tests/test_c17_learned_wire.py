"""C17 host-admitted real sklearn training / checkpoint wire acceptance."""
from dataclasses import replace
from hashlib import sha256
import unittest

from cognitum.proto import temporal_practical_pb2 as pb
from cognitum.temporal_learned_wire import (
    execute_train,verify_train_result,execute_forecast,verify_forecast,
)


def training_request():
    r=pb.TrainRequest(schema_version=1,units=["temperature"],
        origin_id="source_run",provenance_kind="synthetic",
        quality_declared="unverified",train_count=40,lags=3)
    for i in range(65):
        r.samples.add(time_ms=i*1000,values=[10+i*.1],
                      observed=[True],source_id="probe",
                      observation_id="sample_"+str(i))
    return r.SerializeToString(deterministic=True)


def forecast_request(train_wire,training):
    original=pb.TrainRequest()
    original.ParseFromString(train_wire)
    r=pb.ForecastRequest(schema_version=1,
                        origin_id=original.origin_id,
                        provenance_kind=original.provenance_kind,
                        quality_declared=original.quality_declared,
                        steps=5)
    r.artifact.CopyFrom(training.artifact)
    for item in list(original.samples)[:40]:
        r.history.add().CopyFrom(item)
    return r.SerializeToString(deterministic=True)


class C17LearnedWireTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import scipy,sklearn,numpy
        except ImportError:
            raise unittest.SkipTest("optional genuine temporal-learned backend not installed")

    def test_training_requires_explicit_host_permission_and_replays_forecast(self):
        raw=training_request()
        with self.assertRaises(PermissionError):
            execute_train(raw)
        result=verify_train_result(raw,execute_train(raw,host_admitted=True))
        self.assertEqual(result.status,"TRAINED")
        self.assertEqual(result.artifact.training_count,40)
        self.assertEqual(result.request_sha256,sha256(raw).hexdigest())
        query=forecast_request(raw,result)
        forecast=verify_forecast(query,execute_forecast(query))
        self.assertIn(forecast.status,("OK","OOD_ABSTAIN"))
        self.assertEqual(len(forecast.means),5)
        self.assertEqual(len(forecast.variances),5)

    def test_forged_checkpoint_and_future_training_overlap_rejected(self):
        raw=training_request()
        result=pb.TrainResult()
        result.ParseFromString(execute_train(raw,host_admitted=True))
        query=pb.ForecastRequest()
        query.ParseFromString(forecast_request(raw,result))
        query.artifact.coefficients[0].values[0]+=1
        with self.assertRaises(ValueError):
            execute_forecast(query.SerializeToString(deterministic=True))
        query.ParseFromString(forecast_request(raw,result))
        query.history[3].values[0]=2000
        with self.assertRaises(ValueError):
            execute_forecast(query.SerializeToString(deterministic=True))
        original=pb.TrainRequest()
        original.ParseFromString(raw)
        original.train_count=63
        with self.assertRaises(ValueError):
            execute_train(original.SerializeToString(deterministic=True),host_admitted=True)

    def test_forged_output_and_correlation_rejected(self):
        raw=training_request()
        trained=verify_train_result(raw,execute_train(raw,host_admitted=True))
        request=forecast_request(raw,trained)
        out=pb.ForecastResult()
        out.ParseFromString(execute_forecast(request))
        out.means[0].values[0]+=100
        with self.assertRaises(ValueError):
            verify_forecast(request,out.SerializeToString(deterministic=True))
        t=pb.TrainResult()
        t.ParseFromString(execute_train(raw,host_admitted=True))
        t.request_sha256="0"*64
        with self.assertRaises(ValueError):
            verify_train_result(raw,t.SerializeToString(deterministic=True))


if __name__=="__main__":
    unittest.main()
