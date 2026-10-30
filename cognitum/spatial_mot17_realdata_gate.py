"""C15 T1 P2H: stage verified, *unchanged* MOT17 benchmark inputs.

Research-only, fail-closed. Never turns a tracking result into a scientific
claim. This is a parallel native-source track, not the lossless Protobuf adapter.
Original MOT17 GT has 9 columns, non-pedestrian classes and ignore regions;
MPNTrack predictions may use track ID zero. Preserve those bytes so a real
TrackEval MOT17 evaluator can apply its own official pre-processing.
"""
from __future__ import annotations

import configparser
import hashlib
import json
import re
import subprocess
import sys
import time
import zipfile
import stat
from pathlib import Path

from cognitum.spatial_trackeval_bridge import read_summary, ObservationRejected

SEQ = re.compile(r'^MOT17-\d{2}-(DPM|FRCNN|SDP)$')
MAX_ENTRY = 50_000_000
RUNNER_SHA = '12c8791b303e0a0b50f753af204249e622d0281a'
RUNNER_TREE_SHA = 'ce583e59d96b33aad5f8f62149d96bc6bc4d8f96'

class RealDataGateRejected(ValueError):
    pass

def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()

def verify_pinned_trackeval_source(*, source_zip: Path, checkout: Path) -> dict:
    """Reconstruct Git tree from uploaded ZIP; match all bytes in checkout.

    The expected Git tree belongs to pinned TrackEval commit RUNNER_SHA.
    This authenticates archive-to-commit content, not runtime deps or dataset.
    """
    def git_object(kind: str, b: bytes) -> bytes:
        return hashlib.sha1(f'{kind} {len(b)}\0'.encode() + b).digest()

    def git_tree_sha(tree: dict) -> bytes:
        entries=[]
        for name, node in sorted(tree.items(),key=lambda item: item[0] + ('/' if isinstance(item[1],dict) else '')):
            if isinstance(node,dict):
                mode='40000'; sha=git_tree_sha(node)
            else:
                data, permissions=node
                mode='100755' if (permissions & 0o111) else '100644'
                sha=git_object('blob',data)
            entries.append(mode.encode()+b' '+name.encode()+b'\0'+sha)
        return git_object('tree',b''.join(entries))

    try:
        if source_zip.stat().st_size>10_000_000: raise RealDataGateRejected('SOURCE_ZIP_TOO_LARGE')
        tree={}; checks=0; total=0
        with zipfile.ZipFile(source_zip) as z:
            for info in z.infolist():
                if info.is_dir(): continue
                parts=info.filename.split('/')
                if len(parts)<2 or parts[0]!='TrackEval-master' or any(
                    part in ('','.','..') for part in parts[1:]):
                    raise RealDataGateRejected('INVALID_SOURCE_ZIP_PATH')
                permissions=info.external_attr >> 16
                if stat.S_ISLNK(permissions):
                    raise RealDataGateRejected('SOURCE_ARCHIVE_SYMLINK_DENIED')
                if info.file_size>2_000_000:raise RealDataGateRejected('SOURCE_ARCHIVE_FILE_TOO_LARGE')
                total+=info.file_size
                if total>4_000_000:raise RealDataGateRejected('SOURCE_ARCHIVE_TOTAL_TOO_LARGE')
                data=z.read(info)
                path=checkout.joinpath(*parts[1:])
                if not path.is_file() or path.is_symlink() or path.read_bytes()!=data:
                    raise RealDataGateRejected('SOURCE_CHECKOUT_CONTENT_MISMATCH')
                node=tree
                for part in parts[1:-1]:node=node.setdefault(part,{})
                if parts[-1] in node:raise RealDataGateRejected('DUPLICATE_SOURCE_ARCHIVE_ENTRY')
                node[parts[-1]]=(data,permissions)
                checks+=1
        actual_tree=git_tree_sha(tree).hex()
        if actual_tree!=RUNNER_TREE_SHA or checks!=86:
            raise RealDataGateRejected('SOURCE_GIT_TREE_MISMATCH')
        return {'commit':RUNNER_SHA,'git_tree_sha':actual_tree,'files_verified':checks,
                'source_zip_sha256':sha256(source_zip.read_bytes())}
    except (FileNotFoundError,zipfile.BadZipFile,ValueError, OSError) as e:
        if isinstance(e,RealDataGateRejected):raise
        raise RealDataGateRejected('SOURCE_ARCHIVE_INVALID') from e


