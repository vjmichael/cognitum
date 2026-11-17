"""Fixed C11 P3 subprocess entrypoint: raw WorkflowRequest stdin -> WorkflowResult stdout.

The launcher, never a model request, chooses this worker. Runs under Python -I.
This is NOT an OS sandbox nor a host authorization authority.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cognitum.optimization_workflows import MAX_FRAME, WorkflowRegistry


def main():
    buf = sys.stdin.buffer.read(MAX_FRAME + 1)
    if not 0 < len(buf) <= MAX_FRAME:
        return 2
    try:
        frame = WorkflowRegistry(enabled=True).run_frame(buf, host_authorized=True)
    except Exception:
        return 3
    sys.stdout.buffer.write(frame)
    sys.stdout.buffer.flush()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
