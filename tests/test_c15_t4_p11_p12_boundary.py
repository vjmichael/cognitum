"""Disposable local-TSA and synthetic-measurement tests, NOT external acceptance."""
from __future__ import annotations

import copy
import json
import csv
from hashlib import sha256
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from cryptography import x509
from cryptography.hazmat.primitives import serialization

from cognitum.proto import spatial_functional_material_p11_p12_pb2 as w
from cognitum.spatial_functional_material import T4Rejected
from cognitum.spatial_functional_material_p11_p12 import evaluate_p11,evaluate_p12
from cognitum.spatial_functional_material_p8_p10 import policy_snapshot
from tests.test_c15_t4_p8_p10_external_readiness import make_policy,make_dataset
from tests.test_c15_t4_p5_p7_assurance import create, rewrite
from cognitum.spatial_functional_material_p5_p7 import P5_DOMAIN

OPENSSL=shutil.which('openssl')
POLICY='1.3.6.1.4.1.55555.1'


def run(*cmd):
    proc=subprocess.run(cmd,capture_output=True,check=False,timeout=20)
    if proc.returncode: raise RuntimeError(f'{cmd}: {proc.stderr.decode(errors="replace")}')


def receipt_fixture(tmp: Path, future_observations: bool = False):
    p7,_,keys=create(n=2)
    if future_observations:
        for rec in p7.p6.p5.source_statements:
            rewrite(rec,keys,P5_DOMAIN,observed_at_ms=1800000000000)
    def extend_signer_window(policy):
        for entry in policy['keys']:
            entry['valid_until_ms']=1801000000000
    env,roots,_,_=make_policy(keys=keys,
        modifications=extend_signer_window if future_observations else None)
    snapshot=policy_snapshot(env,roots)
    request=w.T4P11Rfc3161Request(schema_version=1,research_only=True,p6=p7.p6,
                                  expected_tsa_policy_oid=POLICY)
    data=p7.p6.plan_lock.SerializeToString(deterministic=True)
    # A real host must preserve nonce query provenance; these keys are test-only.
    run(OPENSSL,'req','-x509','-newkey','rsa:2048','-keyout',str(tmp/'key.pem'),
        '-out',str(tmp/'tsa.pem'),'-nodes','-days','2','-subj','/CN=LOCAL-FIXTURE-TSA',
        '-addext','basicConstraints=critical,CA:TRUE',
        '-addext','extendedKeyUsage=critical,timeStamping',
        '-addext','keyUsage=critical,digitalSignature')
    run(OPENSSL,'ts','-query','-digest',sha256(data).hexdigest(),'-sha256',
        '-cert','-out',str(tmp/'query.tsq'))
    (tmp/'serial').write_text('01\n')
    (tmp/'config.cnf').write_text(f'''[tsa]
default_tsa = tsa_config
[tsa_config]
serial = {tmp/'serial'}
signer_cert = {tmp/'tsa.pem'}
signer_key = {tmp/'key.pem'}
signer_digest = sha256
default_policy = {POLICY}
digests = sha256
accuracy = secs:1
ordering = yes
''')
    run(OPENSSL,'ts','-reply','-config',str(tmp/'config.cnf'),'-queryfile',
        str(tmp/'query.tsq'),'-out',str(tmp/'reply.tsr'))
    request.timestamp_query_der=(tmp/'query.tsq').read_bytes()
    request.timestamp_response_der=(tmp/'reply.tsr').read_bytes()
    pem=(tmp/'tsa.pem').read_bytes()
    fingerprint=sha256(x509.load_pem_x509_certificate(pem).public_bytes(
        serialization.Encoding.DER)).hexdigest()
    host=dict(host_ca_pem=pem,host_tsa_cert_pem=pem,
              host_tsa_cert_sha256=fingerprint,host_policy_oids={POLICY},
              openssl_executable=OPENSSL)
    return request,snapshot,host


