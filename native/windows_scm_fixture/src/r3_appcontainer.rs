//! R3 strict Windows AppContainer SSM launcher.
//!
//! ONLY a separately pinned, living, non-SYSTEM OS peer token
//! may be the origin. Service never copies its own SYSTEM token into child.
//! Installer must provision the exact AppContainer profile, signed runtime,
//! per-profile ACLs and peer publisher/creation identity independently.
//! No profile creation, no key creation, no arbitrary PID/argv, no handle
//! inheritance, no network AppContainer capabilities and no unrestricted
//! CreateProcessW fallback. Genuine kernel TokenIsAppContainer, SID and
//! non-SYSTEM TokenUser are checked before the suspended thread resumes.
//! CI's ephemeral peer is NOT an authenticated Core publisher/enrollment.
#![cfg(all(windows,feature="r3-appcontainer-fixture"))]
use std::{
    ffi::{c_void,OsStr},fs::{self,OpenOptions},io::{self,Write},mem,
    os::windows::ffi::OsStrExt,ptr,path::Path,
};
type Handle=*mut c_void;
const PROCESS_QUERY_LIMITED_INFORMATION:u32=0x1000;
const TOKEN_QUERY:u32=8;
const TOKEN_DUPLICATE:u32=2;
const TOKEN_ASSIGN_PRIMARY:u32=1;
const TOKEN_ALL_ACCESS:u32=0x000f01ff;
const SECURITY_IMPERSONATION:u32=2;
const TOKEN_PRIMARY:u32=1;
const DISABLE_MAX_PRIVILEGE:u32=1;
const LUA_TOKEN:u32=4;
const CREATE_SUSPENDED:u32=4;
const CREATE_NO_WINDOW:u32=0x0800_0000;
const EXTENDED_STARTUPINFO_PRESENT:u32=0x0008_0000;
const CREATE_UNICODE_ENVIRONMENT:u32=0x400;
const ATTRIBUTE_SECURITY_CAPABILITIES:usize=0x0002_0009;
const MAX_ATTR:usize=65536;
const MAX_IMAGE:usize=64*1024*1024;
#[repr(C)]
struct StartupInfo{
    cb:u32,reserved:*mut u16,desktop:*mut u16,title:*mut u16,
    x:u32,y:u32,width:u32,height:u32,chars_x:u32,chars_y:u32,
    fill:u32,flags:u32,show:u16,reserved2:u16,extra:*mut u8,
    stdin:Handle,stdout:Handle,stderr:Handle,
}
#[repr(C)]
struct StartupInfoEx{base:StartupInfo,attributes:Handle}
#[repr(C)]
struct ProbeProcessInfo{process:Handle,thread:Handle,pid:u32,tid:u32}

