//! R1 **CI fixture only**: a fixed, HMAC-bound original-operation envelope
//! used to launch Cognitum's REAL SSM numerical Python child from an SCM Job.
//!
//! CI creates a random test MAC key and compiles it into this unsigned fixture.
//! That is NOT installer credential custody, Lu Core enrollment, independent
//! production authentication, least privilege/AppContainer, or a signed stop
//! receipt. This service refuses any dynamic command, path or user-selected PID.
//! The original request is bound by a write-once prelaunch marker before child
//! creation; a crash permanently holds the fixture and refuses replay.
#![cfg(all(windows, feature = "ssm-fixture"))]
use std::{
    ffi::OsStr, fs::{self,OpenOptions},io::{self,Write},os::windows::ffi::OsStrExt,
    path::{Path,PathBuf},ptr,
};
use std::ffi::c_void;

type Handle=*mut c_void;
const DOMAIN:&[u8]=b"Cognitum.SCM.R1.test.intent.v1\x00";
const MAX_INTENT:usize=2048;
const MAX_REQUEST:usize=2*1024*1024;
const MAX_IMAGE:usize=64*1024*1024;
const BCRYPT_ALG_HANDLE_HMAC_FLAG:u32=8;
#[link(name="bcrypt")]
unsafe extern "system" {
    fn BCryptOpenAlgorithmProvider(alg:*mut Handle,id:*const u16,
        provider:*const u16,flags:u32)->i32;
    fn BCryptHash(alg:Handle,secret:*const u8,secret_len:u32,
        bytes:*const u8,bytes_len:u32,out:*mut u8,out_len:u32)->i32;
    fn BCryptCloseAlgorithmProvider(alg:Handle,flags:u32)->i32;
}
fn denied(message:&str)->io::Error{
    io::Error::new(io::ErrorKind::PermissionDenied,message.to_owned())
}
fn wide(value:&OsStr)->Vec<u16>{
    value.encode_wide().chain(std::iter::once(0)).collect()
}
fn hex(bytes:&[u8])->String{
    const D:&[u8]=b"0123456789abcdef";
    let mut out=String::with_capacity(bytes.len()*2);
    for b in bytes {
        out.push(D[(b>>4)as usize] as char);
        out.push(D[(b&15)as usize] as char);
    }
    out
}
fn parse_hex(text:&str)->io::Result<Vec<u8>>{
    if text.len()%2!=0||text.is_empty()||text.len()>128||
       !text.bytes().all(|b|b.is_ascii_digit()||(b'a'..=b'f').contains(&b)){
       return Err(denied("test-only bounded lowercase hex pin required"));
    }
    let mut out=Vec::new();
    for item in text.as_bytes().chunks_exact(2){
        let s=std::str::from_utf8(item).map_err(|_|denied("invalid hex encoding"))?;
        out.push(u8::from_str_radix(s,16).map_err(|_|denied("invalid hex"))?);
    }
    Ok(out)
}
fn ct_equals(a:&[u8],b:&[u8])->bool{
    if a.len()!=b.len(){return false;}
    let mut mismatch=0u8;
    for (x,y) in a.iter().zip(b){ mismatch|=x^y; }
    mismatch==0
}
fn sha256_or_hmac(secret:Option<&[u8]>,body:&[u8])->io::Result<[u8;32]>{
    if body.len()>MAX_IMAGE {return Err(denied("bounded fixture hash budget"));}
    let algorithm=wide(OsStr::new("SHA256"));
    let mut alg:Handle=ptr::null_mut();
    if unsafe{BCryptOpenAlgorithmProvider(&mut alg,algorithm.as_ptr(),ptr::null(),
          if secret.is_some(){BCRYPT_ALG_HANDLE_HMAC_FLAG}else{0})}!=0||alg.is_null(){
        return Err(denied("Windows CNG SHA256 unavailable"));
    }
    let result=(||{
        let mut answer=[0u8;32];
        let key=secret.unwrap_or(&[]);
        let status=unsafe{BCryptHash(alg,
            if key.is_empty(){ptr::null()}else{key.as_ptr()},key.len() as u32,
            body.as_ptr(),body.len() as u32,answer.as_mut_ptr(),32)};
        if status!=0{return Err(denied("Windows CNG keyed SHA failed"));}
        Ok(answer)
    })();
    unsafe{BCryptCloseAlgorithmProvider(alg,0)};
    result
}
fn pinned_file(path:&str,digest:&str,limit:usize)->io::Result<PathBuf>{
    let p=Path::new(path);
    if !p.is_absolute()||p.is_symlink()||!p.is_file(){
        return Err(denied("fixed image/input path is missing, relative or symlinked"));
    }
    let meta=fs::metadata(p)?;
    if meta.len()==0||meta.len()>limit as u64{
        return Err(denied("fixed image/input size refused"));
    }
    let bytes=fs::read(p)?;
    if !ct_equals(&sha256_or_hmac(None,&bytes)?,&parse_hex(digest)?){
        return Err(denied("approved original fixed image/input SHA differs"));
    }
    Ok(p.to_path_buf())
}
fn write_once(path:&Path,body:&[u8])->io::Result<()>{
    if !path.is_absolute()||path.is_symlink()||body.is_empty()||body.len()>2048{
        return Err(denied("bounded protected write-once fixture path required"));
    }
    let mut file=OpenOptions::new().write(true).create_new(true).open(path)?;
    file.write_all(body)?;
    file.sync_all()?;
    Ok(())
}
fn paths()->[&'static str;7]{
    [
      env!("COG_R1_CI_PYTHON"),
      env!("COG_R1_CI_SCRIPT"),
      env!("COG_R1_CI_REQUEST"),
      env!("COG_R1_CI_OUTPUT"),
      env!("COG_R1_CI_INTENT"),
      env!("COG_R1_CI_PRELAUNCH"),
      env!("COG_R1_CI_STOP"),
    ]
}
#[derive(Clone,Debug)]
pub struct Prepared{
    pub nonce:String,
    pub request_sha256:String,
}
pub fn prepare()->io::Result<(Vec<u16>,Vec<u16>,Prepared)>{
    let p=paths();
    let _python=pinned_file(
        p[0],env!("COG_R1_CI_PYTHON_SHA256"),MAX_IMAGE)?;
    let _script=pinned_file(
        p[1],env!("COG_R1_CI_SCRIPT_SHA256"),MAX_REQUEST)?;
    let request=pinned_file(
        p[2],env!("COG_R1_CI_REQUEST_SHA256"),MAX_REQUEST)?;
    let body=fs::read(&request)?;
    if body.len()>MAX_REQUEST||!body.starts_with(b"{"){
        return Err(denied("fixed SSM data is not framed numerical request"));
    }
    for idx in [3,5,6]{
        let path=Path::new(p[idx]);
        if !path.is_absolute()||path.is_symlink()||path.exists(){
            return Err(denied("output, prelaunch or stop is reused/uncertain"));
        }
    }
    let intent=fs::read(p[4])?;
    if intent.is_empty()||intent.len()>MAX_INTENT{
        return Err(denied("bounded original operation intent unavailable"));
    }
    let pieces=intent.split(|b|*b==b'\n').collect::<Vec<_>>();
    if pieces.len()!=3||!pieces[2].is_empty()||pieces[1].len()!=64 {
        return Err(denied("closed original signed intent frame"));
    }
    let fields=std::str::from_utf8(pieces[0])
        .map_err(|_|denied("original operation intent not ASCII"))?
        .split('\t').collect::<Vec<_>>();
    if fields.len()!=12 ||
       fields[0]!="cognitum.ssm.r1.original_fixture.v1" ||
       fields[1]!="ci-workspace" ||
       fields[2]!="ci-conversation" ||
       fields[3]!="ci-user-turn" ||
       fields[4]!="ci-task" ||
       fields[5]!="ci-original-operation" ||
       fields[6]!="ci-session" ||
       fields[7]!="ci-ssm-subject" ||
       fields[8]!="ci-stream" ||
       fields[9]!="ci-event" ||
       fields[10]!=env!("COG_R1_CI_REQUEST_SHA256") ||
       fields[11].len()!=32 ||
       !fields[11].bytes().all(|b|b.is_ascii_digit()||(b'a'..=b'f').contains(&b)){
        return Err(denied("foreign original workspace/turn/request or nonce"));
    }
    let mac_hex=std::str::from_utf8(pieces[1])
        .map_err(|_|denied("original intent MAC format"))?;
    let key=parse_hex(env!("COG_R1_CI_MAC_KEY_HEX"))?;
    if key.len()!=32 {
        return Err(denied("ephemeral test-only intent key length"));
    }
    let mut message=DOMAIN.to_vec();
    message.extend_from_slice(pieces[0]);
    let mac=sha256_or_hmac(Some(&key),&message)?;
    if !ct_equals(&mac,&parse_hex(mac_hex)?){
        return Err(denied("original intent test MAC mismatch"));
    }
    // This write is a durable ONE-WAY fixture fence: after crash or restart
    // no second worker may be born from the same original intent.
    let pending=format!(
        "{{\"schema\":\"cognitum.ssm.r1.fixture_prelaunch.v1\",\"nonce\":\"{}\",\"request_sha256\":\"{}\",\"replay_authorized\":false,\"production_authority\":false}}\n",
        fields[11],fields[10],
    );
    write_once(Path::new(p[5]),pending.as_bytes())?;
    // No command/argv from the intent file may affect the child launch.
    // Only the build-pinned reviewed Python script handles fixed SSM math.
    let cmd=format!("\"{}\" -I -B \"{}\" \"{}\" \"{}\"",
                    p[0],p[1],p[2],p[3]);
    let approved=Prepared{nonce:fields[11].to_owned(),
                          request_sha256:fields[10].to_owned()};
    Ok((wide(OsStr::new(p[0])),wide(OsStr::new(&cmd)),approved))
}
pub fn record_stop(proof:&Prepared,worker_pid:u32,service_pid:u32,
                   kernel_empty:bool)->io::Result<()>{
    if worker_pid==0||service_pid==0||!kernel_empty{
        return Err(denied("kernel-empty original worker proof missing"));
    }
    let p=paths();
    let out=Path::new(p[3]);
    if !out.is_file()||out.is_symlink(){
        return Err(denied("real SSM fixed worker produced no output"));
    }
    let raw=fs::read(out)?;
    if raw.is_empty()||raw.len()>MAX_REQUEST||!raw.starts_with(b"{"){
        return Err(denied("SSM result not a bounded candidate"));
    }
    let bytes=sha256_or_hmac(None,&raw)?;
    let record=format!(
        "{{\"schema\":\"cognitum.ssm.r1.scm_local_stop.v1\",\"original_nonce\":\"{}\",\"request_sha256\":\"{}\",\"result_sha256\":\"{}\",\"service_pid\":{},\"worker_pid\":{},\"kernel_job_empty\":true,\"independently_signed\":false,\"installed_core_authenticated\":false,\"production_authority\":false,\"output_release_authorized\":false}}\n",
        proof.nonce,proof.request_sha256,hex(&bytes),service_pid,worker_pid,
    );
    write_once(Path::new(p[6]),record.as_bytes())?;
    #[cfg(feature = "r2-restricted-fixture")]
    crate::r2_signer::sign_local_stopped_original(Path::new(p[6]))?;
    Ok(())
}
