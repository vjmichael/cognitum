"""C15 T4 P11/P12 offline, research-only acceptance *mechanisms*.

P11 checks an RFC 3161 request/response against a host-pinned TSA certificate,
root CA and original P6 signed plan-lock bytes using OpenSSL and ASN.1.
Locally manufactured certificates are NOT independently authenticated TSAs;
revocation, challenge issuance custody, legal identity and public registration
remain separate real-world acceptance gates.

P12 checks bounded uncertainty/label consistency over P10-staged CSV. Neither
numeric consistency nor document hashing authenticates physical measurements.
No network access, no model authority, no Lu mutation, no host key enrollment.
"""
from __future__ import annotations

import csv
from datetime import timezone
from decimal import Decimal, InvalidOperation
import hashlib
import io
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Collection, Mapping

from asn1crypto import tsp, x509 as asn1x509
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.x509.oid import ExtendedKeyUsageOID, ExtensionOID

from cognitum.proto import spatial_functional_material_p11_p12_pb2 as wire
from cognitum.spatial_functional_material import T4Rejected, _ident, _no_unknown
from cognitum.spatial_functional_material_p5_p7 import base_contract, ensure, strict_time
from cognitum.spatial_functional_material_p8_p10 import (
    PolicySnapshot, _lock, evaluate_p10, CSV_FIELDS,
)
from cognitum.spatial_functional_material_p4 import _parse

_OID = re.compile(r'(?:[0-2])(?:\.[0-9]+){2,15}\Z')


def _parse_receipt(req: wire.T4P11Rfc3161Request, stamped: bytes,
                   pinned_cert_der: bytes, host_policy_oids: Collection[str]):
    """No signature verdict here: OpenSSL certificate path validation follows."""
    try:
        query = tsp.TimeStampReq.load(req.timestamp_query_der, strict=True)
        response = tsp.TimeStampResp.load(req.timestamp_response_der, strict=True)
        ensure(query.dump()==req.timestamp_query_der and
               response.dump()==req.timestamp_response_der, 'NONCANONICAL_TSA_DER')
        q = query.native
        ensure(q['version']=='v1' and q['message_imprint']['hash_algorithm']['algorithm']=='sha256' and
               q['message_imprint']['hashed_message']==hashlib.sha256(stamped).digest(),
               'TSA_CHALLENGE_IMPRINT_MISMATCH')
        ensure(type(q['nonce']) is int and q['nonce']>0 and q['cert_req'] is True,
               'TSA_CHALLENGE_NONCE_OR_CERT_MISSING')
        ensure(response['status'].native['status'] in ('granted','granted_with_mods'),
               'TSA_RESPONSE_NOT_GRANTED')
        token=response['time_stamp_token']
        ensure(token['content_type'].native=='signed_data', 'TSA_NOT_SIGNED_DATA')
        signed=token['content']
        ensure(signed['encap_content_info']['content_type'].native=='tst_info' and
               len(signed['signer_infos'])==1, 'TSA_INVALID_SIGNED_CONTENT')
        info=signed['encap_content_info']['content'].native
        ensure(info['version']=='v1' and
               info['message_imprint']['hash_algorithm']['algorithm']=='sha256' and
               info['message_imprint']['hashed_message']==q['message_imprint']['hashed_message'] and
               info['nonce']==q['nonce'], 'TSA_RESPONSE_NONCE_OR_IMPRINT_MISMATCH')
        oid=info['policy']
        ensure(oid==req.expected_tsa_policy_oid and oid in host_policy_oids and
               (q['req_policy'] is None or q['req_policy']==oid),
               'TSA_POLICY_NOT_HOST_APPROVED')
        # RFC 3161 ESS signer identity is checked again by OpenSSL ts -verify.
        # Pin the *actual* signer certificate in the signed CMS, not merely
        # any unrelated host-listed certificate whose chain verifies.
        signer=asn1x509.Certificate.load(pinned_cert_der)
        sid=signed['signer_infos'][0]['sid']
        ensure(sid.name=='issuer_and_serial_number' and
               sid.chosen['serial_number'].native==signer.serial_number and
               sid.chosen['issuer'].dump()==signer.issuer.dump(),
               'TSA_SIGNER_CERTIFICATE_MISMATCH')
        ensure(any(c.name=='certificate' and c.chosen.dump()==pinned_cert_der
                   for c in signed['certificates']), 'TSA_SIGNER_CERTIFICATE_MISSING')
        generated=info['gen_time']
        ensure(generated.tzinfo is not None, 'TSA_INVALID_GENERATION_TIME')
        timestamp_ms=int(generated.astimezone(timezone.utc).timestamp()*1000)
        strict_time(timestamp_ms)
        return oid,timestamp_ms
    except T4Rejected:
        raise
    except (TypeError,ValueError,KeyError,IndexError,AttributeError,OverflowError) as exc:
        raise T4Rejected('INVALID_TSA_DER_STRUCTURE') from exc


