"""BENCH-02 R3-R1 bounded real NOAA capture and independently replayable receipts.

This is a pre-registered research source, not signed historical availability.
No fitted model, no source window replacement, and no production admission.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import ssl
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, HTTPSHandler, HTTPRedirectHandler, build_opener

from tools.orcbench02.cohorts import Refusal, build_site, canonical, lock, require

STUDY_PROTOCOL_SHA = 'fd0b6a372ee5cd9ee8870ad20c475261460a069daf4fd52f56e8dcc2961a5104'
SCHEMA = 'cognitum.orc.bench02.r3.acquisition.v1'

class RejectRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Refusal('redirect refused for fixed NOAA origin')


def write_once(path: Path, payload: bytes):
    require(not path.is_symlink(), 'symlink evidence target')
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, 'O_NOFOLLOW'):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, 'wb') as dst:
        dst.write(payload)
        dst.flush()
        os.fsync(dst.fileno())


def fixed_url(site):
    spec, pin = lock()
    require(pin == STUDY_PROTOCOL_SHA, 'preregistered source changed')
    require(site in spec['independent_stations_in_fixed_order'], 'nonpreregistered observation site')
    return spec['source_url_template'].replace('{ICAO}', site)


def download_one(site, *, opener=None, clock=None):
    spec, pin = lock()
    require(pin == STUDY_PROTOCOL_SHA, 'protocol digest mismatch')
    url = fixed_url(site)
    opener = opener or build_opener(HTTPSHandler(context=ssl.create_default_context()),
                                     RejectRedirect())
    clock = clock or (lambda: time.time_ns() // 1_000_000)
    start_ms = clock()
    request = Request(url, method='GET', headers={
        'User-Agent': 'Cognitum-BENCH02-R3/1.0 (github.com/vjmichael/cognitum)',
        'Accept': 'application/json', 'Cache-Control': 'no-cache'})
    try:
        with opener.open(request, timeout=25) as response:
            require(response.status == 200, 'NOAA response status is not 200')
            content_type = response.headers.get('Content-Type', '')
            require('application/json' in content_type.lower(), 'NOAA source MIME not JSON')
            raw = response.read(spec['maximum_json_bytes_per_station'] + 1)
            server_date = response.headers.get('Date', '')
    except (HTTPError, URLError, TimeoutError, OSError) as ex:
        raise Refusal('NOAA HTTPS request not authenticated/available') from ex
    complete_ms = clock()
    require(type(start_ms) is int and type(complete_ms) is int and
            0 < start_ms <= complete_ms, 'invalid capture clock')
    digest = sha256(raw).hexdigest()
    cohort = build_site(raw, site, capture_start_ms=start_ms,
                        capture_end_ms=complete_ms, sha256_pin=digest)
    require(cohort['preregistered_protocol_sha256'] == pin, 'wrong study protocol')
    receipt = {
        'schema': SCHEMA, 'station': site, 'source_url': url,
        'source_sha256': digest, 'source_bytes': len(raw),
        'capture_started_ms': start_ms, 'capture_completed_ms': complete_ms,
        'provider_http_date': server_date, 'provider_content_type': content_type,
        'https': 'SYSTEM_CA_PINNED_DOMAIN_NO_REDIRECT',
        'preregistration_sha256': pin,
        'cohort_sha256': sha256(canonical(cohort)).hexdigest(),
        'source_rows': cohort['original_source_rows'],
        'fixed_window_exclusive_end_ms': cohort['source_clock_end_exclusive_ms'],
        'site_horizons': [x['forecast_horizon_hours'] for x in cohort['horizons']],
        'first_capture_clock_independently_signed': False,
        'historical_public_availability_verified': False,
        'original_sensor_signed': False,
        'production_admission': False,
        'model_fitting_performed': False,
    }
    return raw, cohort, receipt


def save_one(root, site, raw, cohort, receipt):
    root = Path(root)
    require(not root.is_symlink(), 'untrusted evidence root symlink')
    root.mkdir(parents=False, exist_ok=True, mode=0o700)
    require(root.is_dir() and not root.is_symlink(), 'invalid evidence root')
    require(site == receipt['station'] == cohort['station'], 'site identity differs')
    require(sha256(raw).hexdigest() == receipt['source_sha256'], 'original digest mismatch')
    require(sha256(canonical(cohort)).hexdigest() == receipt['cohort_sha256'],
            'cohort digest mismatch')
    write_once(root / (site + '-original.json'), raw)
    write_once(root / (site + '-cohort.json'), canonical(cohort) + b'\n')
    write_once(root / (site + '-receipt.json'), canonical(receipt) + b'\n')
    verify_one(root, site)


def verify_one(root, site):
    root = Path(root)
    require(site in lock()[0]['independent_stations_in_fixed_order'], 'unapproved site')
    raw = (root / (site + '-original.json')).read_bytes()
    cohort = json.loads((root / (site + '-cohort.json')).read_bytes())
    receipt = json.loads((root / (site + '-receipt.json')).read_bytes())
    require(receipt.get('schema') == SCHEMA and receipt.get('station') == site,
            'source receipt changed/station substituted')
    require(receipt.get('source_url') == fixed_url(site), 'source origin switched')
    require(receipt.get('preregistration_sha256') == STUDY_PROTOCOL_SHA,
            'protocol source mutated')
    require(len(raw) == receipt.get('source_bytes') and
            sha256(raw).hexdigest() == receipt.get('source_sha256'),
            'original NOAA bytes missing or changed')
    require(receipt.get('cohort_sha256') == sha256(canonical(cohort)).hexdigest(),
            'derived cohort changed')
    expected = build_site(raw, site,
        capture_start_ms=receipt['capture_started_ms'],
        capture_end_ms=receipt['capture_completed_ms'],
        sha256_pin=receipt['source_sha256'])
    require(cohort == expected, 'independently replayed cohort mismatch')
    require(cohort['preregistered_protocol_sha256'] == STUDY_PROTOCOL_SHA,
            'wrong site cohort preregistration')
    require(receipt['source_rows'] == cohort['original_source_rows'] and
            receipt['fixed_window_exclusive_end_ms'] == cohort['source_clock_end_exclusive_ms'],
            'derived sample record mismatch')
    require(receipt['site_horizons'] == [1, 3, 6], 'forecast horizon altered')
    for flag in ('first_capture_clock_independently_signed',
                 'historical_public_availability_verified',
                 'original_sensor_signed', 'production_admission',
                 'model_fitting_performed'):
        require(receipt.get(flag) is False, 'unsupported scientific/production assertion')
    return receipt, cohort


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--context', required=True)
    args = parser.parse_args(argv)
    require(args.context.startswith('github-run:') and len(args.context) >= 18,
            'missing independently cross-checkable run context')
    spec, pin = lock()
    require(pin == STUDY_PROTOCOL_SHA, 'unfrozen preregistration')
    root = Path(args.output)
    summaries = []
    # Exact original preregistered order. There is no retry, replacement, or
    # hidden source-selection branch: a refusal leaves incomplete artifacts.
    for i, site in enumerate(spec['independent_stations_in_fixed_order']):
        if i: time.sleep(1.1)  # AWC asks clients to space requests.
        raw, cohort, receipt = download_one(site)
        receipt['capture_context'] = args.context
        save_one(root, site, raw, cohort, receipt)
        summaries.append({
            'site': site, 'source_sha256': receipt['source_sha256'],
            'source_bytes': receipt['source_bytes'],
            'source_rows': receipt['source_rows'],
            'capture_started_ms': receipt['capture_started_ms'],
            'capture_completed_ms': receipt['capture_completed_ms'],
            'hour_statuses': cohort['hours_with_each_status'],
            'horizons': [
                {'hours': h['forecast_horizon_hours'],
                 'retrospective_train': h['folds']['train']['reason_counts']['retrospective_receipt_proxy_eligible'],
                 'retrospective_calibration': h['folds']['calibration']['reason_counts']['retrospective_receipt_proxy_eligible'],
                 'retrospective_test': h['folds']['test']['reason_counts']['retrospective_receipt_proxy_eligible'],
                 'first_capture_bounded_test': h['folds']['test']['reason_counts']['first_capture_bounded_eligible']}
                for h in cohort['horizons']],
        })
    require([s['site'] for s in summaries] == spec['independent_stations_in_fixed_order'],
            'missing preregistered station')
    for site in spec['independent_stations_in_fixed_order']:
        verify_one(root, site)
    print(json.dumps({
        'scope': 'RESEARCH_ORIGINAL_SOURCE_ONLY',
        'run_context': args.context,
        'preregistration_sha256': pin,
        'stations': summaries,
        'first_capture_trusted_signed_time': False,
        'original_historical_public_availability_proven': False,
        'model_fitting_performed': False,
        'production_authorized': False}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
