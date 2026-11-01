"""Non-release hostile/slow child fixture for supervisor process-tree tests."""
import os
from pathlib import Path
import subprocess
import sys
import time

# Inherits worker's process group deliberately; tests require entire group kill.
child = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(120)'])
ready = os.environ.get('COGNITUM_G25_TEST_PIDFILE')
if ready:
    Path(ready).write_text(f'{os.getpid()} {child.pid}', encoding='ascii')
sys.stdin.buffer.readline()
time.sleep(120)
