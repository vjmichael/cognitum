"""Optional PyMC worker entrypoint. Host must pin this source and interpreter."""
import sys
from cognitum.probability_continuous import MAX_FRAME, _compute

def main():
    raw=sys.stdin.buffer.read(MAX_FRAME+1)
    if len(raw)>MAX_FRAME:return 2
    sys.stdout.buffer.write(_compute(raw,host_authorized=True,enabled=True,in_worker=True))
    sys.stdout.buffer.flush()
    return 0

if __name__=='__main__':raise SystemExit(main())
