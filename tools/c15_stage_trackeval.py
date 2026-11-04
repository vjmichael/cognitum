"""Stage already-frozen MOT17 tracker predictions for pinned official TrackEval.

This runs AFTER tracking. Ground truth is only staged for the external
independent scorer. No image downloads or GT-as-detector operations.
Metadata matches the MOT17-02 official sequence dimensions; seqLength is
taken from the public heldout validation split (not invented footage).
"""
from argparse import ArgumentParser
from hashlib import sha256
from pathlib import Path
import csv
import math
import shutil

from cognitum.spatial_mot_adapter import read_mot, MOTRejected

SEQUENCE="MOT17-02-FRCNN"
SPLIT="MOT17-train"
TRACKERS=("C15","ByteTrack")


def _filter_unassigned_predictions(path:Path)->tuple[bytes,int]:
    """Filter only ID=-1 detector/no-track placeholders for reference TrackEval.

    A negative identity is not a valid tracked object. Reject other negative
    identities, malformed rows, NaN and duplicate positive frame/ID pairs.
    Never renumber surviving tracked objects or touch original predictions.
    """
    rows=[]
    filtered=0
    seen=set()
    try:
        original=path.read_bytes()
        text=original.decode("utf-8-sig")
        for columns in csv.reader(text.splitlines()):
            if not columns:
                continue
            if len(columns)<7:
                raise ValueError("truncated prediction row")
            frame=float(columns[0])
            identity=float(columns[1])
            if (not math.isfinite(frame) or not frame.is_integer() or frame<1
                    or not math.isfinite(identity) or not identity.is_integer()):
                raise ValueError("invalid frame/identity")
            if not all(math.isfinite(float(v)) for v in columns[:7]):
                raise ValueError("nonfinite prediction row")
            if float(columns[4])<=0 or float(columns[5])<=0:
                raise ValueError("invalid tracked bounding box")
            if identity==-1:
                # Ignore only structurally valid unassigned observations.
                # Never conceal malformed detector rows through filtering.
                filtered+=1
                continue
            if identity<0:
                raise ValueError("unknown negative identity, not a placeholder")
            key=(int(frame),int(identity))
            if key in seen:
                raise ValueError("duplicate identity in a single frame")
            seen.add(key)
            rows.append(",".join(columns)+"\n")
    except (UnicodeError,OverflowError,ValueError) as exc:
        raise ValueError("invalid frozen tracker predictions") from exc
    if not rows:
        raise ValueError("no valid tracked identities after placeholder exclusion")
    return "".join(rows).encode("utf-8"),filtered


def stage(root:Path,gt:Path,c15:Path,bytetrack:Path):
    for item in (root,gt,c15,bytetrack):
        if not isinstance(item,Path) or not item.is_absolute():
            raise ValueError("explicit absolute staging paths required")
    if root.exists():
        raise ValueError("TrackEval staging root must be fresh")
    input_files=(gt,c15,bytetrack)
    for file in input_files:
        if not file.is_file() or file.is_symlink() or not 0<file.stat().st_size<=80_000_000:
            raise ValueError("invalid benchmark input")
    if gt.resolve() in (c15.resolve(),bytetrack.resolve()):
        raise ValueError("never use GT as tracker prediction")
    ground_truth,_=read_mot(gt,kind="gt")
    # Keep strict C15 parsing and source hashes unchanged; the ByteTrack
    # CLI may emit ID=-1 unassigned placeholders. The official evaluator
    # must receive only rows representing an actual tracked identity.
    first,_=read_mot(c15,kind="prediction")
    byte_data,placeholder_count=_filter_unassigned_predictions(bytetrack)
    if not ground_truth or not first or not byte_data:
        raise ValueError("empty real-world result")
    gt_dest=root/"gt"/SPLIT/SEQUENCE/"gt"/"gt.txt"
    gt_dest.parent.mkdir(parents=True)
    shutil.copyfile(gt,gt_dest)
    for name,file in zip(TRACKERS,(c15,bytetrack)):
        dest=root/"trackers"/SPLIT/name/"data"/(SEQUENCE+".txt")
        dest.parent.mkdir(parents=True)
        if name=="ByteTrack":
            dest.write_bytes(byte_data)
        else:
            shutil.copyfile(file,dest)
    # Fail closed unless staging exactly preserved the accepted identities.
    staged,_=read_mot(root/"trackers"/SPLIT/"ByteTrack"/"data"/(SEQUENCE+".txt"),
                      kind="prediction")
    if not staged:
        raise ValueError("no staged ByteTrack tracked identities")
    seq_len=max(box.frame for box in ground_truth)
    seqinfo=root/"gt"/SPLIT/SEQUENCE/"seqinfo.ini"
    seqinfo.write_text(
        "[Sequence]\n"
        "name="+SEQUENCE+"\n"
        "imDir=img1\nframeRate=30\n"
        "seqLength="+str(seq_len)+"\n"
        "imWidth=1920\nimHeight=1080\nimExt=.jpg\n",
        encoding="ascii")
    seqmap=root/"gt"/"seqmaps"/(SPLIT+".txt")
    seqmap.parent.mkdir(parents=True)
    seqmap.write_text("name\n"+SEQUENCE+"\n",encoding="ascii")
    hashes={name:sha256(path.read_bytes()).hexdigest()
            for name,path in (("gt",gt),("c15",c15),("bytetrack",bytetrack))}
    # Returned input SHA-256 values still refer to the untouched original
    # GT, C15 and ByteTrack artifacts. The filtered version is separately
    # hashed to make the evaluation transformation auditable.
    hashes["bytetrack_staged"]=sha256(byte_data).hexdigest()
    hashes["bytetrack_unassigned_rows_excluded"]=placeholder_count
    return seqmap,hashes


def main():
    parser=ArgumentParser()
    for option in ("root","gt","c15","bytetrack"):
        parser.add_argument("--"+option,required=True)
    args=parser.parse_args()
    root=Path(args.root).resolve()
    seqmap,hashes=stage(root,*(Path(getattr(args,x)).resolve()
                               for x in ("gt","c15","bytetrack")))
    print("TrackEval staging file:",seqmap)
    for key,value in sorted(hashes.items()):
        print(key+":",value)
    print("Evaluation configuration: MOT17-train format, 299-frame validation subset;")
    print("not official MOTChallenge leaderboard submission")


if __name__=="__main__":
    main()
