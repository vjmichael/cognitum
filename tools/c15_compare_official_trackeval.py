"""Read pinned official TrackEval outputs; report matched C15/ByteTrack scores.

This tool does not calculate metrics or alter predictions. It reads original
TrackEval summary files and requires the exact HOTA/MOTA/IDF1 columns.
"""
import argparse
import json
from pathlib import Path
from math import isfinite

METRICS=("HOTA","MOTA","IDF1")

def read_summary(path: Path) -> dict[str,float]:
    if not path.is_file() or path.is_symlink() or not 0 < path.stat().st_size <= 65536:
        raise ValueError("official TrackEval summary missing, symlinked, empty or oversized")
    lines=[line.split() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(lines)!=2 or len(lines[0])!=len(lines[1]) or len(set(lines[0]))!=len(lines[0]):
        raise ValueError("malformed TrackEval summary header or data")
    entries=dict(zip(lines[0],lines[1]))
    if not all(metric in entries for metric in METRICS):
        raise ValueError("missing required official TrackEval metric")
    values={metric:float(entries[metric]) for metric in METRICS}
    if not all(isfinite(value) and 0 <= value <= 100 for value in values.values()):
        raise ValueError("nonfinite or out-of-range official metric")
    return values


def compare(c15:Path,bytetrack:Path) -> dict:
    if c15.resolve()==bytetrack.resolve():
        raise ValueError("must compare independent TrackEval files")
    first=read_summary(c15)
    second=read_summary(bytetrack)
    return {
        "schema":"cognitum.c15.official-trackeval-comparison.v1",
        "scope":"MOT17-02-FRCNN 299-frame public-detection validation subset",
        "official_leaderboard_submission":False,
        "units":"TrackEval percentage points",
        "metric_source":"pinned upstream official TrackEval summaries",
        "c15":first,
        "bytetrack":second,
        "c15_minus_bytetrack":{metric:round(first[metric]-second[metric],6) for metric in METRICS},
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--c15",type=Path,required=True)
    p.add_argument("--bytetrack",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    result=compare(args.c15,args.bytetrack)
    text=json.dumps(result,sort_keys=True,indent=2)+"\n"
    if args.output.exists():
        raise ValueError("refuse to overwrite existing comparison evidence")
    args.output.write_text(text,encoding="utf-8")
    print(text,end="")


if __name__=="__main__":
    main()
