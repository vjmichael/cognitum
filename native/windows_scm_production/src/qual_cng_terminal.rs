//! R3-R1 machine-CNG signed terminal candidate: CURRENTLY CI-ONLY.
//! Uses an independently provisioned existing, nonexportable LocalMachine P256
//! signing key. Never creates/imports/exports a private key, never signs a
//! client-provided frame, never authorizes Core effects/output or IPC.
//!
//! Durable sequence: kernel Job empty and child exited BEFORE caller enters;
//! write create_new + sync_all original terminal body; sign its EXACT bytes;
//! write create_new + sync_all detached envelope. An interrupted half-pair is
//! treated as uncertain and MUST NOT be replaced/replayed on restart.
//! The filesystem alone does NOT provide independent antirollback authority.
#![cfg(all(windows, feature="protected-ssm-qualification"))]
use std::{ffi::{c_void,OsStr},fs::{self,OpenOptions},io::{self,Write},
          os::windows::ffi::OsStrExt,path::Path,ptr};
use crate::qual_appcontainer::sha256;

type Handle=*mut c_void;
const KSP:&str="Microsoft Software Key Storage Provider";
const PUBLIC_LEN:usize=72;
const SIGNATURE_LEN:usize=64;
const DOMAIN:&[u8]=b"Cognitum.R3R1.CI.PROTECTED_TERMINAL.v1\0";
const MACHINE:u32=0x20;
#[link(name="ncrypt")]
unsafe extern "system" {
 fn NCryptOpenStorageProvider(out:*mut Handle,name:*const u16,flags:u32)->i32;
 fn NCryptOpenKey(provider:Handle,out:*mut Handle,name:*const u16,legacy:u32,flags:u32)->i32;
 fn NCryptGetProperty(key:Handle,name:*const u16,out:*mut u8,len:u32,used:*mut u32,flags:u32)->i32;
 fn NCryptExportKey(key:Handle,export:Handle,blob:*const u16,params:Handle,
                    out:*mut u8,len:u32,used:*mut u32,flags:u32)->i32;
 fn NCryptSignHash(key:Handle,padding:Handle,hash:*const u8,hash_len:u32,
                   sig:*mut u8,sig_len:u32,used:*mut u32,flags:u32)->i32;
 fn NCryptFreeObject(handle:Handle)->i32;
}
#[link(name="kernel32")]
unsafe extern "system" {
 fn GetCurrentProcessId()->u32;
}
struct Owned(Handle);
impl Drop for Owned{
 fn drop(&mut self){if !self.0.is_null(){unsafe{NCryptFreeObject(self.0);}}}
}
fn refuse(what:&str)->io::Error{
 io::Error::new(io::ErrorKind::PermissionDenied,what.to_string())
}
fn wide(s:&str)->Vec<u16>{
 OsStr::new(s).encode_wide().chain(std::iter::once(0)).collect()
}
fn hex(bytes:&[u8])->String {
 let mut result=String::with_capacity(bytes.len()*2);
 const H:&[u8]=b"0123456789abcdef";
 for b in bytes {result.push(H[(b>>4) as usize] as char);result.push(H[(b&15) as usize] as char);}
 result
}
fn pin(value:&str)->bool{
 value.len()==64 && value.bytes().all(|b|b.is_ascii_digit()||(b'a'..=b'f').contains(&b))
    && value!=("0".repeat(64))
}
fn key()->io::Result<(Owned,Owned,[u8;PUBLIC_LEN])>{
 let name=env!("COG_PROD_QUAL_KSP_NAME");
 let expected=env!("COG_PROD_QUAL_KSP_PUBLIC_SHA256");
 if name.len()<12||name.len()>96||
    !name.bytes().all(|b|b.is_ascii_alphanumeric()||b==b'-'||b==b'_')||
    !pin(expected){
  return Err(refuse("external existing signer name/hash are not pinned"));
 }
 let mut raw=ptr::null_mut();
 if unsafe{NCryptOpenStorageProvider(&mut raw,wide(KSP).as_ptr(),0)}!=0||raw.is_null(){
  return Err(refuse("Windows machine signing provider unavailable"));
 }
 let provider=Owned(raw);
 let mut rawkey=ptr::null_mut();
 if unsafe{NCryptOpenKey(provider.0,&mut rawkey,wide(name).as_ptr(),0,MACHINE)}!=0||
    rawkey.is_null(){
  return Err(refuse("externally provisioned original LocalMachine signer missing"));
 }
 let secret=Owned(rawkey);
 let mut policy=[0u8;4];
 let mut used=0u32;
 if unsafe{NCryptGetProperty(secret.0,wide("Export Policy").as_ptr(),
                  policy.as_mut_ptr(),4,&mut used,0)}!=0||
    used!=4||policy!=[0,0,0,0]{
  return Err(refuse("nonexportable machine signer policy missing"));
 }
 let mut algorithm=[0u8;128];
 used=0;
 if unsafe{NCryptGetProperty(secret.0,wide("Algorithm Name").as_ptr(),
                  algorithm.as_mut_ptr(),128,&mut used,0)}!=0||
    used<4||used as usize>algorithm.len()||used%2!=0{
  return Err(refuse("native signer algorithm unavailable"));
 }
 let decoded=String::from_utf16(&algorithm[..used as usize]
                 .chunks_exact(2)
                 .map(|x|u16::from_le_bytes([x[0],x[1]])).collect::<Vec<_>>())
     .map_err(|_|refuse("invalid CNG algorithm encoding"))?;
 if decoded.trim_end_matches('\0')!="ECDSA_P256"{
  return Err(refuse("not the exact ECDSA P256 algorithm"));
 }
 let mut usage=[0u8;4];
 used=0;
 if unsafe{NCryptGetProperty(secret.0,wide("Key Usage").as_ptr(),
                  usage.as_mut_ptr(),4,&mut used,0)}!=0||
    used!=4||((u32::from_le_bytes(usage)&2)==0){
  return Err(refuse("original key not permitted to sign"));
 }
 let mut pubkey=[0u8;PUBLIC_LEN];
 used=0;
 if unsafe{NCryptExportKey(secret.0,ptr::null_mut(),wide("ECCPUBLICBLOB").as_ptr(),
               ptr::null_mut(),pubkey.as_mut_ptr(),PUBLIC_LEN as u32,&mut used,0)}!=0||
    used as usize!=PUBLIC_LEN||
    pubkey[0..8]!=[0x45,0x43,0x53,0x31,32,0,0,0]||
    hex(&sha256(&pubkey)?)!=expected{
  return Err(refuse("native CNG public identity differs from independent pin"));
 }
 Ok((provider,secret,pubkey))
}
fn terminal_path(p:&str)->io::Result<&Path>{
 let path=Path::new(p);
 if !path.is_absolute()||path.exists()||path.is_symlink()||
    path.parent().is_none_or(|parent|!parent.is_dir()||parent.is_symlink()){
  return Err(refuse("original terminal journal path not fresh, absolute and existing-parent"));
 }
 Ok(path)
}
fn write_new(path:&Path,data:&[u8])->io::Result<()>{
 if data.is_empty()||data.len()>4096{return Err(refuse("bounded original terminal receipt required"));}
 let mut writer=OpenOptions::new().write(true).create_new(true).open(path)?;
 writer.write_all(data)?;
 writer.sync_all()
}
/// Call ONLY after OS observed the actual original child exited, the Job
/// has zero live processes and cancellation was reconciled. This function
/// authenticates the signer key, NOT those OS facts independently.
pub fn seal_original_terminal(pid:u32,request_sha:&str,output_sha:&[u8;32])->io::Result<()>{
 if pid==0||!pin(request_sha)||!output_sha.iter().any(|b|*b!=0){
  return Err(refuse("bounded nonzero exact original terminal identity required"));
 }
 let body_path=terminal_path(env!("COG_PROD_QUAL_TERMINAL"))?;
 let signed_path=terminal_path(env!("COG_PROD_QUAL_TERMINAL_SIGNED"))?;
 if body_path==signed_path{return Err(refuse("terminal and signature may not share path"));}
 // Open signer BEFORE writing any terminal record. The installed signer must
 // come from separately approved OS key custody, not a self-declared output.
 let (_provider,signer,pubkey)=key()?;
 let body=format!(
  "{{\"schema\":\"cognitum.ssm.r3r1.ci_protected_terminal.v1\",\"scm_pid\":{},\"worker_pid\":{},\"original_request_sha256\":\"{}\",\"candidate_output_sha256\":\"{}\",\"kernel_job_empty_after_child_exit\":true,\"original_lu_core_grant_verified\":false,\"installed_signer_approved\":false,\"output_or_ACK_authorized\":false}}\n",
  unsafe{GetCurrentProcessId()},pid,request_sha,hex(output_sha),
 );
 if body.len()>2048{return Err(refuse("terminal frame exceeds immutable bound"));}
 let body_bytes=body.as_bytes();
 let mut signed_input=DOMAIN.to_vec();
 signed_input.extend_from_slice(body_bytes);
 let hash=sha256(&signed_input)?;
 // Once journaled, an interrupted attempt remains uncertain; we do not
 // delete the unsigned original or manufacture a success after a restart.
 write_new(body_path,body_bytes)?;
 let mut signature=[0u8;SIGNATURE_LEN];
 let mut written=0u32;
 if unsafe{NCryptSignHash(signer.0,ptr::null_mut(),hash.as_ptr(),32,
             signature.as_mut_ptr(),SIGNATURE_LEN as u32,&mut written,0)}!=0||
    written as usize!=SIGNATURE_LEN{
  return Err(refuse("genuine nonexportable OS machine terminal signature refused"));
 }
 let envelope=format!(
  "{{\"schema\":\"cognitum.ssm.r3r1.ci_p256_terminal_signature.v1\",\"terminal_sha256\":\"{}\",\"public_blob_sha256\":\"{}\",\"signature_p256_raw\":\"{}\",\"production_issuer_enrollment_verified\":false,\"Core_grant_verified\":false,\"output_or_ACK_authorized\":false}}\n",
  hex(&sha256(body_bytes)?),hex(&sha256(&pubkey)?),hex(&signature)
 );
 write_new(signed_path,envelope.as_bytes())
}