def _read(z: zipfile.ZipFile, name: str):
    try: info = z.getinfo(name)
    except KeyError as e: raise RealDataGateRejected(f'MISSING_ARCHIVE_ENTRY:{name}') from e
    if info.is_dir() or info.file_size > MAX_ENTRY:
        raise RealDataGateRejected(f'INVALID_ARCHIVE_ENTRY:{name}')
    data = z.read(info)
    if len(data) != info.file_size:
        raise RealDataGateRejected(f'CORRUPT_ARCHIVE_ENTRY:{name}')
    return data

def _save(path: Path, data: bytes) -> str:
    if path.exists():
        raise RealDataGateRejected(f'REFUSE_OVERWRITE:{path.name}')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    if path.read_bytes() != data:
        raise RealDataGateRejected('STAGED_BYTES_CHANGED')
    return sha256(data)

def _seq_metadata(seqinfo: bytes, name: str) -> dict:
    p=configparser.ConfigParser()
    try: p.read_string(seqinfo.decode('utf-8-sig'))
    except (ValueError, UnicodeError, configparser.Error) as e:
        raise RealDataGateRejected('INVALID_SEQINFO') from e
    try:
        if p.get('Sequence','name') != name:
            raise RealDataGateRejected('SEQINFO_NAME_MISMATCH')
        length=p.getint('Sequence','seqLength')
        width=p.getint('Sequence','imWidth');height=p.getint('Sequence','imHeight')
        fps=p.getint('Sequence','frameRate')
        if min(length,width,height,fps) < 1 or max(length,width,height,fps) > 100000:
            raise RealDataGateRejected('INVALID_SEQINFO_BOUNDS')
        return {'frames':length,'width':width,'height':height,'source_fps':fps}
    except (configparser.Error, ValueError) as e:
        raise RealDataGateRejected('INVALID_SEQINFO_VALUES') from e

def _validate_rows(content: bytes, *, role: str, nframes: int):
    try: lines=content.decode('utf-8-sig').splitlines()
    except UnicodeError as e: raise RealDataGateRejected('NON_UTF8_MOT') from e
    if not lines or len(lines)>500000:
        raise RealDataGateRejected('INVALID_ROW_COUNT')
    min_id=None;maxframe=0
    for index,line in enumerate(lines,1):
        parts=line.split(',')
        if (role=='prediction' and len(parts)!=10) or (role!='prediction' and len(parts) not in (9,10)):
            raise RealDataGateRejected(f'UNSUPPORTED_{role}_COLUMN_COUNT:{index}')
        try:
            nums=[float(x) for x in parts]
            import math
            if not all(math.isfinite(x) for x in nums):raise ValueError('nonfinite')
            frame=nums[0]; identity=nums[1]
            if frame != int(frame) or not 1<=frame<=nframes:raise ValueError('frame')
            if identity != int(identity):raise ValueError('identity')
            if role=='prediction' and identity<0:raise ValueError('negative identity')
            if nums[4]<=0 or nums[5]<=0:raise ValueError('size')
        except (ValueError,OverflowError) as e:
            raise RealDataGateRejected(f'INVALID_{role}_ROW:{index}') from e
        min_id=identity if min_id is None else min(min_id,identity)
        maxframe=max(maxframe,int(frame))
    return {'rows':len(lines),'min_track_id':int(min_id),'last_observed_frame':maxframe}