def evaluate_p11(req: wire.T4P11Rfc3161Request, snapshot: PolicySnapshot,
                 *, host_ca_pem: bytes, host_tsa_cert_pem: bytes,
                 host_tsa_cert_sha256: str, host_policy_oids: Collection[str],
                 openssl_executable: str) -> wire.T4P11Rfc3161Result:
    """Offline verification; host provides trust roots, binary path and policy.

    The calling trusted host must have generated, retained, and correlated the
    original nonce query; this function cannot prove the query's origin.
    No certificate revocation checks are implemented. One trust certificate
    per accepted CA bundle is recommended by the host, never by a model.
    """
    base_contract(req,wire.T4P11Rfc3161Request,'P11')
    ensure(req.HasField('p6') and isinstance(snapshot,PolicySnapshot),
           'P11_CONTEXT_MISSING')
    ensure(0<len(req.timestamp_query_der)<=8192 and
           0<len(req.timestamp_response_der)<=131072 and
           type(host_ca_pem) is bytes and 0<len(host_ca_pem)<=32768 and
           type(host_tsa_cert_pem) is bytes and 0<len(host_tsa_cert_pem)<=16384 and
           type(host_tsa_cert_sha256) is str and
           re.fullmatch('[0-9a-f]{64}',host_tsa_cert_sha256) is not None and
           type(host_policy_oids) in (set,frozenset,tuple,list) and
           type(openssl_executable) is str and Path(openssl_executable).is_file() and
           _OID.fullmatch(req.expected_tsa_policy_oid) is not None,
           'P11_INVALID_TRUST_CONFIGURATION')
    _,sources,lock_time=_lock(req.p6,snapshot.signers)
    try:
        tsa=x509.load_pem_x509_certificate(host_tsa_cert_pem)
        cert_der=tsa.public_bytes(serialization.Encoding.DER)
        ensure(hashlib.sha256(cert_der).hexdigest()==host_tsa_cert_sha256,
               'TSA_CERTIFICATE_PIN_MISMATCH')
        eku=tsa.extensions.get_extension_for_oid(ExtensionOID.EXTENDED_KEY_USAGE)
        ensure(eku.critical and list(eku.value)==[ExtendedKeyUsageOID.TIME_STAMPING],
               'TSA_CERTIFICATE_EKU_INVALID')
    except T4Rejected:
        raise
    except (ValueError,x509.ExtensionNotFound) as exc:
        raise T4Rejected('TSA_CERTIFICATE_INVALID') from exc
    stamped=req.p6.plan_lock.SerializeToString(deterministic=True)
    policy,gen_ms=_parse_receipt(req,stamped,cert_der,host_policy_oids)
    with tempfile.TemporaryDirectory(prefix='cognitum-p11-') as directory:
        d=Path(directory)
        for name,value in [('query.tsq',req.timestamp_query_der),
                           ('reply.tsr',req.timestamp_response_der),
                           ('ca.pem',host_ca_pem),('tsa.pem',host_tsa_cert_pem)]:
            (d/name).write_bytes(value)
        try:
            proc=subprocess.run([
                openssl_executable,'ts','-verify','-queryfile',str(d/'query.tsq'),
                '-in',str(d/'reply.tsr'),'-CAfile',str(d/'ca.pem'),
                '-untrusted',str(d/'tsa.pem')],capture_output=True,timeout=12,
                shell=False,check=False,env={**os.environ,'OPENSSL_CONF':os.devnull})
        except (OSError,subprocess.TimeoutExpired) as exc:
            raise T4Rejected('TSA_VERIFIER_EXECUTION_FAILURE') from exc
        ensure(proc.returncode==0 and b'Verification: OK' in proc.stdout+proc.stderr,
               'TSA_SIGNATURE_OR_CHAIN_INVALID')
    before=lock_time<=gen_ms<min(t for _,t in sources.values())
    return wire.T4P11Rfc3161Result(
        receipt_chain_signature_verified=True,requested_nonce_and_imprint_verified=True,
        signer_certificate_host_pinned=True,timestamp_before_observations=before,
        claimed_chronology_consistent=before, independent_tsa_identity_verified=False,
        certificate_revocation_checked=False,gen_time_ms=gen_ms,
        timestamp_policy_oid=policy,research_only=True,grants_authority=False,
        warnings=['HOST_MUST_PROVE_NONCE_CHALLENGE_CUSTODY_AND_FRESHNESS',
                  'CERTIFICATE_PINNING_DOES_NOT_AUTHENTICATE_REAL_TSA_IDENTITY',
                  'NO_CRL_OR_OCSP_CERTIFICATE_REVOCATION_VERIFICATION',
                  'SIGNED_TIMESTAMPS_CANNOT_AUTHENTICATE_REAL_WORLD_OBSERVATIONS',
                  'NO_LU_OR_PHYSICAL_ACTION_AUTHORITY'])


