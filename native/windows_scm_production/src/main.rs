//! R3-R1 genuine Windows SCM **production bootstrap**, not the CI fixture.
//! This is a separately named, independently packaged SYSTEM supervisor.
//! Until the Core issuer, protected worker and signer are provisioned it
//! accepts NO operations and launches NO child. Its sole current purpose is
//! genuine SCM lifecycle ownership and fail-closed stop handling.
//! Signing, installer, grants and physical acceptance are separate gates.
#![deny(unsafe_op_in_unsafe_fn)]
#[cfg(windows)]
mod service {
    use std::{ffi::{c_void,OsStr},io,mem,os::windows::ffi::OsStrExt,
        ptr,sync::atomic::{AtomicBool,Ordering},
        thread,time::Duration};

    type Handle=*mut c_void;
    const SERVICE:&str="CognitumSsmSupervisorV1";
    const OWN_PROCESS:u32=0x10;
    const STOPPED:u32=1;
    const START_PENDING:u32=2;
    const STOP_PENDING:u32=3;
    const RUNNING:u32=4;
    const ACCEPT_STOP:u32=1;
    const ACCEPT_SHUTDOWN:u32=4;
    const CONTROL_STOP:u32=1;
    const CONTROL_INTERROGATE:u32=4;
    const CONTROL_SHUTDOWN:u32=5;
    const ERROR_CALL_NOT_IMPLEMENTED:u32=120;
    const TOKEN_QUERY:u32=8;
    const TOKEN_USER:u32=1;
    const WIN_LOCAL_SYSTEM_SID:u32=22;
    const JOB_EXTENDED_LIMIT_INFORMATION:u32=9;
    const JOB_BASIC_ACCOUNTING_INFORMATION:u32=1;
    const JOB_LIMIT_KILL_ON_JOB_CLOSE:u32=0x2000;
    static STOP:AtomicBool=AtomicBool::new(false);