def stage_mot17(*, example_zip: Path, mot17_labels_zip: Path, output: Path,
                sequences: list[str] | None=None) -> dict:
    """Only standard, complete, authentic MOT17 labels + MPNTrack predictions.

    Sequence metadata + GT must match the independently sourced label archive.
    GT, seqinfo, prediction remain unmodified; filtered seqmap is derived.
    """
    if output.exists() and any(output.iterdir()):
        raise RealDataGateRejected('OUTPUT_DIRECTORY_MUST_BE_EMPTY')
    requested=sequences or ['MOT17-02-DPM']
    if not requested or len(set(requested))!=len(requested) or len(requested)>21:
        raise RealDataGateRejected('INVALID_SEQUENCE_SELECTION')
    if any(not SEQ.fullmatch(s) for s in requested):
        raise RealDataGateRejected('INVALID_SEQUENCE_NAME')
    output=output.resolve(); result=[]; file_hashes={}; planned={}
    with zipfile.ZipFile(example_zip) as ez,zipfile.ZipFile(mot17_labels_zip) as lz:
        seqmap=_read(ez,'data/gt/mot_challenge/seqmaps/MOT17-train.txt').decode().splitlines()
        listed=set(seqmap[1:]);
        if any(s not in listed for s in requested):
            raise RealDataGateRejected('SEQUENCE_NOT_IN_SOURCE_SEQMAP')
        for seq in requested:
            base=f'data/gt/mot_challenge/MOT17-train/{seq}/'
            official_gt=_read(ez,base+'gt/gt.txt')
            official_info=_read(ez,base+'seqinfo.ini')
            if official_gt != _read(lz,f'train/{seq}/gt/gt.txt'):
                raise RealDataGateRejected('INDEPENDENT_GT_MISMATCH')
            if official_info != _read(lz,f'train/{seq}/seqinfo.ini'):
                raise RealDataGateRejected('INDEPENDENT_SEQINFO_MISMATCH')
            pred=_read(ez,f'data/trackers/mot_challenge/MOT17-train/MPNTrack/data/{seq}.txt')
            metadata=_seq_metadata(official_info,seq)
            gtstats=_validate_rows(official_gt,role='ground_truth',nframes=metadata['frames'])
            predstats=_validate_rows(pred,role='prediction',nframes=metadata['frames'])
            dest={
                f'gt/MOT17-train/{seq}/gt/gt.txt':official_gt,
                f'gt/MOT17-train/{seq}/seqinfo.ini':official_info,
                f'trackers/MOT17-train/MPNTrack/data/{seq}.txt':pred,
            }
            planned.update(dest)
            result.append({'name':seq,'dimensions':metadata,'gt':gtstats,'prediction':predstats,
                           'independent_GT_and_seqinfo_byte_equal':True})
        seqmap_content=('name\n'+'\n'.join(requested)+'\n').encode()
        planned['gt/seqmaps/MOT17-train.txt']=seqmap_content
    # Validate every input before writing any output, avoiding partial stages.
    for relative,data in planned.items():
        file_hashes[relative]=_save(output/relative,data)
    return {'milestone':'C15_T1_P2H', 'status':'authentic_MOT17_inputs_staged',
            'research_only':True,'dataset':'MOT17-train', 'tracker':'MPNTrack',
            'native_gt_preserved':True, 'native_tracker_ids_preserved':True,
            'official_mot17_preprocessing_required':True,
            'source_archives':{'TrackEval_example_data_sha256':sha256(example_zip.read_bytes()),
                'MOT17Labels_sha256':sha256(mot17_labels_zip.read_bytes())},
            'staging_directory':str(output),'sequences':result,'staged_sha256':file_hashes,
            'official_scores':None,'claim':'Parity stage only; no HOTA/MOTA/IDF1 claims'}

def verify_staging(report: dict):
    root=Path(report['staging_directory']);
    for relative,expected in report['staged_sha256'].items():
        path=root/relative
        if not path.is_file() or sha256(path.read_bytes())!=expected:
            raise RealDataGateRejected(f'STAGING_HASH_MISMATCH:{relative}')
    return True

