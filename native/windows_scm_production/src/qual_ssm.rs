//! Protected mathematical worker qualification for the separate SCM lineage.
//! NOT compiled into the accepted R3-R1 no-worker Windows release.
//! The launcher consumes ONLY independently prepared, build-pinned inputs;
//! no IPC, no Core grant, no output/ACK, no production signer enrollment.
//! A positive run proves kernel AppContainer + attach-before-resume mechanics,
//! but not an independently authorized installed production computation.
#![cfg(all(windows,feature="protected-ssm-qualification"))]
use std::{ffi::{c_void,OsStr},fs::{self,OpenOptions},io::{self,Write},mem,
          os::windows::ffi::OsStrExt,path::Path,ptr,thread,time::{Duration,Instant},
          sync::atomic::{AtomicBool,Ordering}};
use crate::qual_appcontainer::{launch,sha256};
type Handle=*mut c_void;
const CREATE_TIMEOUT:Duration=Duration::from_secs(40);
const WAIT_OBJECT_0:u32=0;
const WAIT_TIMEOUT:u32=0x102;
const MAX_FRAME:usize=2*1024*1024;
const JOB_BASIC_ACCOUNTING_INFORMATION:u32=1;
#[repr(C)]
struct ProcessInfo{process:Handle,thread:Handle,pid:u32,tid:u32}
#[repr(C)]
#[derive(Default)]
struct JobAccounting{
 total_user_time:i64,total_kernel_time:i64,this_user_time:i64,
 this_kernel_time:i64,page_faults:u32,total_processes:u32,
 active_processes:u32,terminated_processes:u32,
}
#[link(name="kernel32")]
unsafe extern "system" {
 fn AssignProcessToJobObject(job:Handle,child:Handle)->i32;
 fn IsProcessInJob(child:Handle,job:Handle,member:*mut i32)->i32;
 fn ResumeThread(thread:Handle)->u32;
 fn TerminateProcess(child:Handle,code:u32)->i32;
 fn TerminateJobObject(job:Handle,code:u32)->i32;
 fn WaitForSingleObject(child:Handle,timeout:u32)->u32;
 fn GetExitCodeProcess(child:Handle,code:*mut u32)->i32;
 fn CloseHandle(handle:Handle)->i32;
 fn QueryInformationJobObject(job:Handle,info:u32,buffer:Handle,len:u32,returned:*mut u32)->i32;
}
struct Owned(Handle);
impl Drop for Owned{
 fn drop(&mut self){if !self.0.is_null(){unsafe{CloseHandle(self.0);}}}
}
fn refused(reason:&str)->io::Error {
 io::Error::new(io::ErrorKind::PermissionDenied,reason.to_string())
}
fn wide(s:&OsStr)->Vec<u16>{
 use std::iter::once;
 s.encode_wide().chain(once(0)).collect()
}
fn pinned(path:&str,digest:&str,limit:usize)->io::Result<()>{
 let p=Path::new(path);
 if !p.is_absolute()||p.is_symlink()||!p.is_file()||
    digest.len()!=64||!digest.bytes().all(|x|x.is_ascii_digit()||(b'a'..=b'f').contains(&x)){
  return Err(refused("absolute immutable image/request pin required"));
 }
 let meta=fs::metadata(p)?;
 if meta.len()==0||meta.len()>limit as u64 {return Err(refused("pinned frame exceeds size budget"));}
 let actual=fs::read(p)?;
 let hash=sha256(&actual)?;
 let as_hex=hash.iter().map(|x|format!("{:02x}",x)).collect::<String>();
 if as_hex!=digest {return Err(refused("original separately pinned file SHA256 mismatch"));}
 Ok(())
}
fn empty(job:Handle)->io::Result<bool>{
 let mut account=JobAccounting::default();
 if unsafe{QueryInformationJobObject(job,JOB_BASIC_ACCOUNTING_INFORMATION,
           (&mut account as *mut JobAccounting).cast(),mem::size_of::<JobAccounting>() as u32,
           ptr::null_mut())}==0{
  return Err(io::Error::last_os_error());
 }
 Ok(account.active_processes==0)
}
fn record(out:&Path,pid:u32,result_digest:&[u8;32])->io::Result<()>{
 if !out.is_absolute()||out.is_symlink()||out.exists(){return Err(refused("qualification witness reused"));}
 let sha=result_digest.iter().map(|b|format!("{:02x}",b)).collect::<String>();
 let body=format!(
  "{{\"schema\":\"cognitum.ssm.production_lineage.protected_numeric_qualification.v1\",\"worker_pid\":{},\"kernel_job_empty_after_wait\":true,\"worker_result_sha256\":\"{}\",\"installed_release_admitted\":false,\"Core_operation_grant\":false,\"production_CNG_receipts\":false,\"output_release_authorized\":false}}\n",
  pid,sha
 );
 let mut f=OpenOptions::new().write(true).create_new(true).open(out)?;
 f.write_all(body.as_bytes())?;
 f.sync_all()?;
 Ok(())
}
pub fn execute(job:Handle,stop:&AtomicBool)->io::Result<()>{
 if !empty(job)?||stop.load(Ordering::Acquire){return Err(refused("SCM original Job not empty"));}
 let python=env!("COG_PROD_QUAL_PYTHON");
 let child=env!("COG_PROD_QUAL_CHILD");
 let input=env!("COG_PROD_QUAL_REQUEST");
 let output=env!("COG_PROD_QUAL_OUTPUT");
 let witness=Path::new(env!("COG_PROD_QUAL_RESULT_WITNESS"));
 // Independently staged: no dynamic argv, PATH discovery or arbitrary
 // code/request selected by a client, process environment or named pipe.
 pinned(python,env!("COG_PROD_QUAL_PYTHON_SHA256"),64*1024*1024)?;
 pinned(child,env!("COG_PROD_QUAL_CHILD_SHA256"),64*1024*1024)?;
 pinned(input,env!("COG_PROD_QUAL_REQUEST_SHA256"),MAX_FRAME)?;
 if Path::new(output).exists()||witness.exists(){
  return Err(refused("original SSM result or qualification receipt already exists"));
 }
 if Path::new(output).parent()!=Path::new(input).parent(){
  return Err(refused("fixed worker request/result directory differs"));
 }
 let application=wide(OsStr::new(python));
 let command=format!("\"{}\" -I -B \"{}\" \"{}\" \"{}\"",python,child,input,output);
 let mut command=wide(OsStr::new(&command));
 let mut raw:ProcessInfo=unsafe{mem::zeroed()};
 // launch performs independently pinned peer TOKEN checks and creates a
 // no-capability AppContainer process SUSPENDED; never run code on failure.
 launch(&application,&mut command,ptr::null(),(&mut raw as *mut ProcessInfo).cast())?;
 if raw.process.is_null()||raw.thread.is_null()||raw.pid==0{
  return Err(refused("invalid OS process/thread handles"));
 }
 let process=Owned(raw.process);
 let thread=Owned(raw.thread);
 let mut attached=false;
 let outcome=(||{
  if unsafe{AssignProcessToJobObject(job,process.0)}==0{
   return Err(refused("SCM Job adoption before resume failed"));
  }
  let mut membership=0i32;
  if unsafe{IsProcessInJob(process.0,job,&mut membership)}==0||membership==0{
   return Err(refused("kernel Job membership could not be verified before resume"));
  }
  attached=true;
  if stop.load(Ordering::Acquire){return Err(refused("SCM stop before SSM execution"));}
  if unsafe{ResumeThread(thread.0)}==u32::MAX{
   return Err(refused("worker resume refused"));
  }
  let deadline=Instant::now()+CREATE_TIMEOUT;
  loop{
   if stop.load(Ordering::Acquire){return Err(refused("SCM cancellation before numerical completion"));}
   match unsafe{WaitForSingleObject(process.0,100)}{
    WAIT_OBJECT_0=>break,
    WAIT_TIMEOUT if Instant::now()<deadline=>thread::sleep(Duration::from_millis(10)),
    WAIT_TIMEOUT=>return Err(refused("bounded SSM deadline expired")),
    _=>return Err(refused("original worker wait failed")),
   }
  }
  let mut status=u32::MAX;
  if unsafe{GetExitCodeProcess(process.0,&mut status)}==0||status!=0{
   return Err(refused("AppContainer mathematical child returned failure"));
  }
  // Candidate math is NOT approved or sent to Lu here. Independent numerical
  // recomputation is performed by a separate CI job on a copied artifact.
  pinned(output,env!("COG_PROD_QUAL_OUTPUT_SHA256"),MAX_FRAME)?;
  let bytes=fs::read(output)?;
  let digest=sha256(&bytes)?;
  Ok(digest)
 })();
 // On every route, direct-terminate if not adopted, otherwise terminate
 // the owned Job and confirm the child has stopped before any evidence.
 if attached {unsafe{TerminateJobObject(job,0xED);}}
 else {unsafe{TerminateProcess(process.0,0xEE);}}
 let waited=unsafe{WaitForSingleObject(process.0,5000)}==WAIT_OBJECT_0;
 let empty_after=empty(job).unwrap_or(false);
 if !waited||!empty_after {return Err(refused("cannot establish terminal kernel Job custody"));}
 let digest=outcome?;
 // A signed receipt is minted ONLY after the kernel Job is confirmed empty
 // and the original numerical result is checked. The signer is externally
 // provisioned; no key creation, issuer grant or output release here.
 crate::qual_cng_terminal::seal_original_terminal(
     raw.pid,env!("COG_PROD_QUAL_REQUEST_SHA256"),&digest)?;
 record(witness,raw.pid,&digest)
}
