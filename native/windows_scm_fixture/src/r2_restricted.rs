//! R2 native restricted-token launch: no LocalSystem-token fallback.
//!
//! In CI this starts from a LocalSystem SCM service token but disables its
//! privileges and adds a real Windows restricting SID (BUILTIN\Users).
//! Windows must report IsTokenRestricted on the PRIMARY child process token
//! before the suspended main thread can be assigned and resumed.
//! TokenUser remains SYSTEM: this is NOT an AppContainer or an approved
//! production sandbox. Production must use a separately pinned low-privilege
//! Core peer/AppContainer and installer-controlled access to Python/data.
//! This source is compiled only with explicit r2-restricted-fixture feature.
#![cfg(all(windows, feature="r2-restricted-fixture"))]
use std::{ffi::c_void,io,ptr,mem};
type Handle=*mut c_void;
const TOKEN_QUERY:u32=0x8;
const TOKEN_DUPLICATE:u32=0x2;
const TOKEN_ALL_ACCESS:u32=0x000f01ff;
const SECURITY_IMPERSONATION:u32=2;
const TOKEN_PRIMARY:u32=1;
const DISABLE_MAX_PRIVILEGE:u32=1;
const CREATE_SUSPENDED:u32=4;
const CREATE_NO_WINDOW:u32=0x08000000;
const WIN_BUILTIN_USERS_SID:u32=27;
#[repr(C)]
struct SidAndAttributes { sid:Handle,attributes:u32 }
#[link(name="advapi32")]
unsafe extern "system" {
    fn OpenProcessToken(process:Handle,access:u32,token:*mut Handle)->i32;
    fn DuplicateTokenEx(existing:Handle,access:u32,sa:Handle,impersonation:u32,
                        kind:u32,out:*mut Handle)->i32;
    fn CreateRestrictedToken(existing:Handle,flags:u32,disable_count:u32,
        disable:Handle,privilege_count:u32,privileges:Handle,
        restrict_count:u32,restrict:Handle,out:*mut Handle)->i32;
    fn CreateWellKnownSid(kind:u32,domain:Handle,sid:Handle,size:*mut u32)->i32;
    fn IsTokenRestricted(token:Handle)->i32;
    fn CreateProcessAsUserW(token:Handle,application:*const u16,command:*mut u16,
        pa:Handle,ta:Handle,inherit:i32,flags:u32,environment:Handle,
        directory:*const u16,startup:Handle,process_info:Handle)->i32;
    fn GetTokenInformation(token:Handle,kind:u32,data:Handle,length:u32,
                           actual:*mut u32)->i32;
}
#[link(name="kernel32")]
unsafe extern "system" {
    fn GetCurrentProcess()->Handle;
    fn CloseHandle(handle:Handle)->i32;
}
struct Owned(Handle);
impl Drop for Owned {fn drop(&mut self){if !self.0.is_null(){
    unsafe{CloseHandle(self.0);}
}}}
fn refused(reason:&'static str)->io::Error{
    io::Error::new(io::ErrorKind::PermissionDenied,reason)
}
fn primary_restricted()->io::Result<Owned>{
    let mut original=ptr::null_mut();
    if unsafe{OpenProcessToken(GetCurrentProcess(),
             TOKEN_QUERY|TOKEN_DUPLICATE,&mut original)}==0||original.is_null(){
        return Err(refused("SCM restricted child: service token missing"));
    }
    let original=Owned(original);
    let mut duplicate=ptr::null_mut();
    if unsafe{DuplicateTokenEx(original.0,TOKEN_ALL_ACCESS,ptr::null_mut(),
             SECURITY_IMPERSONATION,TOKEN_PRIMARY,&mut duplicate)}==0||
             duplicate.is_null(){
        return Err(refused("SCM restricted child: token duplication denied"));
    }
    let duplicate=Owned(duplicate);
    // A fixed *restricting* SID requires BOTH the base SYSTEM DACL check
    // and a BUILTIN\Users allowed ACE. This is a genuine restricted token,
    // but not sufficient for production isolation of untrusted SSM requests.
    let mut sid_storage=[0usize;16];
    let mut sid_size=mem::size_of_val(&sid_storage) as u32;
    if unsafe{CreateWellKnownSid(WIN_BUILTIN_USERS_SID,ptr::null_mut(),
        sid_storage.as_mut_ptr().cast(),&mut sid_size)}==0{
        return Err(refused("SCM restricted child: Users restricting SID unavailable"));
    }
    let attributes=SidAndAttributes{
        sid:sid_storage.as_mut_ptr().cast(),attributes:0,
    };
    let mut reduced=ptr::null_mut();
    if unsafe{CreateRestrictedToken(duplicate.0,DISABLE_MAX_PRIVILEGE,
        0,ptr::null_mut(),0,ptr::null_mut(),1,
        (&attributes as *const SidAndAttributes).cast_mut().cast(),
        &mut reduced)}==0||reduced.is_null(){
        return Err(refused("SCM restricted child: OS primary token reduction denied"));
    }
    let reduced=Owned(reduced);
    if unsafe{IsTokenRestricted(reduced.0)}==0{
        return Err(refused("SCM restricted child: restricting SID not established"));
    }
    Ok(reduced)
}
/// The caller owns original fixed process/thread HANDLEs and the Job; no PID
/// adoption and absolutely no CreateProcessW(LocalSystem) fallback.
pub fn launch(application:&[u16],command:&mut[u16],
              startup:*const c_void,process_info:*mut c_void)->io::Result<()>{
    let token=primary_restricted()?;
    if unsafe{CreateProcessAsUserW(token.0,application.as_ptr(),
        command.as_mut_ptr(),ptr::null_mut(),ptr::null_mut(),0,
        CREATE_SUSPENDED|CREATE_NO_WINDOW,ptr::null_mut(),ptr::null(),
        startup.cast_mut(),process_info)}==0{
        return Err(refused("SCM fixed SSM restricted CreateProcessAsUserW denied"));
    }
    Ok(())
}
/// Independent native kernel TokenIsRestricted on the actual suspended child.
pub fn require_original_worker_restricted(process:Handle)->io::Result<()>{
    if process.is_null(){return Err(refused("restricted child process absent"));}
    let mut token=ptr::null_mut();
    if unsafe{OpenProcessToken(process,TOKEN_QUERY,&mut token)}==0||
       token.is_null(){
        return Err(refused("restricted child token query refused"));
    }
    let token=Owned(token);
    if unsafe{IsTokenRestricted(token.0)}==0{
        return Err(refused("original SSM worker is not OS restricted"));
    }
    // TokenIsAppContainer is deliberately 0. This must NEVER be represented
    // as an installed AppContainer / low-privilege user sandbox.
    let mut is_appcontainer=u32::MAX;
    let mut used=0u32;
    if unsafe{GetTokenInformation(token.0,29,(&mut is_appcontainer as *mut u32).cast(),
        mem::size_of::<u32>() as u32,&mut used)}==0||
        used!=mem::size_of::<u32>() as u32||is_appcontainer!=0{
        return Err(refused("restricted CI fixture token class inconsistent"));
    }
    Ok(())
}
