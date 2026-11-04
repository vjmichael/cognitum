"""CPU auto-detection and parallelism configuration.

What this module does:
  * Auto-detect available CPU cores (logical threads).
  * Set BLAS/OMP/MKL thread pool size so NumPy matrix operations
    (matmul in dot_row, scoring, etc.) use ALL cores.
  * Provide n_workers() for any component that needs to know the core count
    (future KAN/Capsules batch processing, FPGA PE count mapping).

What it does NOT do (and why):
  * Process-pool parallelism for the encoding loop is NOT used. Benchmarks
    on Windows (Ryzen 5 5500, 12 threads) show the spawn overhead (~1.5s per
    worker) dominates the encoding compute (~0.1ms per doc). The encoding
    is memory-bound + Python-overhead-bound, not compute-bound.
  * The real parallelism win is BLAS threading (OpenBLAS/OMP), which
    parallelizes the SGEMV in dot_row (57k×1024 @ 1024) across all cores.

FPGA/ASIC mapping:
  * n_workers() = number of parallel processing elements in the PL fabric.
  * set_blas_threads() = number of DSP slices / ALU lanes per PE.
  * The same interface scales from CPU (NumPy) to FPGA (HLS) to ASIC (RTL).
"""
from __future__ import annotations

import os

# --------------------------------------------------------------------------- #
# Core count
# --------------------------------------------------------------------------- #

def n_workers() -> int:
    """Auto-detect CPU cores (logical threads). Returns a safe worker count.

    On the user's Ryzen 5 5500 (6C/12T) this returns 12.
    Capped at 32 to avoid pathological oversubscription on server CPUs.
    """
    return max(1, min(os.cpu_count() or 4, 32))


def set_blas_threads(n: int | None = None) -> int:
    """Set BLAS/OpenMP/MKL thread pool size. MUST be called before the first
    NumPy BLAS call (i.e., before any matrix multiply). Returns the thread
    count that was set.

    Call this at the top of the entry point (cli.py / __main__.py) BEFORE
    importing numpy-heavy modules, or set the env vars in the .bat launcher.
    """
    n = n or n_workers()
    os.environ["OPENBLAS_NUM_THREADS"] = str(n)
    os.environ["OMP_NUM_THREADS"] = str(n)
    os.environ["MKL_NUM_THREADS"] = str(n)
    os.environ["BLIS_NUM_THREADS"] = str(n)
    # numpy-specific
    os.environ["NUMEXPR_NUM_THREADS"] = str(n)
    return n


# --------------------------------------------------------------------------- #
# BLAS threading verification
# --------------------------------------------------------------------------- #

def verify_blas_threads() -> bool:
    """Check that OpenBLAS is actually using multiple threads.

    Returns True if thread count > 1, False otherwise.
    Safe to call at any time (no side effects).
    """
    import numpy as np
    try:
        # threadpoolctl is the standard way to check, but may not be installed.
        # Fallback: check the env var we set.
        import threadpoolctl
        info = threadpoolctl.threadpool_info()
        for entry in info:
            if entry["internal_api"] == "blas":
                return entry["num_threads"] > 1
    except ImportError:
        pass
    # Fallback: check env var (set by set_blas_threads)
    return int(os.environ.get("OPENBLAS_NUM_THREADS", "1")) > 1


# --------------------------------------------------------------------------- #
# Diagnostic
# --------------------------------------------------------------------------- #

def report() -> str:
    """Print parallelism configuration (for logging at run start)."""
    import platform
    n = n_workers()
    return (f"[parallel] cores={n} workers={n} "
            f"platform={platform.platform()} "
            f"OPENBLAS={os.environ.get('OPENBLAS_NUM_THREADS', 'unset')} "
            f"OMP={os.environ.get('OMP_NUM_THREADS', 'unset')}")
