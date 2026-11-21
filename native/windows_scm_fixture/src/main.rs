//! Cognitum Windows SCM *native acceptance fixture* with SCM-owned Job.
//!
//! Exactly one fixed diagnostic child is created SUSPENDED, inserted in an OS
//! Job before its primary thread is resumed, and retained by the SCM service.
//! No Lu Core grant, SSM data, command, path, secret, payload or signer may be
//! received from an external caller. The process is NOT a production Cognitum
//! host and is deliberately compiled only with acceptance-fixture feature.
//! A real signed installer, independent stop-signing authority, restricted SSM
//! worker, encrypted delivery channel and original Core admission remain OPEN.
#![deny(unsafe_op_in_unsafe_fn)]
#[cfg(all(windows, feature = "ssm-fixture"))]
mod ssm_fixture;
#[cfg(all(windows, feature = "r2-restricted-fixture"))]
mod r2_restricted;
#[cfg(all(windows, feature = "r2-cng-fixture"))]
mod r2_signer;
#[cfg(all(windows, any(feature = "r2-restricted-fixture",
                       feature = "r3-appcontainer-fixture")))]
mod r2_diagnostic;
#[cfg(all(windows, feature = "r3-signed-recovery"))]
mod r3_recovery;
#[cfg(all(windows, feature = "r3-appcontainer-fixture"))]
mod r3_appcontainer;
#[cfg(all(windows, feature = "r3-r1-frozen-fixture"))]
mod r3_r1_runtime;
#[cfg(all(windows, feature = "acceptance-fixture"))]
mod win {
    use std::{
        ffi::{c_void, OsStr}, io, mem, os::windows::ffi::OsStrExt,
        ptr, sync::atomic::{AtomicBool, Ordering},
        thread, time::{Duration, Instant},
    };

    type Handle = *mut c_void;
    const NAME: &str = "CognitumSsmNativeFixtureV1";
    const SERVICE_WIN32_OWN_PROCESS: u32 = 0x10;
    const SERVICE_STOPPED: u32 = 1;
    const SERVICE_START_PENDING: u32 = 2;
    const SERVICE_STOP_PENDING: u32 = 3;
    const SERVICE_RUNNING: u32 = 4;
    const SERVICE_ACCEPT_STOP: u32 = 1;
    const SERVICE_ACCEPT_SHUTDOWN: u32 = 4;
    const SERVICE_CONTROL_STOP: u32 = 1;
    const SERVICE_CONTROL_INTERROGATE: u32 = 4;
    const SERVICE_CONTROL_SHUTDOWN: u32 = 5;
    const CREATE_SUSPENDED: u32 = 4;
    const CREATE_NO_WINDOW: u32 = 0x0800_0000;
    const JOB_LIMIT_ACTIVE: u32 = 8;
    const JOB_LIMIT_KILL_ON_CLOSE: u32 = 0x2000;
    const WAIT_OBJECT_0: u32 = 0;
    const WAIT_TIMEOUT: u32 = 0x102;
    const TOKEN_QUERY: u32 = 8;
    const WIN_LOCAL_SYSTEM_SID: u32 = 22;
    const TEST_CHILD: &str = "--cognitum-fixed-custody-child";
    static STOP: AtomicBool = AtomicBool::new(false);