#[repr(C)]
struct SecurityCapabilities{sid:Handle,capabilities:Handle,count:u32,reserved:u32}
#[repr(C)]
#[derive(Default)]
struct FileTime{low:u32,high:u32}
#[link(name="kernel32")]
unsafe extern "system"{
    fn OpenProcess(access:u32,inherit:i32,pid:u32)->Handle;
    fn CloseHandle(handle:Handle)->i32;
    fn GetProcessId(process:Handle)->u32;
    fn GetProcessTimes(process:Handle,creation:*mut FileTime,exit:*mut FileTime,
        kernel:*mut FileTime,user:*mut FileTime)->i32;
    fn QueryFullProcessImageNameW(process:Handle,flags:u32,
        buffer:*mut u16,length:*mut u32)->i32;
    fn ProcessIdToSessionId(pid:u32,session:*mut u32)->i32;
    fn InitializeProcThreadAttributeList(list:Handle,count:u32,flags:u32,
        bytes:*mut usize)->i32;
    fn UpdateProcThreadAttribute(list:Handle,flags:u32,attribute:usize,
        value:Handle,size:usize,previous:Handle,returned:*mut usize)->i32;
    fn DeleteProcThreadAttributeList(list:Handle);
    fn TerminateProcess(process:Handle,code:u32)->i32;
    fn WaitForSingleObject(process:Handle,millis:u32)->u32;
    fn GetWindowsDirectoryW(buffer:*mut u16,size:u32)->u32;
    fn LocalFree(ptr:Handle)->Handle;
    fn GetFileAttributesW(filename:*const u16)->u32;
}
#[link(name="advapi32")]
unsafe extern "system"{
    fn OpenProcessToken(process:Handle,access:u32,token:*mut Handle)->i32;
    fn ImpersonateLoggedOnUser(token:Handle)->i32;
    fn RevertToSelf()->i32;
    fn DuplicateTokenEx(token:Handle,access:u32,security:Handle,
        level:u32,kind:u32,out:*mut Handle)->i32;
    fn CreateRestrictedToken(token:Handle,flags:u32,disable_count:u32,
        disabled:Handle,privilege_count:u32,privileges:Handle,
        restricting_count:u32,restricting:Handle,out:*mut Handle)->i32;
    fn GetTokenInformation(token:Handle,kind:u32,buffer:Handle,
        capacity:u32,required:*mut u32)->i32;
    fn ConvertSidToStringSidW(sid:Handle,output:*mut *mut u16)->i32;
    fn EqualSid(a:Handle,b:Handle)->i32;
    fn FreeSid(sid:Handle)->Handle;
    fn CreateProcessAsUserW(token:Handle,application:*const u16,command:*mut u16,
        pa:Handle,ta:Handle,inherit:i32,flags:u32,environment:Handle,
        directory:*const u16,startup:*const StartupInfo,process:Handle)->i32;
}
#[link(name="userenv")]
unsafe extern "system"{
    fn DeriveAppContainerSidFromAppContainerName(name:*const u16,
        sid:*mut Handle)->i32;
    fn CreateEnvironmentBlock(env:*mut Handle,user_token:Handle,
        inherit_current:i32)->i32;
    fn DestroyEnvironmentBlock(env:Handle)->i32;
}
fn denied(why:&str)->io::Error{
    io::Error::new(io::ErrorKind::PermissionDenied,why.to_owned())
}
fn wide(value:&OsStr)->Vec<u16>{
    value.encode_wide().chain(std::iter::once(0)).collect()
}
fn hex(bytes:&[u8])->String{
    const D:&[u8]=b"0123456789abcdef";
    let mut result=String::with_capacity(bytes.len()*2);
    for b in bytes {result.push(D[(b>>4) as usize] as char);result.push(D[(b&15) as usize] as char);}
    result
}
struct Owned(Handle);
impl Drop for Owned{fn drop(&mut self){if !self.0.is_null(){
    unsafe{CloseHandle(self.0);}
}}}
struct OwnedSid(Handle);
impl Drop for OwnedSid{fn drop(&mut self){if !self.0.is_null(){
    unsafe{FreeSid(self.0);}
}}}
struct OwnedLocal(Handle);
impl Drop for OwnedLocal{fn drop(&mut self){if !self.0.is_null(){
    unsafe{LocalFree(self.0);}
}}}
/// Resolve the image/CWD as its user, then ALWAYS revert to SCM identity.
struct UserImpersonation{ active:bool }
impl UserImpersonation{
    fn begin(token:Handle)->io::Result<Self>{
        if unsafe{ImpersonateLoggedOnUser(token)}==0{
            return Err(denied("pinned non-SYSTEM user impersonation refused"));
        }
        Ok(Self{active:true})
    }
    fn end(mut self)->io::Result<()>{
        if unsafe{RevertToSelf()}==0{
            return Err(denied("SCM failed to revert original-user impersonation"));
        }
        self.active=false;
        Ok(())
    }
}
impl Drop for UserImpersonation{
    fn drop(&mut self){
        if self.active && unsafe{RevertToSelf()}==0{
            std::process::abort();
        }
    }
}
struct Attr{bytes:Vec<usize>,ready:bool}
impl Attr{
    fn new()->io::Result<Self>{
        let mut size=0usize;
        unsafe{InitializeProcThreadAttributeList(ptr::null_mut(),1,0,&mut size);}
        if size==0||size>MAX_ATTR {return Err(denied("AppContainer attributes unavailable"));}
        let mut this=Self{bytes:vec![0usize;size.div_ceil(mem::size_of::<usize>())],ready:false};
        if unsafe{InitializeProcThreadAttributeList(this.raw(),1,0,&mut size)}==0{
            return Err(io::Error::last_os_error());
        }
        this.ready=true;
        Ok(this)
    }
    fn raw(&mut self)->Handle{self.bytes.as_mut_ptr().cast()}
}
impl Drop for Attr{fn drop(&mut self){if self.ready{
    unsafe{DeleteProcThreadAttributeList(self.raw());}
}}}
fn token_data(token:Handle,kind:u32)->io::Result<Vec<usize>>{
    let mut size=0u32;
    unsafe{GetTokenInformation(token,kind,ptr::null_mut(),0,&mut size);}
    if size==0||size>4096{return Err(denied("native worker OS token claim unavailable"));}
    let mut words=vec![0usize;(size as usize).div_ceil(mem::size_of::<usize>())];
    if unsafe{GetTokenInformation(token,kind,words.as_mut_ptr().cast(),
       size,&mut size)}==0{
        return Err(denied("native worker OS token query refused"));
    }
    Ok(words)
}
fn string_sid(sid:Handle)->io::Result<String>{
    if sid.is_null(){return Err(denied("zero OS user/package SID"));}
    let mut raw: *mut u16=ptr::null_mut();
    if unsafe{ConvertSidToStringSidW(sid,&mut raw)}==0||raw.is_null(){
        return Err(denied("cannot verify OS user/package SID"));
    }
    let _owned=OwnedLocal(raw.cast());
    let mut len=0usize;
    while len<256 && unsafe{*raw.add(len)}!=0 {len+=1;}
    if len==0||len>=256{return Err(denied("unbounded OS user SID"));}
    Ok(String::from_utf16_lossy(unsafe{std::slice::from_raw_parts(raw,len)}))
}
fn user_sid(token:Handle)->io::Result<String>{
    let buffer=token_data(token,1)?; // TokenUser is SID_AND_ATTRIBUTES
    let sid=unsafe{*(buffer.as_ptr() as *const Handle)};
    string_sid(sid)
}
fn require_nonadmin_token(token:Handle)->io::Result<()>{
    // TokenElevation comes from actual Windows TOKEN_ELEVATION, never a
    // caller-provided enrollment JSON flag or unverified account name.
    let body=token_data(token,20)?;
    let elevation=unsafe{*(body.as_ptr() as *const u32)};
    if elevation!=0{
        return Err(denied("original peer or child remains an elevated administrator"));
    }
    let sid=user_sid(token)?;
    if !sid.starts_with("S-1-5-21-"){
        return Err(denied("only separately provisioned local user token admitted"));
    }
    Ok(())
}
fn process_birth(process:Handle)->io::Result<u64>{
    let mut creation=FileTime::default();
    let mut exit=FileTime::default();
    let mut kernel=FileTime::default();
    let mut user=FileTime::default();
    if unsafe{GetProcessTimes(process,&mut creation,&mut exit,&mut kernel,&mut user)}==0{
        return Err(denied("pinned original peer kernel generation unavailable"));
    }
    let birth=(u64::from(creation.high)<<32)|u64::from(creation.low);
    if birth==0{return Err(denied("zero original peer creation FILETIME"));}
    Ok(birth)
}
fn pinned_peer()->io::Result<(Owned,Owned,u64)>{
    let pid:u32=env!("COG_R3_CI_PEER_PID").parse()
        .map_err(|_|denied("no externally pinned original peer PID"))?;
    if pid==0{return Err(denied("zero pinned original peer"));}
    let raw=unsafe{OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,0,pid)};
    if raw.is_null(){return Err(denied("original approved non-System peer not alive"));}
    let process=Owned(raw);
    if unsafe{GetProcessId(process.0)}!=pid{
        return Err(denied("process PID does not match original pinned peer"));
    }
    let birth=process_birth(process.0)?;
    let pinned_birth:u64=env!("COG_R3_CI_PEER_BIRTH").parse()
        .map_err(|_|denied("original kernel peer generation not pinned"))?;
    if birth!=pinned_birth{
        return Err(denied("original peer process creation differs from installer pin"));
    }
    let mut session=u32::MAX;
    if unsafe{ProcessIdToSessionId(pid,&mut session)}==0||
       session==u32::MAX{
        return Err(denied("pinned peer process session identity unavailable"));
    }
    // A dedicated non-SYSTEM service user may legitimately be in session 0.
    // Require separately pinned OS TokenUser SID, AppContainer package SID,
    // kernel creation time and approved executable digest; never SYSTEM.
    let mut path=vec![0u16;32768];
    let mut size=path.len() as u32;
    if unsafe{QueryFullProcessImageNameW(process.0,0,path.as_mut_ptr(),&mut size)}==0||
       size==0||size as usize>=path.len(){
        return Err(denied("original user process executable absent"));
    }
    let name=String::from_utf16(&path[..size as usize])
        .map_err(|_|denied("peer executable path invalid"))?;
    let bytes=fs::read(&name).map_err(|_|denied("approved peer image unreadable"))?;
    if bytes.is_empty()||bytes.len()>MAX_IMAGE||
       hex(&crate::r2_signer::r3_sha_image(&bytes)?)!=env!("COG_R3_CI_PEER_IMAGE_SHA256"){
        return Err(denied("original user process image SHA does not match independent pin"));
    }
    let mut rawtoken=ptr::null_mut();
    if unsafe{OpenProcessToken(process.0,TOKEN_QUERY|TOKEN_DUPLICATE|
        TOKEN_ASSIGN_PRIMARY,&mut rawtoken)}==0||rawtoken.is_null(){
        return Err(denied("approved original user OS primary token unavailable"));
    }
    let token=Owned(rawtoken);
    require_nonadmin_token(token.0)?;
    let sid=user_sid(token.0)?;
    if sid=="S-1-5-18"||sid=="S-1-5-7"||
       sid!=env!("COG_R3_CI_PEER_SID"){
        return Err(denied("original user is SYSTEM/anonymous/wrong pinned SID"));
    }
    Ok((process,token,birth))
}