def _bounded_decimal(value: str, *, minimum: Decimal, maximum: Decimal) -> Decimal:
    ensure(type(value) is str and 1<=len(value)<=32 and value.strip()==value and
           re.fullmatch(r'(?:0|[1-9][0-9]*)(?:\.[0-9]{1,12})?',value) is not None,
           'INVALID_UNCERTAINTY_NUMBER')
    try:
        d=Decimal(value)
    except InvalidOperation as exc:
        raise T4Rejected('INVALID_UNCERTAINTY_NUMBER') from exc
    ensure(d.is_finite() and minimum<=d<=maximum,'INVALID_UNCERTAINTY_RANGE')
    return d


def evaluate_p12(req: wire.T4P12UncertaintyRequest,
                 host_allowed_license_ids: Collection[str]) -> wire.T4P12UncertaintyResult:
    """Measurement-label boundary audit; does not certify source or safety."""
    base_contract(req,wire.T4P12UncertaintyRequest,'P12')
    ensure(req.HasField('p10') and 1<=len(req.specimens)<=160,
           'P12_CONTEXT_MISSING')
    staged=evaluate_p10(req.p10,host_allowed_license_ids)
    rows=list(csv.DictReader(io.StringIO(req.p10.raw_csv.decode('utf-8'))))
    ensure(tuple(rows[0])==CSV_FIELDS, 'P12_SCHEMA_MISMATCH')
    specimens={}
    for point in req.specimens:
        ensure(_no_unknown(point) and _ident(point.specimen_id) and
               _ident(point.instrument_id) and point.specimen_id not in specimens,
               'P12_DUPLICATE_OR_INVALID_SPECIMEN')
        u=_bounded_decimal(point.standard_uncertainty_m,minimum=Decimal('0'),
                           maximum=Decimal('1000000'))
        k=_bounded_decimal(point.coverage_factor,minimum=Decimal('1'),
                           maximum=Decimal('3'))
        strict_time(point.calibrated_at_ms)
        strict_time(point.observed_at_ms)
        ensure(point.calibrated_at_ms<point.observed_at_ms,
               'CALIBRATION_TIME_NOT_BEFORE_MEASUREMENT')
        specimens[point.specimen_id]=(u,k)
    ensure(len(rows)==len(specimens)==staged.rows_validated and
           {r['specimen_id'] for r in rows}==set(specimens),
           'P12_MISSING_UNCERTAINTY_SPECIMEN')
    counts={'calibration':0,'holdout':0}; uncertain=0
    for row in rows:
        counts[row['partition']]+=1
        u,k=specimens[row['specimen_id']]
        value=Decimal(row['measured_clearance_m'])
        lower=value-k*u; upper=value+k*u
        label='satisfies' if lower>0 else ('violates' if upper<0 else 'undetermined')
        ensure(label==row['observed_class'], 'UNCERTAINTY_LABEL_CONTRADICTION')
        uncertain+=label=='undetermined'
    ensure(counts['calibration']>=1 and counts['holdout']>=1,
           'P12_MISSING_HOLDOUT_OR_CALIBRATION')
    return wire.T4P12UncertaintyResult(
        rows_checked=len(rows),calibration_rows=counts['calibration'],
        holdout_rows=counts['holdout'],undetermined_rows=uncertain,
        uncertainty_label_consistency_verified=True,
        real_instrument_calibration_verified=False,physical_safety_verified=False,
        research_only=True,grants_authority=False,
        warnings=['UNCERTAINTY_IS_USER_SUPPLIED_AND_NOT_INSTRUMENT_AUTHENTICATED',
                  'NO_INDEPENDENT_CALIBRATION_CERTIFICATE_OR_SAFETY_VALIDATION',
                  'MEASUREMENT_CONSISTENCY_DOES_NOT_VERIFY_EXTERNAL_DATA_LICENSE',
                  'NO_LU_OR_PHYSICAL_ACTION_AUTHORITY'])
