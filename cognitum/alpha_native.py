"""Cognitum alpha *standalone* process boundary: native Protobuf, default deny.

The admission object MUST originate in a future authenticated Lu supervisor; an
ordinary Python caller can construct it, so it grants NO independent authority.
This is a separately killable trusted subprocess, NOT a hardened OS sandbox.
"""
from __future__ import annotations
from dataclasses import dataclass
import re
import struct
import subprocess
import sys

from google.protobuf.message import DecodeError
from .proto import alpha_native_pb2 as proto
from .protobuf_codec import (RATIONAL_REQUEST_TYPE, RATIONAL_RESULT_TYPE,
                              decode_rational_request, decode_success)
from .plugins.calculator import calculate

MAX_FRAME = 16384
MAX_REPLY = 16384
MAX_TIME_MS = 7500
ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,79}\Z', re.ASCII)
ALLOWED = {'calc.rational': RATIONAL_REQUEST_TYPE}

@dataclass(frozen=True, slots=True)
class HostAdmission:
    # Only a trusted embedding host should be able to set these; no wire grant.
    conversation_id: str = ''
    request_id: str = ''
    operations: frozenset[str] = frozenset()
    enabled: bool = False
    timeout_ms: int = 1000

    def __post_init__(self):
        if (type(self.enabled) is not bool or type(self.operations) is not frozenset
            or type(self.timeout_ms) is not int or not 1 <= self.timeout_ms <= MAX_TIME_MS
            or any(type(x) is not str for x in self.operations)):
            raise ValueError('INVALID_HOST_ADMISSION')


def _parse(cls, wire: bytes, limit: int):
    if type(wire) is not bytes or not 0 < len(wire) <= limit:
        raise ValueError('INVALID_FRAME_SIZE')
    obj = cls()
    try:
        obj.ParseFromString(wire)
    except DecodeError as exc:
        raise ValueError('INVALID_PROTOBUF') from exc
    known = cls(); known.CopyFrom(obj); known.DiscardUnknownFields()
    if known != obj or obj.SerializeToString(deterministic=True) != wire:
        raise ValueError('NONCANONICAL_OR_UNKNOWN_PROTOBUF')
    return obj


def make_call(request_id: str, expression: str) -> bytes:
    from .protobuf_codec import encode_rational_request
    if not ID.fullmatch(request_id):
        raise ValueError('INVALID_REQUEST_ID')
    inner = encode_rational_request(expression)
    call = proto.Call(version=1, request_id=request_id, operation='calc.rational',
                      request_type_url=inner.type_url, request_payload=inner.payload)
    wire = call.SerializeToString(deterministic=True)
    if len(wire) > MAX_FRAME:
        raise ValueError('FRAME_TOO_LARGE')
    return wire


def run_once(call_wire: bytes, admission: HostAdmission) -> bytes:
    if type(admission) is not HostAdmission:
        raise ValueError('HOST_ADMISSION_REQUIRED')
    if (not admission.enabled or not ID.fullmatch(admission.conversation_id)
        or not ID.fullmatch(admission.request_id)):
        raise PermissionError('HOST_NOT_ADMITTED')
    request = _parse(proto.Call, call_wire, MAX_FRAME)
    if not ID.fullmatch(request.request_id) or request.request_id != admission.request_id:
        raise PermissionError('REQUEST_ID_MISMATCH')
    if request.version != 1 or request.operation not in ALLOWED:
        raise ValueError('UNSUPPORTED_CALL')
    if request.operation not in admission.operations:
        raise PermissionError('OPERATION_NOT_ADMITTED')
    if request.request_type_url != ALLOWED[request.operation]:
        raise ValueError('TYPE_URL_MISMATCH')
    expression = decode_rational_request(request.request_type_url, request.request_payload)
    expected_result = calculate(expression)  # bound parser/admission preflight, before child launch
    # No user-controlled executable, command, filesystem path or environment variable.
    try:
        child = subprocess.run([sys.executable, '-m', 'cognitum.alpha_native_worker'],
                               input=struct.pack('>I', len(call_wire)) + call_wire,
                               capture_output=True, timeout=admission.timeout_ms / 1000,
                               check=False)
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError('ALPHA_WORKER_TIMEOUT') from exc
    if child.returncode or child.stderr or len(child.stdout) < 4 or len(child.stdout) > MAX_REPLY+4:
        raise ValueError('ALPHA_WORKER_FAILED')
    length = struct.unpack('>I', child.stdout[:4])[0]
    if not length or length > MAX_REPLY or len(child.stdout) != length + 4:
        raise ValueError('ALPHA_WORKER_FRAME_MISMATCH')
    answer = _parse(proto.Reply, child.stdout[4:], MAX_REPLY)
    if (answer.version != 1 or answer.request_id != request.request_id
        or answer.lu_integrated or answer.os_isolation_verified):
        raise ValueError('ALPHA_WORKER_FORGED_ASSURANCE_OR_ID')
    if answer.status != proto.Reply.COMPLETED or answer.error_code:
        raise ValueError('ALPHA_WORKER_DID_NOT_COMPLETE')
    if answer.result_type_url != RATIONAL_RESULT_TYPE:
        raise ValueError('ALPHA_WORKER_RESULT_TYPE_MISMATCH')
    parsed = decode_success('calc.rational', answer.result_type_url, answer.result_payload,
                            request_id=request.request_id, correlation_id=admission.conversation_id)
    if parsed.value.value != expected_result:
        raise ValueError('WORKER_RESULT_DISAGREES_WITH_VERIFIER')
    return child.stdout[4:]