fn witness_original_appcontainer(child:Handle,profile_sid:&str,
                                 source_birth:u64)->io::Result<()>{
    let destination=Path::new(env!("COG_R3_CI_APP_WITNESS"));
    if !destination.is_absolute()||destination.exists()||destination.is_symlink(){
        return Err(denied("original AppContainer kernel witness path reused or unsafe"));
    }
    let worker_pid=unsafe{GetProcessId(child)};
    let child_birth=process_birth(child)?;
    if worker_pid==0||worker_pid==env!("COG_R3_CI_PEER_PID").parse::<u32>().unwrap_or(0)
        ||child_birth==0||child_birth==source_birth{
        return Err(denied("original OS AppContainer worker process not distinct"));
    }
    let record=format!(
      "{{\"schema\":\"cognitum.ssm.r3.original_appcontainer_kernel_witness.v1\",\"source_user_sid\":\"{}\",\"appcontainer_sid\":\"{}\",\"original_peer_birth\":{},\"worker_pid\":{},\"worker_birth\":{},\"native_TokenIsAppContainer\":true,\"native_TokenUser_is_SYSTEM\":false,\"native_TokenElevation_is_zero\":true,\"checked_before_worker_resume\":true,\"installed_Core_enrollment\":false,\"production_publisher_approved\":false,\"output_release_authorized\":false}}\n",
      env!("COG_R3_CI_PEER_SID"),profile_sid,source_birth,worker_pid,child_birth
    );
    if record.len()>2048{return Err(denied("bounded OS AppContainer witness overflow"));}
    let mut writer=OpenOptions::new().create_new(true).write(true).open(destination)?;
    writer.write_all(record.as_bytes())?;
    writer.sync_all()?;
    Ok(())
}

