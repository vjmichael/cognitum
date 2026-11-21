//! PHYSICAL-02-R3: service-held, independently verifiable CNG-signed
//! prelaunch and uncertain/replay-refusal receipts. The only signing key is
//! an externally provisioned exact LocalMachine P256 pin from R2.
//!
//! Durable receipt != original Core grant or independently anchored
//! antirollback. No outcome delivery, no re-execution and no local
//! "uncertain -> success" transition. Never accept IPC-supplied paths,
//! signer names or replay override. Every crash/restart is fail-closed.
//! Signed uncertain outcome asserts *neither kernel empty nor completion*.
#![cfg(all(windows,feature="r3-signed-recovery"))]
use std::{
    ffi::c_void, fs::{self,OpenOptions},
    io::{self,Write},path::Path,ptr,
};
use crate::{r2_signer,ssm_fixture};
type Handle=*mut c_void;
const PRE_DOMAIN:&[u8]=b"Cognitum.R3.CI.PRELAUNCH.v1\0";
const UNCERTAIN_DOMAIN:&[u8]=b"Cognitum.R3.CI.UNCERTAIN_RESTART.v1\0";
const REPLAY_DOMAIN:&[u8]=b"Cognitum.R3.CI.REPLAY_REFUSED.v1\0";
const MAX_FRAME:usize=2048;
#[repr(C)]
#[derive(Clone,Copy,Default)]
struct FileTime{low:u32,high:u32}
#[link(name="kernel32")]
unsafe extern "system"{
    fn GetCurrentProcess()->Handle;
    fn GetCurrentProcessId()->u32;
    fn GetProcessTimes(process:Handle,creation:*mut FileTime,exit:*mut FileTime,
        kernel:*mut FileTime,user:*mut FileTime)->i32;
}
fn denied(why:&str)->io::Error{
    io::Error::new(io::ErrorKind::PermissionDenied,why.to_string())
}
fn hex(raw:&[u8])->String{
    const TABLE:&[u8]=b"0123456789abcdef";
    let mut s=String::with_capacity(raw.len()*2);
    for v in raw {s.push(TABLE[(v>>4) as usize] as char);s.push(TABLE[(v&15) as usize] as char);}
    s
}
fn sha(raw:&[u8])->io::Result<[u8;32]>{r2_signer::r3_sha(raw)}
fn path(name:&str)->io::Result<&'static Path>{
    let raw=match name{
        "prelaunch"=>env!("COG_R3_CI_PRELAUNCH_SIGNED"),
        "restart"=>env!("COG_R3_CI_RESTART_SIGNED"),
        _=>return Err(denied("unknown fixed signed receipt output"))
    };
    let p=Path::new(raw);
    if !p.is_absolute()||p.is_symlink(){
        return Err(denied("signed receipt destination is not an absolute fixed path"));
    }
    Ok(p)
}
fn write_once(path:&Path,body:&[u8])->io::Result<()>{
    if body.is_empty()||body.len()>4096||path.exists()||path.is_symlink(){
        return Err(denied("signed original receipt already exists or is unsafe"));
    }
    let mut out=OpenOptions::new().create_new(true).write(true).open(path)?;
    out.write_all(body)?;
    out.sync_all()?;
    Ok(())
}
fn generation()->io::Result<(u32,u64)>{
    let mut born=FileTime::default();
    let mut exit=FileTime::default();
    let mut kernel=FileTime::default();
    let mut user=FileTime::default();
    if unsafe{GetProcessTimes(GetCurrentProcess(),&mut born,&mut exit,
           &mut kernel,&mut user)}==0 {
        return Err(denied("original Windows SCM service generation unavailable"));
    }
    let birth=(u64::from(born.high)<<32)|u64::from(born.low);
    let pid=unsafe{GetCurrentProcessId()};
    if pid==0||birth==0{return Err(denied("SCM service has no positive OS generation"));}
    Ok((pid,birth))
}
fn read_r1_prelaunch()->io::Result<(String,String,[u8;32])>{
    let p=Path::new(env!("COG_R1_CI_PRELAUNCH"));
    if !p.is_absolute()||p.is_symlink()||!p.is_file(){
        return Err(denied("missing original durable prelaunch in fixed path"));
    }
    let body=fs::read(p)?;
    if body.is_empty()||body.len()>512{
        return Err(denied("bounded original local prelaunch bytes required"));
    }
    let s=std::str::from_utf8(&body).map_err(|_|denied("non-ASCII original prelaunch"))?;
    let prefix="{\"schema\":\"cognitum.ssm.r1.fixture_prelaunch.v1\",\"nonce\":\"";
    let at=s.strip_prefix(prefix).ok_or_else(||denied("original prelaunch schema differs"))?;
    let (nonce,at)=at.split_once("\",\"request_sha256\":\"")
        .ok_or_else(||denied("original prelaunch nonce absent"))?;
    let (req,last)=at.split_once("\"")
        .ok_or_else(||denied("original prelaunch request digest absent"))?;
    if nonce.len()!=32||req.len()!=64||
       !nonce.bytes().chain(req.bytes()).all(|b|b.is_ascii_digit()||
        (b'a'..=b'f').contains(&b))||
       last!=",\"replay_authorized\":false,\"production_authority\":false}\n"{
        return Err(denied("not exact original prelaunch/no authorization"));
    }
    Ok((nonce.to_string(),req.to_string(),sha(&body)?))
}
fn signed_claim(domain:&[u8],kind:&str,nonce:&str,req:&str,
   linked_hash:[u8;32],out:&Path)->io::Result<()>{
    if nonce.len()!=32||req.len()!=64{
        return Err(denied("original operation identity not pinned"));
    }
    let (pid,birth)=generation()?;
    let body=format!(
        "{{\"schema\":\"cognitum.ssm.r3.CI_original_receipt_frame.v1\",\"kind\":\"{}\",\"original_nonce\":\"{}\",\"request_sha256\":\"{}\",\"source_record_sha256\":\"{}\",\"service_pid\":{},\"service_creation_filetime\":{},\"kernel_job_empty_claimed\":false,\"original_replay_authorized\":false,\"installed_Core_grant\":false,\"installed_publisher_approved\":false,\"production_receipt_issuer_approved\":false,\"external_output_release_authorized\":false}}",
        kind,nonce,req,hex(&linked_hash),pid,birth
    );
    if body.len()>MAX_FRAME{return Err(denied("R3 frame too large"));}
    let (signature,public_sha)=r2_signer::sign_r3_frame(domain,body.as_bytes())?;
    let envelope=format!(
        "{{\"schema\":\"cognitum.ssm.r3.CI_machine_signed_envelope.v1\",\"frame_hex\":\"{}\",\"signature_p256_raw\":\"{}\",\"public_blob_sha256\":\"{}\",\"production_authority\":false,\"output_release_authorized\":false}}\n",
        hex(body.as_bytes()),hex(&signature),hex(&public_sha)
    );
    write_once(out,envelope.as_bytes())
}
/// A signed original admission marker is durable BEFORE CreateProcess.
pub fn sign_verified_prelaunch(original:&ssm_fixture::Prepared)->io::Result<()>{
    let (nonce,req,pre_sha)=read_r1_prelaunch()?;
    if nonce!=original.nonce||req!=original.request_sha256{
        return Err(denied("R1 HMAC-verified original differs from on-disk prelaunch"));
    }
    signed_claim(PRE_DOMAIN,"prelaunch_no_execution_proof",&nonce,&req,
        pre_sha,path("prelaunch")?)
}
/// Called BEFORE Keeper::start/SSM open. A reused original ALWAYS refuses,
/// with a distinct CNG-signed uncertain/replay record for external custody.
/// A local output file without a signed, independent terminal receipt is
/// *uncertain*, not success. No new SSM worker is born on this path.
pub fn refuse_prior_original()->io::Result<()>{
    let source=Path::new(env!("COG_R1_CI_PRELAUNCH"));
    if !source.exists(){return Ok(());}
    let (nonce,req,pre_sha)=read_r1_prelaunch()?;
    // A locally forged or interrupted unsigned admission must never be
    // upgraded into approved signed completion on restart.
    let signed_pre=path("prelaunch")?;
    if !signed_pre.is_file()||signed_pre.is_symlink(){
        return Err(denied("old original lacks signed admission; uncertain blocked"));
    }
    let prior=fs::read(signed_pre)?;
    if prior.is_empty()||prior.len()>4096||
       !prior.starts_with(b"{\"schema\":\"cognitum.ssm.r3.CI_machine_signed_envelope.v1\""){
        return Err(denied("old signed admission envelope malformed"));
    }
    let terminal=Path::new(env!("COG_R2_CI_SIGNED_STOP"));
    let (kind,domain)=if terminal.is_file() && !terminal.is_symlink(){
        ("replay_refused",REPLAY_DOMAIN)
    }else{
        ("uncertain_restart",UNCERTAIN_DOMAIN)
    };
    // Bind the restart to the original prelaunch *and* immutable signed
    // admission by hashing them in order, without asserting Job emptiness.
    let mut link=Vec::with_capacity(32+prior.len());
    link.extend_from_slice(&pre_sha);
    link.extend_from_slice(&prior);
    let linked=sha(&link)?;
    // Signature cannot upgrade state, does not authorize replay or release.
    signed_claim(domain,kind,&nonce,&req,linked,path("restart")?)?;
    Err(denied("original operation already admitted: signed restart refusal"))
}
