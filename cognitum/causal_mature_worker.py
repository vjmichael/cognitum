"""C14 P3C separate-process entry: bounded binary Protobuf only.

Python -I, source pinning and this entrypoint are NOT OS isolation; Lu must
enforce Windows process-tree confinement and host admission independently.
"""
from pathlib import Path
import sys

if __name__ == '__main__':
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from cognitum.causal_mature_backend import _compute_worker,MAX_FRAME
    raw=sys.stdin.buffer.read(MAX_FRAME+1)
    if len(raw)>MAX_FRAME:sys.exit(3)
    sys.stdout.buffer.write(_compute_worker(raw))
