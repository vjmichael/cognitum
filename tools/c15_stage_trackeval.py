"""Stage already-frozen MOT17 tracker predictions for pinned official TrackEval.

This runs AFTER tracking. Ground truth is only staged for the external
independent scorer. No image downloads or GT-as-detector operations.
Metadata matches the MOT17-02 official sequence dimensions; seqLength is
taken from the public heldout validation split (not invented footage).
"""
from argparse import ArgumentParser
from hashlib import sha256
from pathlib import Path
import shutil

from cognitum.spatial_mot_adapter import read_mot

SEQUENCE="MOT17-02-FRCNN"
SPLIT="MOT17-train"
TRACKERS=("C15","ByteTrack")


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
    first,_=read_mot(c15,kind="prediction")
    second,_=read_mot(bytetrack,kind="prediction")
    if not ground_truth or not first or not second:
        raise ValueError("empty real-world result")
    gt_dest=root/"gt"/SPLIT/SEQUENCE/"gt"/"gt.txt"
    gt_dest.parent.mkdir(parents=True)
    shutil.copyfile(gt,gt_dest)
    for name,file in zip(TRACKERS,(c15,bytetrack)):
        dest=root/"trackers"/SPLIT/name/"data"/(SEQUENCE+".txt")
        dest.parent.mkdir(parents=True)
        shutil.copyfile(file,dest)
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
