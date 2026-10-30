"""Synthetic signature fixtures; not independent real-world publisher evidence."""
import hashlib
import unittest
try:
    import numpy  # noqa: F401
    import cryptography  # noqa: F401
except ModuleNotFoundError as exc:
    raise unittest.SkipTest('C09 signed research requires optional NumPy and cryptography') from exc
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from cognitum.proto.kan_approval_pb2 import KanCheckpointApproval
from cognitum.proto.research_optional_pb2 import KanPrediction, KanRequest
from cognitum.research.kan_approval import HostTrustedApprover, predict_approved, _statement
from cognitum.research.kan_optional import ResearchPolicy
from tests.test_research_optional import kan_artifact

class SignedKanGate(unittest.TestCase):
    def setUp(self):
        self.key=Ed25519PrivateKey.generate()
        pub=self.key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
        self.data=kan_artifact();self.digest=hashlib.sha256(self.data).hexdigest()
        self.split='a'*64
        self.trust=HostTrustedApprover('research-signer',pub,'kan-model-1',self.split)
        self.policy=ResearchPolicy(True,self.digest)
        self.req=KanRequest(schema_version=1,feature_values=['0'],checkpoint_sha256=self.digest).SerializeToString(deterministic=True)
        self.approval=KanCheckpointApproval(schema_version=1,signer_id='research-signer',model_id='kan-model-1',checkpoint_sha256=self.digest,training_split_sha256=self.split,feature_units=['unitless'])

    def sign(self,approval=None,key=None):
        msg=KanCheckpointApproval();msg.CopyFrom(self.approval if approval is None else approval)
        msg.signature=(self.key if key is None else key).sign(_statement(msg))
        return msg.SerializeToString(deterministic=True)
    def infer(self,w=None,trust=None,policy=None,checkpoint=None,request=None):
        return predict_approved(self.req if request is None else request,
                self.data if checkpoint is None else checkpoint,
                self.policy if policy is None else policy,
                self.sign() if w is None else w,
                self.trust if trust is None else trust)
    def test_signed_reference_inference(self):
        v=KanPrediction.FromString(self.infer())
        self.assertEqual(v.checkpoint_sha256,self.digest)
        self.assertFalse(v.grants_authority or v.uncertainty_calibrated)
    def test_signature_tamper(self):
        m=KanCheckpointApproval.FromString(self.sign());m.feature_units[0]='meter'
        with self.assertRaisesRegex(PermissionError,'SIGNATURE_INVALID'):self.infer(w=m.SerializeToString(deterministic=True))
    def test_wrong_key(self):
        with self.assertRaisesRegex(PermissionError,'SIGNATURE_INVALID'):
            self.infer(w=self.sign(key=Ed25519PrivateKey.generate()))
    def test_wrong_signer(self):
        m=KanCheckpointApproval.FromString(self.sign());m.signer_id='unknown'
        with self.assertRaisesRegex(PermissionError,'IDENTITY_OR_SPLIT'):self.infer(w=m.SerializeToString(deterministic=True))
    def test_revoked(self):
        t=HostTrustedApprover(self.trust.signer_id,self.trust.public_key,self.trust.model_id,self.split,True)
        with self.assertRaisesRegex(PermissionError,'REVOKED'):self.infer(trust=t)
    def test_inert_by_default(self):
        with self.assertRaisesRegex(PermissionError,'DEFAULT_DISABLED'):self.infer(policy=ResearchPolicy())
    def test_wrong_split_hash_even_if_signed(self):
        m=KanCheckpointApproval.FromString(self.approval.SerializeToString());m.training_split_sha256='b'*64
        with self.assertRaisesRegex(PermissionError,'IDENTITY_OR_SPLIT'):self.infer(w=self.sign(m))
    def test_wrong_checkpoint_even_if_validly_signed(self):
        m=KanCheckpointApproval.FromString(self.approval.SerializeToString());m.checkpoint_sha256='0'*64
        with self.assertRaisesRegex(ValueError,'DIGEST_MISMATCH'):self.infer(w=self.sign(m))
    def test_unknown_fields(self):
        with self.assertRaisesRegex(ValueError,'NONCANONICAL'):self.infer(w=self.sign()+b'\x98\x06\x01')
    def test_invalid_feature_units(self):
        m=KanCheckpointApproval.FromString(self.approval.SerializeToString());m.feature_units[0]='bad unit'
        with self.assertRaisesRegex(ValueError,'METADATA'):self.infer(w=self.sign(m))
    def test_wrong_width(self):
        m=KanCheckpointApproval.FromString(self.approval.SerializeToString());m.feature_units.extend(['meter'])
        with self.assertRaisesRegex(ValueError,'WIDTH_MISMATCH'):self.infer(w=self.sign(m))
    def test_bad_feature_request_under_approved_manifest(self):
        req=KanRequest.FromString(self.req);req.feature_values[0]='200'
        with self.assertRaisesRegex(ValueError,'OUT_OF_DISTRIBUTION'):
            self.infer(request=req.SerializeToString(deterministic=True))

if __name__=='__main__':unittest.main()
