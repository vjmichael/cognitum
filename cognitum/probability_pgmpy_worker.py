"""C13 P2 worker entrypoint. Not OS-sandboxed; Lu must supply hard ceilings."""
import sys
from cognitum.probability_backend import MAX_FRAME, _compute

def main():
    data = sys.stdin.buffer.read(MAX_FRAME + 1)
    if len(data) > MAX_FRAME:
        return 2
    sys.stdout.buffer.write(_compute(data, host_authorized=True, enabled=True, in_worker=True))
    sys.stdout.buffer.flush()
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