    #[repr(C)]
    #[derive(Clone, Copy, Default)]
    struct ServiceStatus {
        service_type: u32,
        current_state: u32,
        controls_accepted: u32,
        win32_exit_code: u32,
        service_specific_exit_code: u32,
        checkpoint: u32,
        wait_hint: u32,
    }
    #[repr(C)]
    struct TableEntry {
        name: *mut u16,
        main: Option<unsafe extern "system" fn(u32, *mut *mut u16)>,
    }
    #[repr(C)]
    struct StartupInfo {
        cb: u32,
        reserved: *mut u16,
        desktop: *mut u16,
        title: *mut u16,
        x: u32, y: u32, width: u32, height: u32,
        count_x: u32, count_y: u32, fill: u32, flags: u32,
        show: u16, extra_size: u16, extra: *mut u8,
        stdin: Handle, stdout: Handle, stderr: Handle,
    }
    #[repr(C)]
    struct ProcessInfo {
        process: Handle, thread: Handle, pid: u32, tid: u32,
    }
    // Win32 ABI zero initialization; raw pointer fields do not implement
    // Default on all supported Rust compiler versions.
    impl Default for StartupInfo {
        fn default() -> Self { unsafe { mem::zeroed() } }
    }
    impl Default for ProcessInfo {
        fn default() -> Self { unsafe { mem::zeroed() } }
    }
    #[repr(C)]
    #[derive(Default)]
    struct BasicLimit {
        per_process_time: i64, per_job_time: i64, flags: u32,
        min_working: usize, max_working: usize, active_limit: u32,
        affinity: usize, priority: u32, scheduling: u32,
    }
    #[repr(C)]
    #[derive(Default)]
    struct IoCounters {
        read_ops: u64, write_ops: u64, other_ops: u64,
        read_bytes: u64, write_bytes: u64, other_bytes: u64,
    }
    #[repr(C)]
    #[derive(Default)]
    struct ExtLimit {
        basic: BasicLimit, io: IoCounters,
        process_memory: usize, job_memory: usize,
        peak_process_memory: usize, peak_job_memory: usize,
    }
    #[repr(C)]
    #[derive(Default)]
    struct JobAccounting {
        total_user_time: i64, total_kernel_time: i64,
        this_user_time: i64, this_kernel_time: i64,
        total_page_faults: u32, total_processes: u32,
        active_processes: u32, terminated_processes: u32,
    }
    #[link(name = "advapi32")]
    unsafe extern "system" {
        fn StartServiceCtrlDispatcherW(table: *const TableEntry) -> i32;
        fn RegisterServiceCtrlHandlerExW(
            name: *const u16,
            handler: Option<unsafe extern "system" fn(u32, u32, Handle, Handle) -> u32>,
            context: Handle,
        ) -> Handle;
        fn SetServiceStatus(handle: Handle, status: *const ServiceStatus) -> i32;
        fn OpenProcessToken(process: Handle, access: u32, token: *mut Handle) -> i32;
        fn GetTokenInformation(token: Handle, class: u32, data: Handle,
                               length: u32, needed: *mut u32) -> i32;
        fn IsWellKnownSid(sid: Handle, kind: u32) -> i32;
    }
    #[link(name = "kernel32")]
    unsafe extern "system" {
        fn TerminateProcess(process: Handle, exit_code: u32) -> i32;
        fn GetCurrentProcess() -> Handle;
        fn GetCurrentProcessId() -> u32;
        fn ProcessIdToSessionId(pid: u32, session: *mut u32) -> i32;
        fn CreateJobObjectW(attributes: Handle, name: *const u16) -> Handle;
        fn SetInformationJobObject(job: Handle, class: u32, info: Handle, size: u32) -> i32;
        fn QueryInformationJobObject(job: Handle, class: u32, info: Handle,
                                     size: u32, returned: *mut u32) -> i32;
        fn CreateProcessW(application: *const u16, command: *mut u16,
                          pa: Handle, ta: Handle, inherit: i32, flags: u32,
                          environment: Handle, directory: *const u16,
                          startup: *const StartupInfo, info: *mut ProcessInfo) -> i32;
        fn AssignProcessToJobObject(job: Handle, process: Handle) -> i32;
        fn IsProcessInJob(process: Handle, job: Handle, result: *mut i32) -> i32;
        fn ResumeThread(thread: Handle) -> u32;
        fn TerminateJobObject(job: Handle, code: u32) -> i32;
        fn WaitForSingleObject(handle: Handle, timeout: u32) -> u32;
        fn GetExitCodeProcess(process: Handle, code: *mut u32) -> i32;
        fn CloseHandle(handle: Handle) -> i32;
    }

