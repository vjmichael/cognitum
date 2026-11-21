//! CI-only bounded Windows SCM R2 diagnostic refusal receipt. This never
//! represents a service stop, security attestation, Core grant or API result.
#![cfg(all(windows,any(feature="r2-restricted-fixture",feature="r3-appcontainer-fixture")))]
use std::{fs::OpenOptions,io::Write,path::Path};
pub fn refused(stage:&str,reason:&str){
    // Caller uses only fixed internal stage literals; sanitize OS error text
    // and never emit any CNG credential, source data, HMAC or arbitrary paths.
    let label=match stage{
        "keeper_start"=>"keeper_start",
        "worker_exit"=>"worker_exit",
        "stop_receipt"=>"stop_receipt",
        _=>"unknown",
    };
    let clipped=reason.chars().take(256).map(|c|
        if c.is_ascii_alphanumeric()||c==' '||c=='-'||c=='_'||c==':'{
            c
        }else{'_'}).collect::<String>();
    let folder=Path::new(env!("COG_R1_CI_PRELAUNCH"));
    let Some(root)=folder.parent() else{return;};
    #[cfg(feature="r3-appcontainer-fixture")]
    let file=root.join("r3-appcontainer-refusal.json");
    #[cfg(not(feature="r3-appcontainer-fixture"))]
    let file=root.join("r2-native-refusal.json");
    let json=format!(
        "{{\"schema\":\"cognitum.ssm.r2.CI_native_diagnostic.v1\",\"stage\":\"{}\",\"reason\":\"{}\",\"production_approved\":false,\"output_release_authorized\":false}}\n",
        label,clipped
    );
    if let Ok(mut handle)=OpenOptions::new().write(true).create_new(true).open(file){
        let _=handle.write_all(json.as_bytes());
        let _=handle.sync_all();
    }
}
