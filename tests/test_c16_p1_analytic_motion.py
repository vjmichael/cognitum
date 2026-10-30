"""C16 P1: exact, dimensioned motion and adversarial Protobuf contract."""
from fractions import Fraction
import hashlib
import unittest
from google.protobuf.internal.encoder import _VarintBytes
from cognitum.proto import physics_linear_motion_pb2 as pb
from cognitum.physics_motion import calculate, verify


def rational(dest, n, d=1):
    f = Fraction(n, d)
    dest.numerator, dest.denominator = str(f.numerator), str(f.denominator)


def req(steps=2, velocity=3, acceleration=2, dt=1, x0=0, mass=2):
    r = pb.LinearMotionRequest(schema_version=1, unit_system='SI:m,s,kg', steps=steps)
    for k, v in [('initial_position_m', x0), ('initial_velocity_m_per_s', velocity),
                 ('acceleration_m_per_s2', acceleration), ('mass_kg', mass), ('time_step_s', dt)]:
        rational(getattr(r, k), v)
    return r


def wire(r):
    return r.SerializeToString(deterministic=True)


class MotionTests(unittest.TestCase):
    def run_case(self, r):
        data = wire(r)
        payload = calculate(data)
        self.assertTrue(verify(data, payload))
        result = pb.LinearMotionResult.FromString(payload)
        self.assertEqual(result.request_sha256, hashlib.sha256(data).digest())
        self.assertFalse(result.physical_model_validated)
        self.assertFalse(result.host_approved)
        self.assertEqual(result.method, 'ANALYTIC_CONSTANT_ACCELERATION_V1')
        return result

    def test_constant_acceleration_exact_trajectory(self):
        result = self.run_case(req())
        self.assertEqual([s.position_m.numerator for s in result.samples], ['0','4','10'])
        self.assertEqual([s.velocity_m_per_s.numerator for s in result.samples], ['3','5','7'])
        self.assertEqual(result.samples[-1].kinetic_energy_j.numerator, '49')
        self.assertEqual(result.samples[-1].work_j.numerator, '40')

    def test_fractional_timestep(self):
        result = self.run_case(req(steps=3, velocity=Fraction(1,3), acceleration=Fraction(-2,5), dt=Fraction(1,10)))
        self.assertEqual(result.samples[1].position_m.numerator, '47')
        self.assertEqual(result.samples[1].position_m.denominator, '1500')

    def test_zero_acceleration_is_supported(self):
        result = self.run_case(req(steps=3, velocity=Fraction(-5,2), acceleration=0))
        self.assertEqual(result.samples[-1].work_j.numerator, '0')

    def test_energy_work_identity_holds_every_sample(self):
        result = self.run_case(req(steps=7, velocity=-4, acceleration=Fraction(2,7), dt=Fraction(3,7)))
        start = Fraction(int(result.samples[0].kinetic_energy_j.numerator), int(result.samples[0].kinetic_energy_j.denominator))
        for sample in result.samples:
            ke = Fraction(int(sample.kinetic_energy_j.numerator),int(sample.kinetic_energy_j.denominator))
            work = Fraction(int(sample.work_j.numerator),int(sample.work_j.denominator))
            self.assertEqual(ke - start, work)

    def test_unsupported_units_rejected(self):
        r=req();r.unit_system='imperial:ft,s,slug'
        with self.assertRaisesRegex(ValueError, 'UNIT_SYSTEM'): calculate(wire(r))

    def test_missing_dimension_rejected(self):
        r=req();r.ClearField('mass_kg')
        with self.assertRaisesRegex(ValueError,'MISSING_DIMENSIONED_INPUT'):calculate(wire(r))

    def test_zero_negative_mass_rejected(self):
        for mass in [0,-1]:
            with self.subTest(mass=mass), self.assertRaisesRegex(ValueError,'INVALID_MASS'):
                calculate(wire(req(mass=mass)))

    def test_invalid_time_or_step_budget(self):
        cases=[req(dt=0),req(dt=-1),req(steps=0),req(steps=257),req(steps=256,dt=4)]
        for r in cases:
            with self.subTest(r=r), self.assertRaises(ValueError):calculate(wire(r))

    def test_fraction_denominator_zero_or_noncanonical(self):
        for n,d in [('1','0'),('1','2'),('-0','1'),('01','1'),('1','02'),('2','4'),('1','-2')]:
            r=req();r.mass_kg.numerator=n;r.mass_kg.denominator=d
            if (n,d)==('1','2'):continue
            with self.subTest(n=n,d=d), self.assertRaises(ValueError):calculate(wire(r))

    def test_unbounded_input(self):
        r=req();r.mass_kg.numerator='1000001'
        with self.assertRaisesRegex(ValueError, 'UNBOUNDED'):calculate(wire(r))

    def test_unsupported_version(self):
        r=req();r.schema_version=2
        with self.assertRaisesRegex(ValueError,'UNSUPPORTED_SCHEMA'):calculate(wire(r))

    def test_reject_unknown_protobuf_fields(self):
        raw=wire(req())+_VarintBytes((999<<3)|0)+b'\x01'
        with self.assertRaisesRegex(ValueError,'UNKNOWN_DUPLICATE'):calculate(raw)

    def test_reject_duplicate_known_scalar(self):
        raw=wire(req())+b'\x08\x01' # duplicate schema_version=1
        with self.assertRaisesRegex(ValueError,'UNKNOWN_DUPLICATE'):calculate(raw)

    def test_reject_trailing_malformed_protobuf(self):
        with self.assertRaises(ValueError):calculate(wire(req())+b'\x80')

    def test_reject_nonbytes(self):
        with self.assertRaises(ValueError):calculate(bytearray(wire(req())))

    def test_reject_tampered_result(self):
        raw=wire(req()); r=pb.LinearMotionResult.FromString(calculate(raw))
        r.samples[2].velocity_m_per_s.numerator='8'
        self.assertFalse(verify(raw,wire(r)))

    def test_reject_forged_host_or_model_certification(self):
        raw=wire(req());r=pb.LinearMotionResult.FromString(calculate(raw))
        r.host_approved=True
        self.assertFalse(verify(raw,wire(r)))
        r.host_approved=False;r.physical_model_validated=True
        self.assertFalse(verify(raw,wire(r)))

    def test_reject_wrong_request_binding(self):
        raw=wire(req()); out=calculate(raw)
        self.assertFalse(verify(wire(req(steps=3)),out))

    def test_reject_truncated_result(self):
        raw=wire(req());out=calculate(raw)
        with self.assertRaises(ValueError):verify(raw,out[:-1])

    def test_overlarge_frames(self):
        with self.assertRaisesRegex(ValueError,'FRAME'):calculate(wire(req())+b'\x00'*9000)

if __name__=='__main__':unittest.main()