/// Windows userenv owns the target *user's* profile environment. An SCM
/// process must not construct a four-variable pseudo-environment: Windows
/// AppContainer creation depends on the real user's profile variables and
/// package namespace setup. bInherit=FALSE forbids leaking SCM credentials.
struct TargetProfileEnvironment{
    original:Handle,
    filtered:Vec<u16>,
}
impl Drop for TargetProfileEnvironment{
    fn drop(&mut self){
        if !self.original.is_null(){
            unsafe{DestroyEnvironmentBlock(self.original);}
        }
    }
}
fn windows_environment(user:Handle)->io::Result<TargetProfileEnvironment>{
    let mut raw=ptr::null_mut();
    if unsafe{CreateEnvironmentBlock(&mut raw,user,0)}==0||raw.is_null(){
        return Err(denied("Windows refused noninherited profile environment for original user"));
    }
    let mut target=TargetProfileEnvironment{
        original:raw,
        filtered:Vec::with_capacity(4096),
    };
    // Use the genuine target user's OS profile block, not a four-field
    // pseudo-environment. Never hand its privileged CI/SCM-like names to the
    // lowbox: copy only bounded, vetted entries into a second private block.
    // Neither log nor serialize any environment VALUE.
    let wchar=raw as *const u16;
    let mut offset=0usize;
    let mut seen=std::collections::BTreeSet::new();
    let mut ended=false;
    while offset<32768{
        let start=offset;
        while offset<32768&&unsafe{*wchar.add(offset)}!=0{offset+=1;}
        if offset>=32768{return Err(denied("unbounded OS user profile environment"));}
        if offset==start{
            ended=true;
            break;
        }
        let line=String::from_utf16(unsafe{
            std::slice::from_raw_parts(wchar.add(start),offset-start)
        }).map_err(|_|denied("profile environment variable malformed"))?;
        let (name,_value)=line.split_once('=')
            .ok_or_else(||denied("malformed original user environment entry"))?;
        // Windows allows drive-working-directory =C: pseudo-entries. They do
        // not authorize filesystem access and are not required for this run.
        if !name.is_empty(){
            let key=name.to_ascii_uppercase();
            // Cognitum's own host-owned fields are NEVER permitted in a
            // separately enrolled user profile, even if we could omit them.
            if key.starts_with("COG_"){
                return Err(denied("SCM Cognitum field escaped into original user profile"));
            }
            // On hosted Windows, genuine machine/user profile blocks can
            // include CI variables. Do not copy these, nor any password,
            // token or secret-bearing names, to the nonadmin AppContainer.
            let forbidden=key.starts_with("GITHUB_")||
                key.starts_with("GH_")||key.starts_with("ACTIONS_")||
                key.contains("PASSWORD")||key.contains("SECRET")||
                key.contains("TOKEN");
            if !forbidden{
                if !seen.insert(key){
                    return Err(denied("duplicate target user environment variable"));
                }
                target.filtered.extend_from_slice(unsafe{
                    std::slice::from_raw_parts(wchar.add(start),offset-start)
                });
                target.filtered.push(0);
                if target.filtered.len()>=32768{
                    return Err(denied("sanitized user environment exceeds bound"));
                }
            }
        }
        // Ignore drive-current-directory =C: pseudo-entries: absolute
        // application, script and CWD pins are mandatory for this worker.
        offset+=1;
    }
    if !ended{
        return Err(denied("unterminated target user profile environment"));
    }
    for required in ["SYSTEMROOT","USERPROFILE","LOCALAPPDATA","APPDATA"]{
        if !seen.contains(required){
            return Err(denied("native original AppContainer user profile variable missing"));
        }
    }
    // Every retained entry already has one NUL. A final NUL terminates
    // the Windows Unicode environment block without copying excluded values.
    target.filtered.push(0);
    Ok(target)
}
/// Must be called while worker is still SUSPENDED; caller must attach
/// to SCM's original kill-on-close Job BEFORE primary thread resume.
/// If any OS proof fails, child is synchronously killed and reaped.
pub fn launch(application:&[u16],command:&mut[u16],
              _original_startup:*const c_void,output:*mut c_void)->io::Result<()>{
    let (peer,orig,birth)=pinned_peer()?;
    let mut duplicated=ptr::null_mut();
    if unsafe{DuplicateTokenEx(orig.0,TOKEN_ALL_ACCESS,ptr::null_mut(),
        SECURITY_IMPERSONATION,TOKEN_PRIMARY,&mut duplicated)}==0||
       duplicated.is_null(){
        return Err(denied("non-System original user primary token duplication denied"));
    }
    let duplicated=Owned(duplicated);
    let mut reduced=ptr::null_mut();
    // The R3-R1 installer-style source is already an independently checked
    // NONADMIN local account; LUA_TOKEN is intended to downgrade admins and
    // can disturb a genuine standard-user profile. Remove ALL privileges,
    // retain the nonadmin TokenUser, and require actual TokenElevation=0.
    #[cfg(feature = "r3-r1-frozen-fixture")]
    let restrictions=DISABLE_MAX_PRIVILEGE;
    #[cfg(not(feature = "r3-r1-frozen-fixture"))]
    let restrictions=DISABLE_MAX_PRIVILEGE|LUA_TOKEN;
    if unsafe{CreateRestrictedToken(duplicated.0,
        restrictions,0,ptr::null_mut(),0,ptr::null_mut(),
        0,ptr::null_mut(),&mut reduced)}==0||reduced.is_null(){
        return Err(denied("AppContainer caller token not reduced from approved user"));
    }
    let reduced=Owned(reduced);
    require_nonadmin_token(reduced.0)?;
    if user_sid(reduced.0)?!=env!("COG_R3_CI_PEER_SID"){
        return Err(denied("reduced AppContainer caller user identity differs"));
    }
    let profile=env!("COG_R3_CI_PROFILE");
    if profile!="CognitumSsmR3CiSandboxV1"{
        return Err(denied("noncanonical installed profile name refused"));
    }
    let mut sid=ptr::null_mut();
    if unsafe{DeriveAppContainerSidFromAppContainerName(
        wide(OsStr::new(profile)).as_ptr(),&mut sid)}!=0||sid.is_null(){
        return Err(denied("independently provisioned AppContainer SID not derivable"));
    }
    let sid=OwnedSid(sid);
    if string_sid(sid.0)?!=env!("COG_R3_CI_APP_SID"){
        return Err(denied("AppContainer profile is not installer-pinned"));
    }
    let caps=SecurityCapabilities{sid:sid.0,capabilities:ptr::null_mut(),
        count:0,reserved:0}; // no internetClient/network/privateNetwork capability
    let mut attrs=Attr::new()?;
    if unsafe{UpdateProcThreadAttribute(attrs.raw(),0,
        ATTRIBUTE_SECURITY_CAPABILITIES,
        (&caps as *const SecurityCapabilities).cast_mut().cast(),
        mem::size_of::<SecurityCapabilities>(),ptr::null_mut(),ptr::null_mut())}==0{
        return Err(denied("Windows refused AppContainer launch capability attribute"));
    }
    let mut startup:StartupInfoEx=unsafe{mem::zeroed()};
    startup.base.cb=mem::size_of::<StartupInfoEx>() as u32;
    startup.attributes=attrs.raw();
    let env=windows_environment(orig.0)?;
    // Never inherit SCM's working directory or drive-relative mappings.
    let image=Path::new(env!("COG_R1_CI_PYTHON"));
    let cwd=image.parent().ok_or_else(||denied("pinned image parent missing"))?;
    if !image.is_absolute()||!image.is_file()||image.is_symlink()||
       !cwd.is_dir()||cwd.is_symlink(){
        return Err(denied("original pinned image/CWD unavailable"));
    }
    let wide_cwd=wide(cwd.as_os_str());
    let impersonated=UserImpersonation::begin(reduced.0)?;
    // Visibility under the original user is only a diagnostic, NOT a lowbox
    // AppContainer proof or permission to run an unrestricted child.
    let user_image_visible=unsafe{GetFileAttributesW(application.as_ptr())}!=u32::MAX;
    let launched=unsafe{CreateProcessAsUserW(reduced.0,application.as_ptr(),
        command.as_mut_ptr(),ptr::null_mut(),ptr::null_mut(),0,
        CREATE_SUSPENDED|CREATE_NO_WINDOW|EXTENDED_STARTUPINFO_PRESENT|
            CREATE_UNICODE_ENVIRONMENT,
        env.filtered.as_ptr().cast_mut().cast(),wide_cwd.as_ptr(),&startup.base,
        output)};
    let launch_error=if launched==0{Some(io::Error::last_os_error())}else{None};
    if impersonated.end().is_err(){
        if launched!=0{
            let unsafe_child=unsafe{*(output as *const Handle)};
            if !unsafe_child.is_null(){
                unsafe{TerminateProcess(unsafe_child,0xE7);
                       WaitForSingleObject(unsafe_child,5000);}
            }
        }
        return Err(denied("SCM failed closed when restoring its SYSTEM identity"));
    }
    if let Some(err)=launch_error{
        // Exact same image, non-SYSTEM user token, environment and CWD.
        // No AppContainer package attribute *only for a terminated SUSPENDED
        // diagnostic probe*. Never resume this probe or return its handles
        // as an alternative worker. This distinguishes target-user filesystem
        // resolution from AppContainer package/namespace setup.
        let mut baseline_startup:StartupInfo=unsafe{mem::zeroed()};
        baseline_startup.cb=mem::size_of::<StartupInfo>() as u32;
        let mut probe:ProbeProcessInfo=unsafe{mem::zeroed()};
        let mut probe_command=command.to_vec();
        let base_created=unsafe{CreateProcessAsUserW(
            reduced.0,application.as_ptr(),probe_command.as_mut_ptr(),
            ptr::null_mut(),ptr::null_mut(),0,
            CREATE_SUSPENDED|CREATE_NO_WINDOW|CREATE_UNICODE_ENVIRONMENT,
            env.filtered.as_ptr().cast_mut().cast(),wide_cwd.as_ptr(),
            &baseline_startup,(&mut probe as *mut ProbeProcessInfo).cast()
        )}!=0;
        let base_error=if base_created{0}else{
            io::Error::last_os_error().raw_os_error().unwrap_or(-1)
        };
        if base_created{
            // Before any untrusted user code can execute, terminate, await
            // death and close BOTH original native handles.
            if probe.process.is_null()||probe.thread.is_null(){
                std::process::abort();
            }
            if unsafe{TerminateProcess(probe.process,0xE8)}==0||
               unsafe{WaitForSingleObject(probe.process,5000)}!=0{
                std::process::abort();
            }
            unsafe{CloseHandle(probe.thread);
                   CloseHandle(probe.process);}
        }
        return Err(denied(&format!(
            "AppContainer CreateProcessAsUserW OS {}; original_user_image_visible={}; suspended_nonlowbox_probe_created_and_reaped={}; nonlowbox_error={}",
            err,user_image_visible,base_created,base_error
        )));
    }
    // Caller owns process+thread HANDLEs, original PID and Job after success.
    let child=unsafe{*(output as *const Handle)};
    let mut token=ptr::null_mut();
    let checked=(||{
        if child.is_null()||
           unsafe{OpenProcessToken(child,TOKEN_QUERY,&mut token)}==0||
           token.is_null(){
            return Err(denied("AppContainer suspended SSM process token unavailable"));
        }
        let tok=Owned(token);
        token=ptr::null_mut();
        require_nonadmin_token(tok.0)?;
        if user_sid(tok.0)?!=env!("COG_R3_CI_PEER_SID"){
            return Err(denied("AppContainer child did not retain non-System original user"));
        }
        let app=token_data(tok.0,29)?; // TokenIsAppContainer
        if app[0] as u32!=1{return Err(denied("child was not a real Windows AppContainer"));}
        let package=token_data(tok.0,31)?; // TokenAppContainerSid -> SID_AND_ATTRIBUTES
        let actual=unsafe{*(package.as_ptr() as *const Handle)};
        if actual.is_null()||unsafe{EqualSid(actual,sid.0)}==0{
            return Err(denied("child AppContainer SID differs from installer profile"));
        }
        if process_birth(peer.0)?!=birth{
            return Err(denied("source peer changed while opening original process"));
        }
        witness_original_appcontainer(child,&string_sid(sid.0)?,birth)?;
        Ok(())
    })();
    if checked.is_err(){
        unsafe{
            TerminateProcess(child,0xE5);
            WaitForSingleObject(child,5000);
        }
    }
    checked
}
