//! R2: installer-*style* pre-provisioned Windows machine CNG receipt key.
//! No key generation/import, no fallback, no private-key export, no key
//! selection from an IPC message. CI provisions a temporary KSP key OUTSIDE
//! this unsigned SCM fixture and pins its ECCPUBLICBLOB SHA at build time.
//!
//! A genuine OS CNG ECDSA signature can be verified by an independent host,
//! but self-generated CI installer inputs do not constitute independent
//! approved publisher/enrollment/antirollback. Never release output on receipt.
#![cfg(all(windows,feature="r2-cng-fixture"))]
use std::{ffi::{c_void,OsStr},io,os::windows::ffi::OsStrExt,ptr,
          fs::{self,OpenOptions},io::Write,path::Path};
type Handle=*mut c_void;
const KSP:&str="Microsoft Software Key Storage Provider";
const MACHINE_KEY_FLAG:u32=0x20;
const DOMAIN:&[u8]=b"Cognitum.R2.CI.SCM_STOP.v1\0";
const PUBLIC_LEN:usize=72;
const SIGNATURE_LEN:usize=64;
#[link(name="ncrypt")]
unsafe extern "system"{
    fn NCryptOpenStorageProvider(provider:*mut Handle,name:*const u16,flags:u32)->i32;
    fn NCryptOpenKey(provider:Handle,key:*mut Handle,name:*const u16,
                     legacy:u32,flags:u32)->i32;
    fn NCryptExportKey(key:Handle,export:Handle,kind:*const u16,
        parameters:Handle,out:*mut u8,len:u32,used:*mut u32,flags:u32)->i32;
    fn NCryptSignHash(key:Handle,padding:Handle,hash:*const u8,hash_len:u32,
        signature:*mut u8,signature_len:u32,used:*mut u32,flags:u32)->i32;
    fn NCryptFreeObject(handle:Handle)->i32;
}
#[link(name="bcrypt")]
unsafe extern "system"{
    fn BCryptOpenAlgorithmProvider(provider:*mut Handle,name:*const u16,
                                   implementation:*const u16,flags:u32)->i32;
    fn BCryptHash(alg:Handle,secret:*const u8,secret_len:u32,
        data:*const u8,len:u32,digest:*mut u8,digest_len:u32)->i32;
    fn BCryptCloseAlgorithmProvider(handle:Handle,flags:u32)->i32;
}
fn wide(value:&str)->Vec<u16>{
    OsStr::new(value).encode_wide().chain(std::iter::once(0)).collect()
}
fn denied(why:&'static str)->io::Error{
    io::Error::new(io::ErrorKind::PermissionDenied,why)
}
fn hex(raw:&[u8])->String{
    let mut out=String::with_capacity(raw.len()*2);
    const D:&[u8]=b"0123456789abcdef";
    for b in raw {out.push(D[(b>>4) as usize] as char);out.push(D[(b&15) as usize] as char);}
    out
}
struct OwnedN(Handle);
impl Drop for OwnedN{fn drop(&mut self){if !self.0.is_null(){
    unsafe{NCryptFreeObject(self.0);}
}}}
struct OwnedB(Handle);
impl Drop for OwnedB{fn drop(&mut self){if !self.0.is_null(){
    unsafe{BCryptCloseAlgorithmProvider(self.0,0);}
}}}
fn sha(data:&[u8])->io::Result<[u8;32]>{
    if data.is_empty()||data.len()>4096{return Err(denied("bounded R2 signer frame required"));}
    let mut raw=ptr::null_mut();
    if unsafe{BCryptOpenAlgorithmProvider(&mut raw,wide("SHA256").as_ptr(),ptr::null(),0)}!=0
       ||raw.is_null(){return Err(denied("Windows R2 SHA256 provider unavailable"));}
    let alg=OwnedB(raw);
    let mut digest=[0u8;32];
    if unsafe{BCryptHash(alg.0,ptr::null(),0,data.as_ptr(),data.len() as u32,
           digest.as_mut_ptr(),32)}!=0{
        return Err(denied("Windows R2 signer hash refused"));
    }
    Ok(digest)
}
fn key_name()->io::Result<&'static str>{
    let name=env!("COG_R2_CI_KEY_NAME");
    if name.len()<20||name.len()>100||
       !name.bytes().all(|b|b.is_ascii_alphanumeric()||b==b'-'){
        return Err(denied("externally enrolled fixed R2 test signer name invalid"));
    }
    Ok(name)
}
fn open()->io::Result<(OwnedN,OwnedN,[u8;PUBLIC_LEN])>{
    let mut raw=ptr::null_mut();
    if unsafe{NCryptOpenStorageProvider(&mut raw,wide(KSP).as_ptr(),0)}!=0
       ||raw.is_null(){return Err(denied("R2 machine KSP signer provider missing"));}
    let provider=OwnedN(raw);
    let mut key=ptr::null_mut();
    if unsafe{NCryptOpenKey(provider.0,&mut key,wide(key_name()?).as_ptr(),0,
              MACHINE_KEY_FLAG)}!=0||key.is_null(){
        return Err(denied("externally provisioned R2 LocalMachine CNG key missing"));
    }
    let key=OwnedN(key);
    let mut pubkey=[0u8;PUBLIC_LEN];
    let mut used=0u32;
    if unsafe{NCryptExportKey(key.0,ptr::null_mut(),wide("ECCPUBLICBLOB").as_ptr(),
                ptr::null_mut(),pubkey.as_mut_ptr(),PUBLIC_LEN as u32,&mut used,0)}!=0||
       used as usize!=PUBLIC_LEN ||
       pubkey[..4]!=[0x45,0x43,0x53,0x31]||
       pubkey[4..8]!=[32,0,0,0]{
        return Err(denied("installed-style R2 CNG key is not ECDSA P256"));
    }
    let expected=env!("COG_R2_CI_PUBLIC_SHA256");
    if expected.len()!=64||!expected.bytes().all(|b|b.is_ascii_digit()||
           (b'a'..=b'f').contains(&b))||
        hex(&sha(&pubkey)?)!=expected{
        return Err(denied("R2 service signer public key differs from separately pinned test manifest"));
    }
    Ok((provider,key,pubkey))
}
/// Open exact already-present CNG machine signer before any SSM prelaunch.
pub fn require_preprovisioned()->io::Result<()>{
    let _key=open()?;
    Ok(())
}
/// Sign only the original fsynced kernel-empty *local stop*. This has no
/// protected Core enrollment/producer independence claim or release effect.
/// No receipt is emitted if key was rotated or key store is unreachable.
pub fn sign_local_stopped_original(stop_path:&Path)->io::Result<()>{
    if !stop_path.is_file()||stop_path.is_symlink(){
        return Err(denied("R2 locally witnessed kernel stop missing"));
    }
    let local=fs::read(stop_path)?;
    if local.is_empty()||local.len()>2048||
       !local.starts_with(b"{\"schema\":\"cognitum.ssm.r1.scm_local_stop.v1\""){
        return Err(denied("R2 local original kernel stop schema missing"));
    }
    let (_provider,key,pubkey)=open()?;
    let mut input=DOMAIN.to_vec();
    input.extend_from_slice(&local);
    let digest=sha(&input)?;
    let mut signature=[0u8;SIGNATURE_LEN];
    let mut used=0u32;
    if unsafe{NCryptSignHash(key.0,ptr::null_mut(),digest.as_ptr(),32,
        signature.as_mut_ptr(),SIGNATURE_LEN as u32,&mut used,0)}!=0||
        used as usize!=SIGNATURE_LEN{
        return Err(denied("R2 OS-held machine P256 signature refused"));
    }
    let body=format!(
      "{{\"schema\":\"cognitum.ssm.r2.CI_CNG_signed_stop.v1\",\"kernel_stop_sha256\":\"{}\",\"public_blob_sha256\":\"{}\",\"signature_p256_raw\":\"{}\",\"preprovisioned_os_machine_key\":true,\"installed_publisher_accepted\":false,\"independent_prod_signer_accepted\":false,\"Core_authenticated\":false,\"output_release_authorized\":false}}\n",
      hex(&sha(&local)?),hex(&sha(&pubkey)?),hex(&signature),
    );
    let receipt=Path::new(env!("COG_R2_CI_SIGNED_STOP"));
    if !receipt.is_absolute()||receipt.is_symlink()||receipt.exists(){
        return Err(denied("R2 CNG stop record reused, relative or forged"));
    }
    let mut f=OpenOptions::new().write(true).create_new(true).open(receipt)?;
    f.write_all(body.as_bytes())?;
    f.sync_all()?;
    Ok(())
}


