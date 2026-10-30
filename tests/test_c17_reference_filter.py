"""Offline C17 bounded Kalman reference checks, not real host authorization."""
from fractions import Fraction
from decimal import Decimal
import unittest

from cognitum.proto import temporal_filter_pb2 as p
from cognitum.temporal_filter import run_filter, METHOD


def request():
    r = p.FilterRequest(initial_mean="0", initial_variance="1", process_variance_per_second="1", measurement_variance="1", units="m", forecast_time_ms=1000)
    r.samples.add(time_ms=0, observation="2", source_id="frame0")
    r.samples.add(time_ms=1000, source_id="frame1")
    return r


def evaluate(r):
    return p.FilterResult.FromString(run_filter(r.SerializeToString(deterministic=True)))


class C17ReferenceTests(unittest.TestCase):
    def test_known_analytical_posterior(self):
        out = evaluate(request())
        self.assertEqual(Decimal(out.mean), Decimal('1'))
        self.assertEqual(Decimal(out.variance), Decimal('1.5'))
        self.assertEqual((out.assimilated, out.missing), (1, 1))
        self.assertEqual(out.at_time_ms, 1000)
        self.assertEqual(out.method, METHOD)
        self.assertIn('NOT_LU_HOST_AUTHORIZATION_OR_PHYSICAL_CERTIFICATION',out.limitations)

    def test_rational_independent_reference(self):
        r = request()
        r.samples.add(time_ms=2000, observation="4", source_id="frame2")
        r.forecast_time_ms = 3000
        out = evaluate(r)
        m1, v1 = Fraction(1), Fraction(1,2)
        p = v1 + 2 * Fraction(1)
        gain = p/(p+1)
        m2 = m1 + gain*(4-m1)
        v2 = (1-gain)**2*p + gain**2
        self.assertAlmostEqual(float(out.mean),float(m2),places=12)
        self.assertAlmostEqual(float(out.variance),float(v2 + 1),places=12)
        self.assertEqual(out.assimilated,2)

    def test_zero_process_variance_does_not_inflate(self):
        r=request();r.process_variance_per_second="0"
        self.assertEqual(Decimal(evaluate(r).variance), Decimal('0.5'))

    def test_multiple_missing_supported(self):
        r=request();r.samples.add(time_ms=2000,source_id="frame2");r.forecast_time_ms=3000
        out=evaluate(r)
        self.assertEqual(out.missing,2)
        self.assertEqual(Decimal(out.variance),Decimal('3.5'))

    def test_new_evidence_changes_mean(self):
        r=request();r.samples[1].observation="4"
        self.assertGreater(Decimal(evaluate(r).mean),Decimal('1'))

    def test_nonmonotonic_time(self):
        r=request();r.samples.add(time_ms=500,observation='3',source_id='frame2')
        with self.assertRaisesRegex(ValueError,'NONMONOTONIC_TIME'):evaluate(r)

    def test_duplicate_source(self):
        r=request();r.samples[1].source_id='frame0'
        with self.assertRaisesRegex(ValueError,'INVALID_OR_DUPLICATE_SOURCE'):evaluate(r)

    def test_source_identity_syntax(self):
        r=request();r.samples[0].source_id='../../private'
        with self.assertRaisesRegex(ValueError,'INVALID_OR_DUPLICATE_SOURCE'):evaluate(r)

    def test_missing_observations_rejected(self):
        r=request();r.samples[0].ClearField('observation')
        with self.assertRaisesRegex(ValueError,'NO_OBSERVED_EVIDENCE'):evaluate(r)

    def test_no_samples_rejected(self):
        r=request();r.ClearField('samples')
        with self.assertRaisesRegex(ValueError,'INVALID_SAMPLE_COUNT'):evaluate(r)

    def test_duplicate_time_rejected(self):
        r=request();r.samples[1].time_ms=0
        with self.assertRaisesRegex(ValueError,'NONMONOTONIC_TIME'):evaluate(r)

    def test_time_horizon_rejected(self):
        r=request();r.forecast_time_ms=1000+3600001
        with self.assertRaisesRegex(ValueError,'FORECAST_OUT_OF_BOUNDS'):evaluate(r)

    def test_backwards_forecast_rejected(self):
        r=request();r.forecast_time_ms=999
        with self.assertRaisesRegex(ValueError,'FORECAST_OUT_OF_BOUNDS'):evaluate(r)

    def test_time_gap_rejected(self):
        r=request();r.samples[1].time_ms=86400001;r.forecast_time_ms=86400001
        with self.assertRaisesRegex(ValueError,'TIME_GAP_EXCEEDED'):evaluate(r)

    def test_infinite_or_not_a_number_rejected(self):
        for bad in ('NaN','Infinity','1e3','+1',' 1','01','-1e2'):
            with self.subTest(bad=bad):
                r=request();r.samples[0].observation=bad
                with self.assertRaisesRegex(ValueError,'INVALID_DECIMAL'):evaluate(r)

    def test_negative_variance_rejected(self):
        for field in ('initial_variance','process_variance_per_second','measurement_variance'):
            r=request();setattr(r,field,'-1')
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'INVALID_VARIANCE'):evaluate(r)

    def test_zero_measurement_variance_rejected(self):
        r=request();r.measurement_variance='0'
        with self.assertRaisesRegex(ValueError,'INVALID_VARIANCE'):evaluate(r)

    def test_missing_units_rejected(self):
        r=request();r.units=''
        with self.assertRaisesRegex(ValueError,'UNITS_REQUIRED'):evaluate(r)

    def test_canonical_unknown_field_rejected(self):
        raw=request().SerializeToString(deterministic=True)
        with self.assertRaisesRegex(ValueError,'NONCANONICAL_PROTOBUF'):run_filter(raw+b'\xf8\x07\x01')

    def test_canonical_duplicate_known_field_rejected(self):
        raw=request().SerializeToString(deterministic=True)
        with self.assertRaisesRegex(ValueError,'NONCANONICAL_PROTOBUF'):run_filter(raw + b'\x0a\x01\x30')

    def test_frame_size_limit(self):
        with self.assertRaisesRegex(ValueError,'INVALID_FRAME_SIZE'):run_filter(b'x'*32769)

    def test_frame_requires_bytes(self):
        with self.assertRaisesRegex(ValueError,'INVALID_FRAME_SIZE'):run_filter('not bytes')

    def test_malformed_wire_rejected(self):
        with self.assertRaisesRegex(ValueError,'MALFORMED_PROTOBUF'):run_filter(b'\xff')

    def test_sample_limit(self):
        r=request()
        for i in range(128):r.samples.add(time_ms=1001+i,source_id=f'frame{i+2}')
        r.forecast_time_ms=1200
        with self.assertRaisesRegex(ValueError,'INVALID_SAMPLE_COUNT'):evaluate(r)

    def test_empty_decimal_rejected(self):
        r=request();r.initial_mean=''
        with self.assertRaisesRegex(ValueError,'INVALID_DECIMAL'):evaluate(r)

    def test_result_is_deterministic(self):
        raw=request().SerializeToString(deterministic=True)
        self.assertEqual(run_filter(raw),run_filter(raw))

if __name__ == '__main__':unittest.main()
