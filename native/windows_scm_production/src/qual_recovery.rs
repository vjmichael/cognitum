//! R3-R1 SOURCE-ONLY conservative original-operation recovery fence.
//! Feature-gated to a disposable native Windows SCM qualifier, never the
//! owner-accepted NO-WORKER installed private GPG release.
//!
//! A prior prelaunch marker, even if terminal signing never finished, means
//! the same original operation MUST NOT resume or execute again. Only an
//! independently authorized recovery authority may reconcile it.
//! This is FILE-LOCAL replay refusal, NOT independently monotonic antirollback,
//! not an authenticated Lu PURE_COMPUTE grant, not installed production.
#![cfg(all(windows,feature="protected-ssm-qualification"))]
use std::{fs::{self,OpenOptions},io::{self,Write},path::Path};
use crate::qual_appcontainer::sha256;
const SCHEMA:&str="cognitum.ssm.r3r1.ci_prelaunch_uncertain_v1";
fn denied(why:&str)->io::Error{
    io::Error::new(io::ErrorKind::PermissionDenied,why.to_string())
}
fn valid_digest(s:&str)->bool{
    s.len()==64 && s.bytes().all(|b|b.is_ascii_digit()||(b'a'..=b'f').contains(&b))
        && s.bytes().any(|b|b!=b'0')
}
pub(crate) fn prelaunch_path()->&'static Path{
    Path::new(env!("COG_PROD_QUAL_PRELAUNCH"))
}
fn fresh_absolute(p:&Path)->io::Result<()>{
    if !p.is_absolute()||p.exists()||p.is_symlink()||
        p.parent().is_none_or(|q|!q.is_dir()||q.is_symlink()){
        return Err(denied("durable original-operation marker preexists, is redirected, or is not absolute"));
    }
    Ok(())
}
/// This is the very first check on each SCM service generation, before
/// reading the input or creating an OS child. Prior markers are never
/// removed by this service, even when a signed terminal exists.
pub(crate) fn require_fresh_original()->io::Result<()>{
    let paths=[
      prelaunch_path(),
      Path::new(env!("COG_PROD_QUAL_TERMINAL")),
      Path::new(env!("COG_PROD_QUAL_TERMINAL_SIGNED")),
      Path::new(env!("COG_PROD_QUAL_RESULT_WITNESS")),
    ];
    for p in paths{fresh_absolute(p)?;}
    if paths.windows(2).any(|v|v[0]==v[1]){
        return Err(denied("distinct immutable original-operation record paths required"));
    }
    Ok(())
}
/// Write before native CreateProcessAsUserW, including before the SUSPENDED
/// child is created. create_new + sync_all leave a conservative permanent
/// fence for any crash, cancellation or partial terminal signing. No key,
/// output or user grant is ever accepted from this record.
pub(crate) fn write_prelaunch()->io::Result<[u8;32]>{
    require_fresh_original()?;
    let request=env!("COG_PROD_QUAL_REQUEST_SHA256");
    let python=env!("COG_PROD_QUAL_PYTHON_SHA256");
    let child=env!("COG_PROD_QUAL_CHILD_SHA256");
    if !valid_digest(request)||!valid_digest(python)||!valid_digest(child){
        return Err(denied("independently pinned original request/runtime identities required"));
    }
    let claim=format!(
       "{{\"schema\":\"{}\",\"original_request_sha256\":\"{}\",\"pinned_python_sha256\":\"{}\",\"pinned_child_sha256\":\"{}\",\"worker_may_have_started\":true,\"replay_after_restart_permitted\":false,\"independent_antirollback_verified\":false,\"original_Lu_Core_grant_verified\":false,\"output_or_ACK_authorized\":false}}\n",
       SCHEMA,request,python,child,
    );
    let marker=prelaunch_path();
    let mut file=OpenOptions::new().write(true).create_new(true).open(marker)?;
    file.write_all(claim.as_bytes())?;
    file.sync_all()?;
    // Do not delete or rewrite this record if any subsequent step fails.
    // Original host must verify the exact marker digest before accepting
    // the later CNG-signed terminal as a candidate claim.
    sha256(claim.as_bytes())
}
