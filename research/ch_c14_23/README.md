# CH-C14-23

Research-only. Run on Linux Python with numpy, scipy and pytest:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python run.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python bounded_global.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python independent_audit.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -q test_ch23.py
```

See `frozen_protocol.json` and `Engineering_Report_CH_C14_23.md`. No release certification. `ch22_pinned.py` is a frozen prior implementation, with a separately prescribed CH23 six-start schedule in `run.py`.
