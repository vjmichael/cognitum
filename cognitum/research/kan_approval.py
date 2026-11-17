"""C09 P2 signed metadata gate for optional portable KAN research.

A locally trusted Ed25519 key attests the supplied metadata *claim*, not real
publisher identity, source licenses, model accuracy, calibrated uncertainty,
OS isolation, persistent revocation or permission. Do not let a model select
trusted keys or enable ResearchPolicy.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import re
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from google.protobuf.message import DecodeError
from cognitum.proto.kan_approval_pb2 import KanCheckpointApproval
from cognitum.proto.research_optional_pb2 import KanRequest
from .kan_optional import ResearchPolicy, predict

DOMAIN = b'COGNITUM-C09-KAN-CHECKPOINT-APPROVAL-V1\x00'
ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,79}\Z', re.ASCII)
HEX = re.compile(r'[0-9a-f]{64}\Z', re.ASCII)
UNIT = re.compile(r'[A-Za-z][A-Za-z0-9_/*.-]{0,31}\Z', re.ASCII)
MAX_MANIFEST = 4096

@dataclass(frozen=True, slots=True)
class HostTrustedApprover:
    signer_id: str
    public_key: bytes
    model_id: str
    training_split_sha256: str
    revoked: bool = False

    def __post_init__(self):
        if (not ID.fullmatch(self.signer_id) or not ID.fullmatch(self.model_id)
            or type(self.public_key) is not bytes or len(self.public_key) != 32
            or not HEX.fullmatch(self.training_split_sha256)
            or type(self.revoked) is not bool):
            raise ValueError('INVALID_TRUSTED_APPROVER')


def _parse(raw: bytes) -> KanCheckpointApproval:
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_MANIFEST:
        raise ValueError('INVALID_APPROVAL_FRAME')
    msg = KanCheckpointApproval()
    try: msg.ParseFromString(raw)
    except DecodeError as exc: raise ValueError('MALFORMED_APPROVAL') from exc
    copy = KanCheckpointApproval(); copy.CopyFrom(msg); copy.DiscardUnknownFields()
    if copy != msg or msg.SerializeToString(deterministic=True) != raw:
        raise ValueError('NONCANONICAL_APPROVAL')
    if (msg.schema_version != 1 or not ID.fullmatch(msg.signer_id)
        or not ID.fullmatch(msg.model_id) or not HEX.fullmatch(msg.checkpoint_sha256)
        or not HEX.fullmatch(msg.training_split_sha256)
        or not 1 <= len(msg.feature_units) <= 8
        or any(not UNIT.fullmatch(unit) for unit in msg.feature_units)
        or len(msg.signature) != 64):
        raise ValueError('INVALID_APPROVAL_METADATA')
    return msg


def _statement(msg: KanCheckpointApproval) -> bytes:
    checked = KanCheckpointApproval(); checked.CopyFrom(msg)
    checked.ClearField('signature')
    return DOMAIN + checked.SerializeToString(deterministic=True)


def predict_approved(request: bytes, checkpoint: bytes, policy: ResearchPolicy,
                     approval_wire: bytes, trust: HostTrustedApprover) -> bytes:
    if type(trust) is not HostTrustedApprover or trust.revoked:
        raise PermissionError('TRUST_ROOT_UNAVAILABLE_OR_REVOKED')
    if type(policy) is not ResearchPolicy or not policy.research_enabled:
        raise PermissionError('RESEARCH_DEFAULT_DISABLED')
    approval = _parse(approval_wire)
    if (approval.signer_id != trust.signer_id or approval.model_id != trust.model_id
        or approval.training_split_sha256 != trust.training_split_sha256):
        raise PermissionError('UNTRUSTED_APPROVAL_IDENTITY_OR_SPLIT')
    if (type(checkpoint) is not bytes or hashlib.sha256(checkpoint).hexdigest() != approval.checkpoint_sha256
        or policy.expected_checkpoint_sha256 != approval.checkpoint_sha256):
        raise ValueError('CHECKPOINT_APPROVAL_DIGEST_MISMATCH')
    req = KanRequest()
    try: req.ParseFromString(request)
    except DecodeError as exc: raise ValueError('INVALID_KAN_REQUEST') from exc
    if len(approval.feature_units) != len(req.feature_values):
        raise ValueError('APPROVED_FEATURE_WIDTH_MISMATCH')
    try: Ed25519PublicKey.from_public_bytes(trust.public_key).verify(approval.signature,_statement(approval))
    except (InvalidSignature,ValueError) as exc: raise PermissionError('APPROVAL_SIGNATURE_INVALID') from exc
    # The existing predictor validates the actual typed request, pin, bounds and checkpoint members.
    return predict(request,checkpoint,policy)
