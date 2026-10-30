"""P4E isolated worker entrypoint. Python -I alone is NOT an OS security fence."""
from pathlib import Path
import sys

if __name__=='__main__':
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from cognitum.causal_tigramite_backend import _compute_worker,MAX_FRAME
    raw=sys.stdin.buffer.read(MAX_FRAME+1)
    if len(raw)>MAX_FRAME:sys.exit(3)
    sys.stdout.buffer.write(_compute_worker(raw))
