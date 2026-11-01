"""One Cognitum distribution, three independent research-grade specialists.

Installed together with the core, never loaded into Lu. Registry admission,
research opt-in and per-call authorization are still required. This adapter
uses the existing Cognitum Phase-0 Shape/Manifest and disposable worker model.
"""
from __future__ import annotations
import base64
import binascii
import hashlib
import json
import os
import re
from cognitum.contracts import Manifest, Operation, Shape

HEX = re.compile(r'[a-f0-9]{64}\Z', re.ASCII)


def _no_duplicate_keys(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError('DUPLICATE_JSON_KEY')
    return result


def _b64(raw: str, limit: int) -> bytes:
    if type(raw) is not str or not 1 <= len(raw) <= (limit + 2) // 3 * 4:
        raise ValueError('INVALID_BASE64_SIZE')
    try:
        result = base64.b64decode(raw, validate=True)
    except (binascii.Error,ValueError) as exc:
        raise ValueError('INVALID_BASE64') from exc
    if len(result) < 1 or len(result) > limit or base64.b64encode(result).decode('ascii') != raw:
        raise ValueError('NONCANONICAL_OR_OVERSIZE_BASE64')
    return result


class Specialists:
    """All three engines share the existing one-package Cognitum registry."""
    def manifest(self):
        result = Shape((('result_json', 15000),('status', 40),('limitations', 256)))
        return Manifest(
            'cognitum_specialists', '0.1.0', (
                Operation('specialist.hdc', 'hdc', Shape((('frame_b64', 24000),)), result,
                          assurance='heuristic', outcome_kind='candidate_set'),
                Operation('specialist.kan', 'kan', Shape((('frame_b64', 12000),('checkpoint_b64', 190000))), result,
                          assurance='numerical', outcome_kind='approximation'),
                Operation('specialist.ssm', 'ssm', Shape((('request_json', 24000),)), result,
                          assurance='numerical', outcome_kind='state_sequence'),
            ), track='research', maturity='prototype',
        )

    def health(self):
        try:
            import numpy
            import google.protobuf
        except ImportError:
            return False
        return True

    def self_test(self):
        from cognitum.specialists.ssm import scan_request
        req={'parameters':{'a':[0.5],'b':[[1]],'c':[[1]],'d':[[0]]},
             'inputs':[[2],[2]],'initial_state':None}
        return scan_request(req)['outputs'] == [[2.0],[3.0]]

    @staticmethod
    def _result(value, status, limitations):
        text = json.dumps(value, sort_keys=True, separators=(',',':'),allow_nan=False)
        if len(text)>15000:
            raise ValueError('RESULT_SIZE_LIMIT')
        return {'result_json':text, 'status':status, 'limitations':limitations}

    def handle(self, operation, payload):
        if operation == 'specialist.hdc':
            from cognitum.research.hdc_optional import query
            raw = _b64(payload['frame_b64'], 16384)
            output = query(raw)
            return self._result({'protobuf_b64':base64.b64encode(output).decode('ascii')},
                'candidates_only', 'HDC_BINARY_BINDING_NOT_AUTHORIZED_MEMORY_OR_CITATION')
        if operation == 'specialist.kan':
            from cognitum.research.kan_optional import predict, ResearchPolicy
            request = _b64(payload['frame_b64'],8192)
            checkpoint = _b64(payload['checkpoint_b64'],131072)
            # Host-owned approval: the request cannot grant trust to itself.
            trusted_sha = os.environ.get('COGNITUM_TRUSTED_KAN_SHA256','')
            if not HEX.fullmatch(trusted_sha) or hashlib.sha256(checkpoint).hexdigest() != trusted_sha:
                raise PermissionError('KAN_HOST_CHECKPOINT_APPROVAL_REQUIRED')
            out = predict(request, checkpoint, ResearchPolicy(True, trusted_sha))
            return self._result({'protobuf_b64':base64.b64encode(out).decode('ascii')},
                'approximate', 'KAN_CPU_REFERENCE_NO_PRODUCTION_CALIBRATION')
        if operation == 'specialist.ssm':
            from cognitum.specialists.ssm import scan_request
            raw = payload['request_json']
            if type(raw) is not str or len(raw)>24000:
                raise ValueError('INVALID_SSM_REQUEST_SIZE')
            try:
                obj=json.loads(raw, object_pairs_hook=_no_duplicate_keys,
                    parse_constant=lambda x: (_ for _ in ()).throw(ValueError('NONFINITE_JSON')))
            except (ValueError,TypeError) as exc:
                raise ValueError('INVALID_SSM_JSON') from exc
            result=scan_request(obj)
            return self._result(result,'state_sequence_only',result['limitation'])
        raise ValueError('UNKNOWN_SPECIALIST_OPERATION')
