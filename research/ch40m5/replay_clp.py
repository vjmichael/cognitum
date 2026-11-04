"""CH40-M.5 research-only replay with IBEX bundled CLP and original 15 CH23 traces.

No IBEX-reported dual/underbound is admitted as an independent mathematical certificate.
Global scientific release remains NO_GO until separately verified upper bounds close gaps.
"""
from __future__ import annotations
import argparse, hashlib, json, math, os, platform, re, resource, subprocess, sys
from pathlib import Path
from tempfile import TemporaryDirectory
from fractions import Fraction as F
from types import SimpleNamespace
import zipfile

EXPECTED_CH40E_ARCHIVE_SHA256 = '6dfd4ea081b783503c7d960419766296642da68a246033fdcf0da94282882078'
EXPECTED_CH39_NESTED_SHA256 = '9e713b102982ea09fecbcfbd27bccf55d56808188bfc3e5be1ba76922000ae6b'
EXPECTED_NESTED_NAME = 'Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip'
SOURCE_SUFFIX = '_1_original_mpfr_trace.json'


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def extract_best_point(s: str):
    match = re.search(r'x\* in\s*\(\s*\[([^\]]+)\]\s*;\s*\[([^\]]+)\]\s*;\s*\[([^\]]+)\]\s*\)', s)
    if not match:
        return None
    vals = []
    for raw in match.groups():
        pair = raw.split(',')
        if len(pair) != 2:
            return None
        a, b = map(float, pair)
        if not (math.isfinite(a) and math.isfinite(b) and a == b):
            return None
        vals.append(a)
    return vals


def limits(memory_bytes, cpu_seconds):
    def apply():
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    return apply