    #[repr(C)]
    #[derive(Clone,Copy,Default)]
    struct ServiceStatus {
        service_type:u32,current_state:u32,controls_accepted:u32,
        win32_exit_code:u32,service_specific_exit_code:u32,
        checkpoint:u32,wait_hint:u32,
    }
    #[repr(C)]
    struct TableEntry {
        name:*mut u16,main:Option<unsafe extern "system" fn(u32,*mut *mut u16)>,
    }
    #[repr(C)]
    #[derive(Default)]
    struct BasicLimit {
        process_time:i64,job_time:i64,flags:u32,min_working:usize,
        max_working:usize,active_limit:u32,affinity:usize,
        priority:u32,scheduling:u32,
    }
    #[repr(C)]
    #[derive(Default)]
    struct IoCounters {
        reads:u64,writes:u64,other:u64,read_bytes:u64,write_bytes:u64,other_bytes:u64,
    }
    #[repr(C)]
    #[derive(Default)]
    struct ExtLimit {
        basic:BasicLimit,io:IoCounters,
        process_memory:usize,job_memory:usize,
        peak_process_memory:usize,peak_job_memory:usize,
    }
    #[repr(C)]
    #[derive(Default)]
    struct JobAccounting {
        total_user_time:i64,total_kernel_time:i64,
        this_user_time:i64,this_kernel_time:i64,
        page_faults:u32,total_processes:u32,active_processes:u32,
        terminated_processes:u32,
    }
    #[link(name="advapi32")]
    unsafe extern "system" {
        fn StartServiceCtrlDispatcherW(table:*const TableEntry)->i32;
        fn RegisterServiceCtrlHandlerExW(name:*const u16,
            handler:Option<unsafe extern "system" fn(u32,u32,Handle,Handle)->u32>,
            context:Handle)->Handle;
        fn SetServiceStatus(handle:Handle,status:*const ServiceStatus)->i32;
        fn OpenProcessToken(process:Handle,rights:u32,token:*mut Handle)->i32;
        fn GetTokenInformation(token:Handle,kind:u32,data:Handle,len:u32,
            out_len:*mut u32)->i32;
        fn IsWellKnownSid(sid:Handle,kind:u32)->i32;
    }
    #[link(name="kernel32")]
    unsafe extern "system" {
        fn GetCurrentProcess()->Handle;
        fn GetCurrentProcessId()->u32;
        fn ProcessIdToSessionId(pid:u32,session:*mut u32)->i32;
        fn CreateJobObjectW(attributes:Handle,name:*const u16)->Handle;
        fn SetInformationJobObject(job:Handle,kind:u32,details:Handle,len:u32)->i32;
        fn QueryInformationJobObject(job:Handle,kind:u32,details:Handle,len:u32,
            returned:*mut u32)->i32;
        fn CloseHandle(handle:Handle)->i32;
    }
    struct Owned(Handle);
    impl Drop for Owned {
        fn drop(&mut self) {
            if !self.0.is_null() {unsafe {CloseHandle(self.0);}}
        }
    }
    fn protected_system_session()->io::Result<()> {
        let mut raw:Handle=ptr::null_mut();
        if unsafe {OpenProcessToken(GetCurrentProcess(),TOKEN_QUERY,&mut raw)}==0 ||
           raw.is_null() {
            return Err(io::Error::last_os_error());
        }
        let token=Owned(raw);
        let mut bytes=0u32;
        unsafe {GetTokenInformation(token.0,TOKEN_USER,ptr::null_mut(),0,&mut bytes);}
        if bytes<(mem::size_of::<usize>() as u32) || bytes>4096 {
            return Err(io::Error::new(io::ErrorKind::PermissionDenied,"unknown SCM TokenUser"));
        }
        let mut aligned=vec![0usize;(bytes as usize).div_ceil(mem::size_of::<usize>())];
        if unsafe {GetTokenInformation(token.0,TOKEN_USER,aligned.as_mut_ptr().cast(),
                                       bytes,&mut bytes)}==0 {
            return Err(io::Error::last_os_error());
        }
        let sid=unsafe {*(aligned.as_ptr() as *const Handle)};
        if sid.is_null() || unsafe {IsWellKnownSid(sid,WIN_LOCAL_SYSTEM_SID)}==0 {
            return Err(io::Error::new(io::ErrorKind::PermissionDenied,"SCM SYSTEM required"));
        }
        let mut session=u32::MAX;
        if unsafe {ProcessIdToSessionId(GetCurrentProcessId(),&mut session)}==0 ||
           session!=0 {
            return Err(io::Error::new(io::ErrorKind::PermissionDenied,"SCM session zero required"));
        }
        Ok(())
    }
    fn empty_kill_on_close_job()->io::Result<Owned> {
        let handle=unsafe {CreateJobObjectW(ptr::null_mut(),ptr::null())};
        if handle.is_null(){return Err(io::Error::last_os_error());}
        let job=Owned(handle);
        let mut limit=ExtLimit::default();
        limit.basic.flags=JOB_LIMIT_KILL_ON_JOB_CLOSE;
        if unsafe {SetInformationJobObject(job.0,JOB_EXTENDED_LIMIT_INFORMATION,
                 (&mut limit as *mut ExtLimit).cast(),mem::size_of::<ExtLimit>() as u32)}==0 {
            return Err(io::Error::last_os_error());
        }
        assert_no_workers(&job)?;
        Ok(job)
    }
    fn assert_no_workers(job:&Owned)->io::Result<()> {
        let mut counter=JobAccounting::default();
        if unsafe {QueryInformationJobObject(job.0,JOB_BASIC_ACCOUNTING_INFORMATION,
                   (&mut counter as *mut JobAccounting).cast(),
                   mem::size_of::<JobAccounting>() as u32,ptr::null_mut())}==0 {
            return Err(io::Error::last_os_error());
        }
        if counter.active_processes!=0 || counter.total_processes!=0 {
            return Err(io::Error::new(io::ErrorKind::PermissionDenied,
                "unapproved process entered production supervisor Job"));
        }
        Ok(())
    }
    fn report(handle:Handle,state:u32,code:u32)->io::Result<()> {
        let status=ServiceStatus {
            service_type:OWN_PROCESS,current_state:state,
            controls_accepted:if state==RUNNING {ACCEPT_STOP|ACCEPT_SHUTDOWN}else{0},
            win32_exit_code:if state==STOPPED && code!=0 {1066}else{0},
            service_specific_exit_code:code,
            checkpoint:if state==START_PENDING || state==STOP_PENDING {1}else{0},
            wait_hint:if state==START_PENDING || state==STOP_PENDING {8000}else{0},
        };
        if unsafe {SetServiceStatus(handle,&status)}==0 {
            Err(io::Error::last_os_error())
        }else{Ok(())}
    }
    unsafe extern "system" fn control(code:u32,_event:u32,
        _data:Handle,_context:Handle)->u32 {
        match code {
            CONTROL_STOP|CONTROL_SHUTDOWN=>{
                STOP.store(true,Ordering::Release);0
            }
            CONTROL_INTERROGATE=>0,
            _=>ERROR_CALL_NOT_IMPLEMENTED,
        }
    }
    unsafe extern "system" fn service_main(_argc:u32,_argv:*mut *mut u16) {
        STOP.store(false,Ordering::Release);
        let name=wide(OsStr::new(SERVICE));
        let handle=unsafe {RegisterServiceCtrlHandlerExW(
            name.as_ptr(),Some(control),ptr::null_mut())};
        if handle.is_null(){return;}
        if report(handle,START_PENDING,0).is_err(){return;}
        if protected_system_session().is_err(){
            let _=report(handle,STOPPED,1);return;
        }
        let job=match empty_kill_on_close_job(){
            Ok(job)=>job,Err(_)=>{
                let _=report(handle,STOPPED,2);return;
            }
        };
        if report(handle,RUNNING,0).is_err(){return;}
        // No named-pipe endpoint and no mathematical operation. Only the
        // externally accepted Lu Core operation bridge may later unlock work.
        let mut failed=false;
        while !STOP.load(Ordering::Acquire) {
            if assert_no_workers(&job).is_err(){failed=true;break;}
            thread::sleep(Duration::from_millis(100));
        }
        let _=report(handle,STOP_PENDING,0);
        if assert_no_workers(&job).is_err(){failed=true;}
        drop(job); // kill-on-close remains armed; no child is ever launched.
        let _=report(handle,STOPPED,if failed{3}else{0});
    }
    fn wide(s:&OsStr)->Vec<u16>{
        use std::iter::once;
        s.encode_wide().chain(once(0)).collect()
    }
    pub fn run()->io::Result<()> {
        let mut name=wide(OsStr::new(SERVICE));
        let table=[
            TableEntry{name:name.as_mut_ptr(),main:Some(service_main)},
            TableEntry{name:ptr::null_mut(),main:None},
        ];
        if unsafe {StartServiceCtrlDispatcherW(table.as_ptr())}==0 {
            Err(io::Error::last_os_error())
        }else{Ok(())}
    }
}
#[cfg(windows)]
fn main(){
    if service::run().is_err(){std::process::exit(1);}
}
#[cfg(not(windows))]
fn main() {
    eprintln!("Cognitum production SCM bootstrap requires genuine Windows");
    std::process::exit(1);
}
