"""Windows kernel Job-owned *fixed diagnostic worker* for Cognitum R3.

This is an independent native process-custody prerequisite, NOT the SSM
production worker: there is NO Lu grant, Core issuer, installer signer, remote
monotonic authority, output release, or user-controlled worker command.

The child is created SUSPENDED and attached to a kill-on-close Job before its
primary thread resumes. A failure never falls back to unsupervised Popen.
The diagnostic executes one of two fixed Python sleep commands only.
"""
from __future__ import annotations

import ctypes
import hashlib
from pathlib import Path
import subprocess
import sys
import time


class WorkerCustodyUnavailable(RuntimeError):
    """Kernel cannot prove the expected fixed worker custody lifecycle."""


MAX_IMAGE_BYTES = 128 * 1024 * 1024
JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
CREATE_SUSPENDED = 0x00000004
CREATE_NO_WINDOW = 0x08000000
WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 258
STILL_ACTIVE = 259
FIXTURE_COMMANDS = {
    "exit": "import time;time.sleep(0.01)",
    "timeout": "import time;time.sleep(30)",
}


def _need(ok, detail):
    if not ok:
        raise WorkerCustodyUnavailable("Cognitum Windows Job custody refused: " + detail)


def _win_api():
    _need(sys.platform == "win32", "Windows kernel Job only")
    from ctypes import wintypes as w

    class STARTUPINFO(ctypes.Structure):
        _fields_ = [
            ("cb", w.DWORD), ("lpReserved", w.LPWSTR),
            ("lpDesktop", w.LPWSTR), ("lpTitle", w.LPWSTR),
            ("dwX", w.DWORD), ("dwY", w.DWORD),
            ("dwXSize", w.DWORD), ("dwYSize", w.DWORD),
            ("dwXCountChars", w.DWORD), ("dwYCountChars", w.DWORD),
            ("dwFillAttribute", w.DWORD), ("dwFlags", w.DWORD),
            ("wShowWindow", w.WORD), ("cbReserved2", w.WORD),
            ("lpReserved2", ctypes.c_void_p),
            ("hStdInput", w.HANDLE), ("hStdOutput", w.HANDLE),
            ("hStdError", w.HANDLE),
        ]

    class PROCESS_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("hProcess", w.HANDLE), ("hThread", w.HANDLE),
            ("dwProcessId", w.DWORD), ("dwThreadId", w.DWORD),
        ]

    class BASIC_LIMIT(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", w.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", w.DWORD), ("Affinity", ctypes.c_size_t),
            ("PriorityClass", w.DWORD), ("SchedulingClass", w.DWORD),
        ]

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount", ctypes.c_uint64),
            ("WriteTransferCount", ctypes.c_uint64),
            ("OtherTransferCount", ctypes.c_uint64),
        ]

    class EXTENDED_LIMIT(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", BASIC_LIMIT), ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    class ACCOUNTING(ctypes.Structure):
        _fields_ = [
            ("TotalUserTime", ctypes.c_int64),
            ("TotalKernelTime", ctypes.c_int64),
            ("ThisPeriodTotalUserTime", ctypes.c_int64),
            ("ThisPeriodTotalKernelTime", ctypes.c_int64),
            ("TotalPageFaultCount", w.DWORD),
            ("TotalProcesses", w.DWORD), ("ActiveProcesses", w.DWORD),
            ("TotalTerminatedProcesses", w.DWORD),
        ]

    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
    k.CreateJobObjectW.restype = w.HANDLE
    k.SetInformationJobObject.argtypes = [
        w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
    k.SetInformationJobObject.restype = w.BOOL
    k.CreateProcessW.argtypes = [
        w.LPCWSTR, w.LPWSTR, ctypes.c_void_p, ctypes.c_void_p,
        w.BOOL, w.DWORD, ctypes.c_void_p, w.LPCWSTR,
        ctypes.POINTER(STARTUPINFO), ctypes.POINTER(PROCESS_INFORMATION)]
    k.CreateProcessW.restype = w.BOOL
    k.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
    k.AssignProcessToJobObject.restype = w.BOOL
    k.IsProcessInJob.argtypes = [w.HANDLE, w.HANDLE,
                                 ctypes.POINTER(w.BOOL)]
    k.IsProcessInJob.restype = w.BOOL
    k.ResumeThread.argtypes = [w.HANDLE]
    k.ResumeThread.restype = w.DWORD
    k.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
    k.WaitForSingleObject.restype = w.DWORD
    k.GetExitCodeProcess.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
    k.GetExitCodeProcess.restype = w.BOOL
    k.TerminateJobObject.argtypes = [w.HANDLE, w.UINT]
    k.TerminateJobObject.restype = w.BOOL
    k.QueryInformationJobObject.argtypes = [
        w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD, ctypes.c_void_p]
    k.QueryInformationJobObject.restype = w.BOOL
    k.CloseHandle.argtypes = [w.HANDLE]
    k.CloseHandle.restype = w.BOOL
    return k, w, STARTUPINFO, PROCESS_INFORMATION, EXTENDED_LIMIT, ACCOUNTING


def _image_sha(path):
    p = Path(path)
    _need(p.is_absolute() and p.is_file() and not p.is_symlink(),
          "existing exact absolute fixed executable required")
    _need(0 < p.stat().st_size <= MAX_IMAGE_BYTES, "bounded installed image")
    with p.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


class WindowsFixedJobProbe:
    """Windows-only native Job test. Does not accept a worker command.

    Expected executable hash is HOST DATA only, not proof of Authenticode or
    installer-owned enrollment. No caller may promote this fixture to a Lu
    tool/SSM job. It is independent proof of OS Job mechanics.
    """

    def __init__(self, *, trusted_python_executable, trusted_image_sha256):
        _need(sys.platform == "win32", "Windows-only native Job")
        _need(type(trusted_python_executable) is str and
              type(trusted_image_sha256) is str and
              len(trusted_image_sha256) == 64 and
              all(c in "0123456789abcdef" for c in trusted_image_sha256),
              "fixed image digest pin required")
        self.image = trusted_python_executable
        self.pin = trusted_image_sha256
        _need(_image_sha(self.image) == self.pin,
              "fixed executable image does not match host pin")
        self.last_kernel_reap_verified = False

    def run(self, *, mode="exit", deadline_ms=4000):
        _need(type(mode) is str and mode in FIXTURE_COMMANDS,
              "closed fixed diagnostic worker kind")
        _need(type(deadline_ms) is int and 50 <= deadline_ms <= 10000,
              "bounded Job observation deadline")
        _need(_image_sha(self.image) == self.pin,
              "fixed executable changed before launch")
        k, w, STARTUP, PROCESS, LIMIT, ACCOUNTING = _win_api()
        job = k.CreateJobObjectW(None, None)
        _need(job, "CreateJobObjectW refused")
        pi = PROCESS()
        self.last_kernel_reap_verified = False
        failure = None
        succeeded = False
        assigned = False
        process_started = False
        exit_code = w.DWORD()
        try:
            limits = LIMIT()
            limits.BasicLimitInformation.LimitFlags = (
                JOB_OBJECT_LIMIT_ACTIVE_PROCESS | JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)
            limits.BasicLimitInformation.ActiveProcessLimit = 1
            _need(k.SetInformationJobObject(job, 9, ctypes.byref(limits),
                                            ctypes.sizeof(limits)),
                  "private kill-on-close Job limits refused")
            si = STARTUP()
            si.cb = ctypes.sizeof(si)
            # This command is hard-coded by Cognitum, never from a user
            # request or model. No console, shell or inherited handles.
            argv = [self.image, "-I", "-c", FIXTURE_COMMANDS[mode]]
            cmd = ctypes.create_unicode_buffer(subprocess.list2cmdline(argv))
            _need(k.CreateProcessW(self.image, cmd, None, None, False,
                                   CREATE_SUSPENDED | CREATE_NO_WINDOW,
                                   None, None, ctypes.byref(si), ctypes.byref(pi)),
                  "suspended fixed worker creation refused")
            process_started = True
            _need(k.AssignProcessToJobObject(job, pi.hProcess),
                  "kernel Job assignment before worker release refused")
            in_job = w.BOOL()
            _need(k.IsProcessInJob(pi.hProcess, job, ctypes.byref(in_job)) and
                  in_job.value, "kernel process/Job membership not observed")
            assigned = True
            _need(k.ResumeThread(pi.hThread) != 0xFFFFFFFF,
                  "suspended worker release refused")
            wait = k.WaitForSingleObject(pi.hProcess, deadline_ms)
            if wait == WAIT_TIMEOUT:
                raise WorkerCustodyUnavailable(
                    "Cognitum Windows Job custody refused: fixed worker timeout")
            _need(wait == WAIT_OBJECT_0, "kernel worker wait failed")
            _need(k.GetExitCodeProcess(pi.hProcess, ctypes.byref(exit_code)) and
                  exit_code.value != STILL_ACTIVE and exit_code.value == 0,
                  "fixed worker exit refused")
            succeeded = True
        except BaseException as exc:
            failure = exc
        finally:
            # Job always kills remaining descendants before closing handles.
            if job:
                k.TerminateJobObject(job, 0xEE)
            if process_started:
                waited = k.WaitForSingleObject(pi.hProcess, 5000)
                if waited == WAIT_OBJECT_0 and job:
                    until = time.monotonic() + 2.0
                    while time.monotonic() < until:
                        accounting = ACCOUNTING()
                        if (k.QueryInformationJobObject(
                                job, 1, ctypes.byref(accounting),
                                ctypes.sizeof(accounting), None) and
                                accounting.ActiveProcesses == 0):
                            self.last_kernel_reap_verified = True
                            break
                        time.sleep(0.02)
                if pi.hThread:
                    k.CloseHandle(pi.hThread)
                if pi.hProcess:
                    k.CloseHandle(pi.hProcess)
            if job:
                k.CloseHandle(job)
        _need(self.last_kernel_reap_verified or not process_started,
              "kernel termination/reaping remained uncertain")
        if failure is not None:
            if isinstance(failure, WorkerCustodyUnavailable):
                raise failure
            raise WorkerCustodyUnavailable(
                "Cognitum Windows Job custody refused: native failure") from failure
        _need(succeeded and assigned and self.last_kernel_reap_verified,
              "Job cleanup/ownership witness unavailable")
        return {
            "status": "WINDOWS_FIXED_JOB_PROBE_ONLY",
            "job_assigned_before_resume": True,
            "kernel_membership_observed": True,
            "kernel_process_exit_observed": True,
            "kernel_job_empty_after_cleanup": True,
            "installed_production_ssm_worker_qualified": False,
            "installed_lu_core_peer_verified": False,
            "model_tool_execution_authorized": False,
            "output_delivery_authorized": False,
        }