def report(records, args):
    return dict(protocol='CH40M5-BUNDLED-CLP-REPLAY-V1', original_archive_sha256=EXPECTED_CH40E_ARCHIVE_SHA256,
                original_case_count=15, attempted_cases=len(records), scientific_release='NO_GO',
                global_duals_proven_independently=False, certified_closed_global_gaps=0,
                native_execution_records=sum(x.get('native_status') == 'NATIVE_OPTIMIZER_EXECUTED_UNVERIFIED' for x in records),
                independent_points=sum(x.get('independent_candidate_checked') is True for x in records),
                scope='Native optimizer pilot only, not original CH40 signed proof-tree replacement',
                options={'cpu_cap':args.cpu_cap, 'wall_cap':args.wall_cap, 'memory_bytes':args.memory_bytes,
                         'solver_seconds':args.solver_seconds, 'abs_gap':args.abs_gap}, cases=records)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--ibexopt', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--cpu-cap', type=int, default=24)
    p.add_argument('--wall-cap', type=int, default=29)
    p.add_argument('--memory-bytes', type=int, default=1400000000)
    p.add_argument('--solver-seconds', type=float, default=0.15)
    p.add_argument('--abs-gap', type=float, default=0.05)
    p.add_argument('--case', type=str, help='Run one original case for diagnostic only')
    args = p.parse_args()
    if sys.platform != 'linux':
        raise SystemExit('REFUSED: this replay uses Linux RLIMIT sandbox; no unbounded fallback')
    if not (2 <= args.cpu_cap <= 120 and 3 <= args.wall_cap <= 180 and
            100000000 <= args.memory_bytes <= 8000000000 and
            0 < args.solver_seconds <= 30 and args.abs_gap == 0.05):
        raise SystemExit('REFUSED: invalid or non-frozen gate limits')
    if not args.archive.is_file() or sha(args.archive.read_bytes()) != EXPECTED_CH40E_ARCHIVE_SHA256:
        raise SystemExit('REFUSED: original CH40-E archive missing or altered')
    if not args.ibexopt.is_file():
        raise SystemExit('REFUSED: native ibexopt missing')

    # repository location: research/ch40m5/replay_clp.py
    sibling = Path(__file__).resolve().parents[1]/'ch40m2'/'source'
    if not (sibling/'ibex_model.py').is_file():
        raise SystemExit('REFUSED: original reviewed model serializer unavailable')
    sys.path.insert(0, str(sibling))
    from ibex_model import ibex_text
    # Each member and nested source is verified before loading Python code.
    with zipfile.ZipFile(args.archive) as z:
        if sha(z.read(EXPECTED_NESTED_NAME)) != EXPECTED_CH39_NESTED_SHA256:
            raise SystemExit('REFUSED: original nested CH39 archive changed')
        manifest = json.loads(z.read('CH40E_MANIFEST_SHA256.json'))
        if manifest.get('protocol') != 'CH40E-FILE-MANIFEST-V1':
            raise SystemExit('REFUSED: original manifest protocol changed')
        names = sorted(n for n in z.namelist() if n.startswith('results/') and n.endswith(SOURCE_SUFFIX))
        if len(names) != 15 or len({Path(n).name.removesuffix(SOURCE_SUFFIX) for n in names}) != 15:
            raise SystemExit('REFUSED: original 15 cases incomplete')
        cases = []
        for name in names:
            raw = z.read(name)
            if sha(raw) != manifest['file_sha256'].get(name):
                raise SystemExit(f'REFUSED: trace hash mismatch {name}')
            cert = json.loads(raw)['certificate']
            case = Path(name).name.removesuffix(SOURCE_SUFFIX)
            if (cert['model']['d'] != 3 or len(cert['model']['rows']) not in (80, 160)
                    or cert['root_box'] != [['-10', '1'], ['-5', '5'], ['-5', '5']]):
                raise SystemExit(f'REFUSED: changed frozen dimensions or bounds {case}')
            cases.append((case, cert, sha(raw)))
        if args.case and args.case not in {c[0] for c in cases}:
            raise SystemExit('REFUSED: unknown original case')
    sys.path.insert(0, str(args.archive))
    from rational_kernel40d import point_objective
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out/'logs').mkdir(exist_ok=True)
    (args.out/'cov').mkdir(exist_ok=True)
    records = []
    for case, cert, source_sha in cases:
        if args.case and args.case != case:
            continue
        # Native parser reads a separate immutable original-case reproduction, not synthetic data.
        model = args.out/(case+'.bch')
        model_text = ibex_text(SimpleNamespace(name=case, source_sha256=source_sha, certificate=cert))
        model.write_bytes(model_text.encode())
        cmd = [str(args.ibexopt), '--rigor', '--simpl=0', '-a0.05',
               f'-t{args.solver_seconds}', '--trace', f'-o{args.out / "cov" / (case+".cov")}', str(model)]
        rec = {'case':case, 'source_sha256':source_sha,
               'model_sha256':sha(model_text.encode()), 'rows':len(cert['model']['rows']),
               'native_status':'NOT_ACCEPTED', 'scientific_certificate':False}
        try:
            cp = subprocess.run(cmd, capture_output=True, text=True, timeout=args.wall_cap,
                                preexec_fn=limits(args.memory_bytes, args.cpu_cap))
            rec['returncode'] = cp.returncode
            output = cp.stdout+'\n'+cp.stderr
            (args.out/'logs'/(case+'.log')).write_text(output)
            if cp.returncode == 0 and ' f* in' in output and 'results written' in output:
                rec['native_status'] = 'NATIVE_OPTIMIZER_EXECUTED_UNVERIFIED'
                gap = re.search(r'absolute precision on f\*:\s*([^\n]+)', output)
                if gap:
                    rec['solver_reported_absolute_gap'] = gap.group(1).strip()
                rec['solver_internal_time_cap_hit'] = 'time limit' in output
                best = extract_best_point(output)
                if best:
                    try:
                        val = point_objective(cert, [F(x) for x in best])
                        rec['independent_candidate_checked'] = True
                        rec['best_feasible_point'] = [repr(x) for x in best]
                        rec['independent_minimum_point_enclosure'] = [str(-val.hi), str(-val.lo)]
                    except Exception as exc:
                        rec['independent_candidate_error'] = repr(exc)[:250]
            else:
                rec['native_status'] = 'NONZERO_OR_INCOMPLETE'
                rec['output_tail'] = output[-500:]
        except (subprocess.TimeoutExpired, OSError, ValueError) as exc:
            rec['native_status'] = 'RESOURCE_OR_RUNTIME_EXCEPTION'
            rec['runtime_error'] = repr(exc)[:350]
        records.append(rec)
        payload = report(records, args)
        tmp = args.out/'CH40M5_REPLAY.json.tmp'
        tmp.write_text(json.dumps(payload,indent=2,allow_nan=False)+'\n')
        os.replace(tmp,args.out/'CH40M5_REPLAY.json')
        print(f"{len(records):02d}/{1 if args.case else 15} {case} {rec['native_status']} candidate={rec.get('independent_candidate_checked',False)}",flush=True)
    if args.case:
        print('Diagnostic run only; 15-case scientific gate NOT_RUN',flush=True)
    else:
        print('Original 15-case native execution complete; scientific NO_GO',flush=True)


if __name__ == '__main__':
    main()
