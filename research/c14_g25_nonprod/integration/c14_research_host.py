#!/usr/bin/env python3
"""Research-only C14 G25 local capability host; NO production or Lu registration.

Protocol: one JSON request per line, one JSON reply per line. The entrypoint
refuses to start without both an environment opt-in and --research-only flag.
Only trusted host supervisors should launch it; receipt hashes are NOT MACs.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from g25_release_guard import report

VERSION = 'C14-G25-research-transport-v1'
ACTION = 'c14.g25.sensitivity.report'
MAX_LINE = 1024 * 1024
MAX_OBSERVATIONS = 25000
MAX_SAMPLE = 1_000_000
MAX_REQUESTS = 10000
REQUEST_FIELDS = {'schema_version','request_id','action','counts','observations','gamma','assumption_evidence'}
RE_REQUEST_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$')


def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False)


def pairs_no_duplicates(pairs):
    out={}
    for k,v in pairs:
        if k in out:
            raise ValueError('duplicate_json_key')
        out[k]=v
    return out


def reject_constants(value):
    raise ValueError('invalid_json_constant')


def parse_request(raw):
    data=json.loads(raw, object_pairs_hook=pairs_no_duplicates, parse_constant=reject_constants)
    if not isinstance(data,dict) or set(data)-REQUEST_FIELDS:
        raise ValueError('invalid_request_object_or_fields')
    if type(data.get('schema_version')) is not int or data['schema_version']!=1:
        raise ValueError('unsupported_schema_version')
    ident=data.get('request_id')
    if not isinstance(ident,str) or not RE_REQUEST_ID.fullmatch(ident):
        raise ValueError('invalid_request_id')
    if data.get('action')!=ACTION:
        raise ValueError('unsupported_action')
    if ('counts' in data)==('observations' in data):
        raise ValueError('provide_exactly_one_input_mode')
    if 'gamma' not in data:
        raise ValueError('gamma_must_be_explicit')
    if 'assumption_evidence' not in data:
        raise ValueError('assumption_evidence_field_required')
    return data


def binary(x):
    return type(x) is int and x in (0,1)


def to_counts(obj):
    if 'counts' in obj:
        from g25_release_guard import strict_counts
        z=strict_counts(obj['counts'])
        if int(z.sum())>MAX_SAMPLE:
            raise ValueError('sample_exceeds_host_limit')
        return z
    rows=obj['observations']
    if not isinstance(rows,list) or not rows or len(rows)>MAX_OBSERVATIONS:
        raise ValueError('invalid_observations_length')
    import numpy as np
    z=np.zeros((2,2,2),dtype=np.int64)
    for row in rows:
        if not isinstance(row,dict) or set(row)!={'w','t','y'}:
            raise ValueError('observation_keys_must_be_w_t_y')
        w,t,y=(row['w'],row['t'],row['y'])
        if not all(binary(v) for v in (w,t,y)):
            raise ValueError('nonbinary_or_boolean_observation')
        z[w,t,y]+=1
    return z


def host_reply(host_status, request_id, source_hash, *, result=None, code=None):
    body={
       'schema_version':1, 'host_version':VERSION,
       'request_id':request_id, 'input_sha256':source_hash,
       'host_status':host_status,'research_only':True,
       'action':ACTION,'automatic_causal_certification':False,
       'production_estimator_promotion':False,
       'result':result, 'error_code':code
    }
    return {**body,'host_receipt_sha256':hashlib.sha256(canonical(body).encode()).hexdigest()}


def handle(raw, used_ids):
    inp_sha=hashlib.sha256(raw).hexdigest()
    ident=None
    try:
        data=parse_request(raw)
        ident=data['request_id']
        if ident in used_ids:
            raise ValueError('duplicate_request_id')
        used_ids.add(ident)
        z=to_counts(data)
        r=report(z,data['gamma'],data['assumption_evidence'])
        status='completed' if r['status']=='conditional_sensitivity_report_only' else 'refused'
        return host_reply(status,ident,inp_sha,result=r)
    except (ValueError, TypeError, OverflowError) as exc:
        # No raw request or stack trace is echoed; errors are precise and fail-closed.
        return host_reply('invalid_request',ident,inp_sha,code=str(exc)[:128])
    except Exception:
        # No numerical result on unexpected failure; the supervisor can fail closed.
        return host_reply('internal_failure',ident,inp_sha,code='research_worker_internal_error')


def main():
    parser=argparse.ArgumentParser(description='DISABLED-BY-DEFAULT C14 G25 research-only JSONL host')
    parser.add_argument('--research-only',action='store_true')
    args=parser.parse_args()
    if not args.research_only or os.environ.get('COGNITUM_G25_RESEARCH_OPT_IN')!='1':
        print('research host disabled: requires explicit flag and environment opt-in',file=sys.stderr)
        return 78
    used_ids=set()
    for _ in range(MAX_REQUESTS):
        raw=sys.stdin.buffer.readline(MAX_LINE+1)
        if not raw:
            break
        if len(raw)>MAX_LINE:
            # Abort stream rather than trying to drain an unbounded attacker line.
            reply=host_reply('invalid_request',None,hashlib.sha256(raw).hexdigest(),code='line_too_large_stream_closed')
            sys.stdout.write(canonical(reply)+'\n')
            sys.stdout.flush()
            return 65
        if not raw.strip():
            reply=host_reply('invalid_request',None,hashlib.sha256(raw).hexdigest(),code='blank_request')
        else:
            reply=handle(raw.rstrip(b'\r\n'),used_ids)
        sys.stdout.write(canonical(reply)+'\n')
        sys.stdout.flush()
    else:
        return 69
    return 0

if __name__=='__main__':
    raise SystemExit(main())