/// R3: one original, domain-separated signature over a closed canonical
/// native receipt frame. The key is machine-held and separately preprovisioned;
/// the production publisher/issuer/antirollback remain unqualified in CI.
/// This API NEVER returns private key bytes, creates keys, grants effects,
/// or accepts a signer-selected path from IPC.
#[cfg(feature="r3-signed-recovery")]
pub(crate) fn sign_r3_frame(domain:&[u8],body:&[u8])
    ->io::Result<([u8;SIGNATURE_LEN],[u8;32])>{
    if domain!=b"Cognitum.R3.CI.PRELAUNCH.v1\0" &&
       domain!=b"Cognitum.R3.CI.UNCERTAIN_RESTART.v1\0" &&
       domain!=b"Cognitum.R3.CI.REPLAY_REFUSED.v1\0" {
        return Err(denied("R3 original receipt signer domain not approved"));
    }
    if body.is_empty() || body.len()>2048 {
        return Err(denied("R3 bounded original receipt frame refused"));
    }
    let (_provider,key,pubkey)=open()?;
    let mut to_hash=domain.to_vec();
    to_hash.extend_from_slice(body);
    let digest=sha(&to_hash)?;
    let mut signature=[0u8;SIGNATURE_LEN];
    let mut used=0u32;
    if unsafe{NCryptSignHash(key.0,ptr::null_mut(),digest.as_ptr(),32,
        signature.as_mut_ptr(),SIGNATURE_LEN as u32,&mut used,0)}!=0||
        used as usize!=SIGNATURE_LEN{
        return Err(denied("R3 genuine OS-machine receipt signature refused"));
    }
    Ok((signature,sha(&pubkey)?))
}


#[cfg(feature="r3-signed-recovery")]
pub(crate) fn r3_sha(bytes:&[u8])->io::Result<[u8;32]>{
    if bytes.len()>8192{return Err(denied("R3 original marker too large"));}
    sha(bytes)
}
#[cfg(feature="r3-appcontainer-fixture")]
pub(crate) fn r3_sha_image(bytes:&[u8])->io::Result<[u8;32]>{
    if bytes.is_empty()||bytes.len()>64*1024*1024{
        return Err(denied("pinned peer executable too large"));
    }
    let mut raw=ptr::null_mut();
    if unsafe{BCryptOpenAlgorithmProvider(&mut raw,wide("SHA256").as_ptr(),
        ptr::null(),0)}!=0||raw.is_null(){
        return Err(denied("peer image CNG SHA256 unavailable"));
    }
    let provider=OwnedB(raw);
    let mut result=[0u8;32];
    if unsafe{BCryptHash(provider.0,ptr::null(),0,
        bytes.as_ptr(),bytes.len() as u32,result.as_mut_ptr(),32)}!=0{
        return Err(denied("peer image CNG hash failed"));
    }
    Ok(result)
}