@unittest.skipUnless(OPENSSL,'OpenSSL executable not installed')
class P11OfflineTimestampTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._temp=tempfile.TemporaryDirectory()
        cls.root=Path(cls._temp.name)
        cls.fixture,cls.snapshot,cls.host=receipt_fixture(cls.root)

    @classmethod
    def tearDownClass(cls): cls._temp.cleanup()

    def verdict(self,request=None,host=None):
        return evaluate_p11(request or self.fixture,self.snapshot,
                            **(host or self.host))

    def test_valid_local_token_not_external_pre_registration(self):
        r=self.verdict()
        self.assertTrue(r.receipt_chain_signature_verified)
        self.assertTrue(r.requested_nonce_and_imprint_verified)
        self.assertTrue(r.signer_certificate_host_pinned)
        # Our local token was minted AFTER the synthetic September observation.
        self.assertFalse(r.timestamp_before_observations)
        self.assertFalse(r.claimed_chronology_consistent)
        self.assertFalse(r.independent_tsa_identity_verified)
        self.assertFalse(r.certificate_revocation_checked)
        self.assertFalse(r.grants_authority)

    def rejected(self,code,request=None,host=None):
        with self.assertRaisesRegex(T4Rejected,code): self.verdict(request,host)

    def test_future_synthetic_observation_yields_chronology_not_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            req,snap,host=receipt_fixture(Path(directory), future_observations=True)
            result=evaluate_p11(req,snap,**host)
            self.assertTrue(result.timestamp_before_observations)
            self.assertTrue(result.claimed_chronology_consistent)
            # Even cryptographically consistent order does not prove authentic
            # lab measurements, an enrolled external TSA or sealed challenge.
            self.assertFalse(result.independent_tsa_identity_verified)
            self.assertFalse(result.certificate_revocation_checked)

    def test_different_nonce_with_matching_digest_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            q=Path(directory)/'fresh.tsq'
            raw=self.fixture.p6.plan_lock.SerializeToString(deterministic=True)
            run(OPENSSL,'ts','-query','-digest',sha256(raw).hexdigest(),
                '-sha256','-cert','-out',str(q))
            changed=copy.deepcopy(self.fixture)
            changed.timestamp_query_der=q.read_bytes()
            self.rejected('TSA_RESPONSE_NONCE_OR_IMPRINT_MISMATCH',changed)

    def test_changed_stamped_plan(self):
        r=copy.deepcopy(self.fixture)
        r.p6.plan_lock.ed25519_signature=b'\x00'*64
        self.rejected('INVALID_ED25519_SIGNATURE',r)

    def test_tampered_timestamp_response(self):
        r=copy.deepcopy(self.fixture)
        t=bytearray(r.timestamp_response_der);t[-14]^=1
        r.timestamp_response_der=bytes(t)
        self.rejected('TSA_SIGNATURE_OR_CHAIN_INVALID|INVALID_TSA_DER_STRUCTURE',r)

    def test_unrelated_receipt_query_digest(self):
        r=copy.deepcopy(self.fixture)
        q=bytearray(r.timestamp_query_der)
        # Deliberately mutating query breaks request digest / response binding.
        q[-50]^=1
        r.timestamp_query_der=bytes(q)
        self.rejected('TSA_CHALLENGE_IMPRINT_MISMATCH|INVALID_TSA_DER_STRUCTURE',r)

    def test_revoked_or_unknown_policy(self):
        r=copy.deepcopy(self.fixture)
        r.expected_tsa_policy_oid='1.3.6.1.4.1.55555.22'
        self.rejected('TSA_POLICY_NOT_HOST_APPROVED',r)

    def test_host_certificate_pin_mismatch(self):
        host=dict(self.host,host_tsa_cert_sha256='0'*64)
        self.rejected('TSA_CERTIFICATE_PIN_MISMATCH',host=host)

    def test_host_ca_not_trusted(self):
        other=tempfile.TemporaryDirectory()
        try:
            p=Path(other.name)
            run(OPENSSL,'req','-x509','-newkey','rsa:2048','-nodes','-keyout',
                str(p/'other.key'),'-out',str(p/'other.pem'),'-days','1',
                '-subj','/CN=UNRELATED-CA')
            self.rejected('TSA_SIGNATURE_OR_CHAIN_INVALID',
                          host=dict(self.host,host_ca_pem=(p/'other.pem').read_bytes()))
        finally:other.cleanup()

    def test_no_authority(self):
        r=copy.deepcopy(self.fixture);r.grants_authority=True
        self.rejected('INVALID_P11_CONTRACT',r)


class P12MeasurementBoundaryTests(unittest.TestCase):
    def setUp(self):
        p10,_=make_dataset()
        self.req=w.T4P12UncertaintyRequest(schema_version=1,research_only=True,p10=p10)
        for specimen in ('s1','s2'):
            self.req.specimens.add(specimen_id=specimen,standard_uncertainty_m='0.1',
                coverage_factor='2',instrument_id='synthetic_instrument',
                calibrated_at_ms=1790000000000,observed_at_ms=1790000001000)

    def verify(self): return evaluate_p12(self.req,{'synthetic_fixture'})

    def test_consistent_intervals_and_partition(self):
        result=self.verify()
        self.assertEqual((result.rows_checked,result.calibration_rows,result.holdout_rows),
                         (2,1,1))
        self.assertFalse(result.real_instrument_calibration_verified)
        self.assertFalse(result.physical_safety_verified)

    def test_tampered_uncertainty_contradiction(self):
        self.req.specimens[1].standard_uncertainty_m='0.2'
        with self.assertRaisesRegex(T4Rejected,'UNCERTAINTY_LABEL_CONTRADICTION'):
            self.verify()

    def test_negative_uncertainty_rejected(self):
        self.req.specimens[0].standard_uncertainty_m='-0.1'
        with self.assertRaisesRegex(T4Rejected,'INVALID_UNCERTAINTY_NUMBER'):
            self.verify()

    def test_nan_uncertainty_rejected(self):
        self.req.specimens[0].standard_uncertainty_m='NaN'
        with self.assertRaisesRegex(T4Rejected,'INVALID_UNCERTAINTY_NUMBER'):
            self.verify()

    def test_missing_case(self):
        del self.req.specimens[-1]
        with self.assertRaisesRegex(T4Rejected,'P12_MISSING_UNCERTAINTY_SPECIMEN'):
            self.verify()

    def test_duplicate_case(self):
        self.req.specimens.add().CopyFrom(self.req.specimens[0])
        with self.assertRaisesRegex(T4Rejected,'P12_DUPLICATE_OR_INVALID_SPECIMEN'):
            self.verify()

    def test_fake_calibration_timestamp(self):
        self.req.specimens[0].calibrated_at_ms=1790000003000
        with self.assertRaisesRegex(T4Rejected,'CALIBRATION_TIME_NOT_BEFORE_MEASUREMENT'):
            self.verify()

    def test_host_license_denied(self):
        with self.assertRaisesRegex(T4Rejected,'LICENSE_NOT_APPROVED_BY_HOST'):
            evaluate_p12(self.req,set())

    def test_tampered_csv(self):
        self.req.p10.raw_csv+=b's3,g1,holdout,satisfies,1.0,cal1\n'
        with self.assertRaisesRegex(T4Rejected,'DATASET_HASH_MISMATCH'):
            self.verify()

    def test_invalid_permission(self):
        self.req.grants_authority=True
        with self.assertRaisesRegex(T4Rejected,'INVALID_P12_CONTRACT'):
            self.verify()


if __name__=='__main__':unittest.main()