def evaluate_with_official_trackeval(staged: dict, *, trackeval_root: Path|None=None, timeout_sec:int=300,
                                     legacy_numpy_compat: bool=False, source_zip: Path|None=None):
    """Official engine only when the real source checkout is supplied.

    MOT17 must run its *standard* pre-processing (DO_PREPROC True), unlike
    the custom-data adapter's intentionally disabled pre-processing.
    """
    try: verify_staging(staged)
    except RealDataGateRejected as e: return {'status':'blocked_staging_integrity_failure','reason':str(e)}
    if trackeval_root is None:
        return {'status':'blocked_official_evaluator_missing','official_scores':None}
    root=Path(trackeval_root).resolve();script=root/'scripts'/'run_mot_challenge.py'
    if not script.is_file() or not (root/'trackeval/metrics/hota.py').is_file():
        return {'status':'blocked_official_evaluator_missing','official_scores':None}
    if type(timeout_sec)!=int or not 1<=timeout_sec<=3600:
        raise RealDataGateRejected('INVALID_TIMEOUT')
    source_integrity=None
    if source_zip is not None:
        try:source_integrity=verify_pinned_trackeval_source(source_zip=Path(source_zip),checkout=root)
        except RealDataGateRejected as e:
            return {'status':'blocked_unverified_trackeval_source','reason':str(e),'official_scores':None}
    stage=Path(staged['staging_directory']); summary=stage/'trackers/MOT17-train/MPNTrack/pedestrian_summary.txt'
    if summary.exists():
        return {'status':'blocked_stale_evaluator_summary','official_scores':None}
    cmd=[sys.executable,str(script),'--GT_FOLDER',str(stage/'gt'),
         '--TRACKERS_FOLDER',str(stage/'trackers'),'--BENCHMARK','MOT17','--SPLIT_TO_EVAL','train',
         # TrackEval's CLI parses SEQMAP_FILE (default None) using nargs='+',
         # yielding a list where MotChallenge2DBox expects a string. Use the
         # standard GT_FOLDER/seqmaps/MOT17-train.txt default instead.
         '--TRACKERS_TO_EVAL','MPNTrack','--CLASSES_TO_EVAL','pedestrian',
         '--METRICS','HOTA','CLEAR','Identity','--DO_PREPROC','True',
         '--PLOT_CURVES','False','--PRINT_CONFIG','False','--TIME_PROGRESS','False',
         '--USE_PARALLEL','False']
    shim_sha = None
    if legacy_numpy_compat:
        shim = Path(__file__).resolve().parent.parent / 'tools' / 'c15_trackeval_legacy_numpy_compat.py'
        if not shim.is_file():
            return {'status':'blocked_numpy_compatibility_shim_missing', 'official_scores':None}
        shim_sha = sha256(shim.read_bytes())
        cmd = [sys.executable, str(shim), str(script)] + cmd[2:]
    try:
        run=subprocess.run(cmd,cwd=root,capture_output=True,text=True,timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        return {'status':'engine_timeout','official_scores':None}
    if run.returncode:
        return {'status':'engine_failed','exit_code':run.returncode,'stdout_tail':run.stdout[-3500:],
                'stderr_tail':run.stderr[-3500:],'official_scores':None}
    if source_integrity is not None:
        try: verify_pinned_trackeval_source(source_zip=Path(source_zip),checkout=root)
        except RealDataGateRejected as e:
            return {'status':'blocked_evaluator_modified_during_run','reason':str(e),'official_scores':None}
    try: scores=read_summary(summary)
    except ObservationRejected as e:
        return {'status':'engine_summary_missing_or_invalid','reason':str(e),'official_scores':None}
    return {'status':'executed_verified_pinned_trackeval' if source_integrity else 'executed_source_revision_unverified',
            'verified_source':source_integrity,'official_scores':scores,'numpy_compatibility_shim_sha256':shim_sha,
            'source_commit_expected':RUNNER_SHA,'source_verified':bool(source_integrity),
            'MOT17_official_preproc':True,'runner_sha256':sha256(script.read_bytes()),
            'summary_sha256':sha256(summary.read_bytes())}