    fn wide(value: &OsStr) -> Vec<u16> {
        value.encode_wide().chain(std::iter::once(0)).collect()
    }
    fn denied(why: &'static str) -> io::Error {
        io::Error::new(io::ErrorKind::PermissionDenied, why)
    }
    struct Owned(Handle);
    impl Drop for Owned {
        fn drop(&mut self) {
            if !self.0.is_null() {
                unsafe { CloseHandle(self.0); }
            }
        }
    }
    fn require_local_system_session_zero() -> io::Result<()> {
        let mut token: Handle = ptr::null_mut();
        if unsafe { OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &mut token) } == 0
           || token.is_null() {
            return Err(denied("SCM service requires actual unimpersonated OS token"));
        }
        let token = Owned(token);
        let mut size = 0u32;
        unsafe { GetTokenInformation(token.0, 1, ptr::null_mut(), 0, &mut size); }
        if size < mem::size_of::<Handle>() as u32 || size > 4096 {
            return Err(denied("SCM service token user unavailable"));
        }
        let mut aligned = vec![0usize; (size as usize).div_ceil(mem::size_of::<usize>())];
        if unsafe {
            GetTokenInformation(token.0, 1, aligned.as_mut_ptr().cast(),
                                size, &mut size)
        } == 0 {
            return Err(denied("SCM service token user query failed"));
        }
        let sid = unsafe { *(aligned.as_ptr() as *const Handle) };
        if sid.is_null() || unsafe { IsWellKnownSid(sid, WIN_LOCAL_SYSTEM_SID) } == 0 {
            return Err(denied("SCM acceptance fixture only permits LocalSystem"));
        }
        let mut session = u32::MAX;
        if unsafe { ProcessIdToSessionId(GetCurrentProcessId(), &mut session) } == 0 ||
           session != 0 {
            return Err(denied("SCM service must run in session zero"));
        }
        Ok(())
    }
    fn report(handle: Handle, state: u32, specific: u32) -> io::Result<()> {
        let record = ServiceStatus {
            service_type: SERVICE_WIN32_OWN_PROCESS,
            current_state: state,
            controls_accepted: if state == SERVICE_RUNNING {
                SERVICE_ACCEPT_STOP | SERVICE_ACCEPT_SHUTDOWN
            } else { 0 },
            win32_exit_code: if state == SERVICE_STOPPED && specific != 0 { 1066 } else { 0 },
            service_specific_exit_code: specific,
            checkpoint: if matches!(state, SERVICE_START_PENDING | SERVICE_STOP_PENDING) { 1 } else { 0 },
            wait_hint: if matches!(state, SERVICE_START_PENDING | SERVICE_STOP_PENDING) { 10000 } else { 0 },
        };
        if unsafe { SetServiceStatus(handle, &record) } == 0 {
            Err(io::Error::last_os_error())
        } else { Ok(()) }
    }
    unsafe extern "system" fn control(code: u32, _: u32, _: Handle, _: Handle) -> u32 {
        match code {
            SERVICE_CONTROL_STOP | SERVICE_CONTROL_SHUTDOWN => {
                STOP.store(true, Ordering::Release);
                0
            }
            SERVICE_CONTROL_INTERROGATE => 0,
            _ => 120,
        }
    }
    struct Keeper {
        job: Owned,
        child: Owned,
        child_thread: Owned,
        pid: u32,
        #[cfg(feature = "ssm-fixture")]
        original_fixture: crate::ssm_fixture::Prepared,
    }
    impl Keeper {
        fn start() -> io::Result<Self> {
            let job = unsafe { CreateJobObjectW(ptr::null_mut(), ptr::null()) };
            if job.is_null() {
                return Err(io::Error::last_os_error());
            }
            let job = Owned(job);
            let mut limit = ExtLimit::default();
            limit.basic.flags = JOB_LIMIT_ACTIVE | JOB_LIMIT_KILL_ON_CLOSE;
            limit.basic.active_limit = 1;
            if unsafe {
                SetInformationJobObject(job.0, 9, (&mut limit as *mut ExtLimit).cast(),
                                        mem::size_of::<ExtLimit>() as u32)
            } == 0 {
                return Err(denied("SCM-owned Job limit configuration refused"));
            }
            #[cfg(feature = "r3-r1-frozen-fixture")]
            crate::r3_r1_runtime::verify()?;
            #[cfg(feature = "r2-cng-fixture")]
            crate::r2_signer::require_preprovisioned()?;
            #[cfg(feature = "r3-signed-recovery")]
            crate::r3_recovery::refuse_prior_original()?;
            #[cfg(feature = "ssm-fixture")]
            let (app, mut cmd, original_fixture) = crate::ssm_fixture::prepare()?;
            #[cfg(feature = "r3-signed-recovery")]
            crate::r3_recovery::sign_verified_prelaunch(&original_fixture)?;
            #[cfg(not(feature = "ssm-fixture"))]
            let (app, mut cmd) = {
                let exe = std::env::current_exe()?;
                let app = wide(exe.as_os_str());
                let command = format!("\"{}\" {}", exe.display(), TEST_CHILD);
                (app, wide(OsStr::new(&command)))
            };
            let mut si = StartupInfo { cb: mem::size_of::<StartupInfo>() as u32,
                                      ..Default::default() };
            let mut pi = ProcessInfo::default();
            #[cfg(feature = "r3-appcontainer-fixture")]
            crate::r3_appcontainer::launch(&app,&mut cmd,
                (&si as *const StartupInfo).cast(),
                (&mut pi as *mut ProcessInfo).cast())?;
            #[cfg(all(not(feature = "r3-appcontainer-fixture"),
                      feature = "r2-restricted-fixture"))]
            crate::r2_restricted::launch(&app,&mut cmd,
                (&si as *const StartupInfo).cast(),
                (&mut pi as *mut ProcessInfo).cast())?;
            #[cfg(all(not(feature = "r3-appcontainer-fixture"),
                      not(feature = "r2-restricted-fixture")))]
            if unsafe {
                CreateProcessW(app.as_ptr(), cmd.as_mut_ptr(), ptr::null_mut(),
                               ptr::null_mut(), 0, CREATE_SUSPENDED | CREATE_NO_WINDOW,
                               ptr::null_mut(), ptr::null(), &mut si, &mut pi)
            } == 0 {
                return Err(denied("SCM fixed diagnostic child creation refused"));
            }
            let child = Owned(pi.process);
            let thread = Owned(pi.thread);
            #[cfg(feature = "r2-restricted-fixture")]
            if crate::r2_restricted::require_original_worker_restricted(child.0).is_err(){
                unsafe {
                    TerminateProcess(child.0,0xE4);
                    WaitForSingleObject(child.0,5000);
                }
                return Err(denied("SCM original numerical worker token not kernel-restricted"));
            }
            // If any subsequent step fails, the suspended child is terminated
            // directly because it may not yet belong to our kernel Job.
            let accepted = unsafe {
                AssignProcessToJobObject(job.0, child.0) != 0
            };
            let mut is_member = 0i32;
            let joined = accepted && unsafe {
                IsProcessInJob(child.0, job.0, &mut is_member) != 0
            } && is_member != 0;
            if !joined {
                // A pending suspended child not yet adopted by the Job must
                // be directly terminated and reaped before returning.
                unsafe {
                    TerminateProcess(child.0, 0xE1);
                    WaitForSingleObject(child.0, 5000);
                }
                return Err(denied("SCM Job attach before first instruction refused"));
            }
            if unsafe { ResumeThread(thread.0) } == u32::MAX {
                unsafe {
                    TerminateJobObject(job.0, 0xE2);
                    WaitForSingleObject(child.0, 5000);
                }
                return Err(denied("SCM-owned suspended worker resume refused"));
            }
            Ok(Self { job, child, child_thread: thread, pid: pi.pid,
                #[cfg(feature = "ssm-fixture")]
                original_fixture,
            })
        }
        fn alive(&self) -> bool {
            unsafe { WaitForSingleObject(self.child.0, 0) == WAIT_TIMEOUT }
        }
        fn stop_and_observe(self) -> bool {
            let wrote = unsafe { TerminateJobObject(self.job.0, 0xE3) } != 0;
            let waited = unsafe { WaitForSingleObject(self.child.0, 5000) } == WAIT_OBJECT_0;
            let mut empty = false;
            if wrote && waited {
                let until = Instant::now() + Duration::from_secs(3);
                while Instant::now() < until {
                    let mut record = JobAccounting::default();
                    let query = unsafe {
                        QueryInformationJobObject(self.job.0, 1,
                            (&mut record as *mut JobAccounting).cast(),
                            mem::size_of::<JobAccounting>() as u32,
                            ptr::null_mut())
                    };
                    if query != 0 && record.active_processes == 0 {
                        empty = true;
                        break;
                    }
                    thread::sleep(Duration::from_millis(20));
                }
            }
            let owned_stopped = wrote && waited && empty && self.pid > 0;
            #[cfg(feature = "ssm-fixture")]
            {
                if !owned_stopped {
                    #[cfg(feature = "r2-restricted-fixture")]
                    crate::r2_diagnostic::refused("stop_receipt","kernel job not empty");
                    return false;
                }
                let result=crate::ssm_fixture::record_stop(
                    &self.original_fixture,self.pid,
                    unsafe { GetCurrentProcessId() },empty);
                #[cfg(feature = "r2-restricted-fixture")]
                if let Err(ref e)=result {
                    crate::r2_diagnostic::refused("stop_receipt",&e.to_string());
                }
                return result.is_ok();
            }
            #[cfg(not(feature = "ssm-fixture"))]
            { owned_stopped }
        }
    }
    unsafe extern "system" fn service_main(_: u32, _: *mut *mut u16) {
        STOP.store(false, Ordering::Release);
        let name = wide(OsStr::new(NAME));
        let handle = unsafe {
            RegisterServiceCtrlHandlerExW(name.as_ptr(), Some(control), ptr::null_mut())
        };
        if handle.is_null() { return; }
        if report(handle, SERVICE_START_PENDING, 0).is_err() { return; }
        if require_local_system_session_zero().is_err() {
            let _ = report(handle, SERVICE_STOPPED, 1);
            return;
        }
        let keeper = match Keeper::start() {
            Ok(k) => k,
            Err(e) => {
                #[cfg(any(feature = "r2-restricted-fixture",
                           feature = "r3-appcontainer-fixture"))]
                crate::r2_diagnostic::refused("keeper_start",&e.to_string());
                #[cfg(not(any(feature = "r2-restricted-fixture",
                               feature = "r3-appcontainer-fixture")))]
                let _ = e;
                let _ = report(handle, SERVICE_STOPPED, 2);
                return;
            }
        };
        if report(handle, SERVICE_RUNNING, 0).is_err() {
            let _ = keeper.stop_and_observe();
            return;
        }
        // Deliberate service-only diagnostic lifecycle. No untrusted commands.
        let deadline = Instant::now() + Duration::from_secs(15);
        let mut abnormal = false;
        while !STOP.load(Ordering::Acquire) {
            if Instant::now() >= deadline {
                abnormal = true;
                break;
            }
            if !keeper.alive() {
                #[cfg(not(feature = "ssm-fixture"))]
                { abnormal = true; break; }
                #[cfg(feature = "ssm-fixture")]
                {
                    let mut code = u32::MAX;
                    let clean = unsafe {
                        GetExitCodeProcess(keeper.child.0,&mut code)
                    } != 0 && code == 0
                    && std::path::Path::new(env!("COG_R1_CI_OUTPUT")).is_file();
                    if !clean {
                        #[cfg(any(feature = "r2-restricted-fixture",
                                   feature = "r3-appcontainer-fixture"))]
                        crate::r2_diagnostic::refused("worker_exit",
                            &format!("fixed Python SSM exit code {}",code));
                        abnormal = true;
                        break;
                    }
                }
            }
            thread::sleep(Duration::from_millis(50));
        }
        let _ = report(handle, SERVICE_STOP_PENDING, 0);
        let empty = keeper.stop_and_observe();
        let _ = report(handle, SERVICE_STOPPED, if empty && !abnormal { 0 } else { 3 });
    }
    pub fn run() -> io::Result<()> {
        let mut name = wide(OsStr::new(NAME));
        let entries = [
            TableEntry { name: name.as_mut_ptr(), main: Some(service_main) },
            TableEntry { name: ptr::null_mut(), main: None },
        ];
        if unsafe { StartServiceCtrlDispatcherW(entries.as_ptr()) } == 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(())
    }
    pub fn fixed_child() {
        // Fixed diagnostic only. Production SSM data is intentionally absent.
        thread::sleep(Duration::from_secs(30));
    }
}
#[cfg(all(windows, feature = "acceptance-fixture"))]
fn main() {
    if std::env::args().nth(1).as_deref() == Some("--cognitum-fixed-custody-child") {
        win::fixed_child();
        return;
    }
    if win::run().is_err() { std::process::exit(1); }
}
#[cfg(not(all(windows, feature = "acceptance-fixture")))]
fn main() {
    eprintln!("Cognitum SCM requires genuine Windows and explicit acceptance-fixture build");
    std::process::exit(1);
}
