//! R3-R1 all-file SHA256 verification for externally staged, closed numerical
//! CPython + NumPy/SciPy + reviewed Cognitum imports. A test-only exact
//! original manifest digest is pinned INTO the SCM binary at compilation.
//!
//! This cannot replace signed installer/PE publisher/cert, protected OS image
//! handles, privileged antirollback or trusted Core original authorization.
//! Fail closed before signing admission or creating a child. No dynamic
//! package download, tool/plugin discovery or additional IPC entrypoints.
#![cfg(all(windows,feature="r3-r1-frozen-fixture"))]
use std::{fs,io,path::{Path,Component}};
type Result<T>=std::result::Result<T,io::Error>;
const MAX_MANIFEST:usize=3*1024*1024;
const MAX_FILE:usize=64*1024*1024;
const MAX_FILES:usize=12000;
fn refused(message:&str)->io::Error{
    io::Error::new(io::ErrorKind::PermissionDenied,message.to_owned())
}
fn hex(bytes:&[u8])->String{
    const D:&[u8]=b"0123456789abcdef";
    let mut s=String::with_capacity(bytes.len()*2);
    for b in bytes{s.push(D[(b>>4) as usize] as char);s.push(D[(b&15) as usize] as char);}
    s
}
fn sha(raw:&[u8])->Result<String>{
    Ok(hex(&crate::r2_signer::r3_sha_image(raw)?))
}
pub fn verify()->Result<()>{
    let root=Path::new(env!("COG_R3_R1_RUNTIME_ROOT"));
    if !root.is_absolute()||root.is_symlink()||!root.is_dir(){
        return Err(refused("externally pinned frozen Windows SSM root missing"));
    }
    let pinned_root=root.canonicalize().map_err(|_|refused("frozen root inaccessible"))?;
    let manifest=root.join("r3-r1-runtime.manifest");
    if !manifest.is_file()||manifest.is_symlink(){
        return Err(refused("original immutable SSM dependency manifest missing"));
    }
    let bytes=fs::read(&manifest)?;
    if bytes.is_empty()||bytes.len()>MAX_MANIFEST||
       sha(&bytes)?!=env!("COG_R3_R1_RUNTIME_MANIFEST_SHA256"){
        return Err(refused("build-pinned full dependency manifest digest mismatch"));
    }
    let text=std::str::from_utf8(&bytes)
        .map_err(|_|refused("original runtime manifest is not ASCII"))?;
    let mut last="";
    let mut count=0usize;
    for line in text.split_terminator('\n'){
        count+=1;
        if count>MAX_FILES||line.contains('\r'){
            return Err(refused("bounded immutable runtime file count/encoding"));
        }
        let (digest,rel)=line.split_once('\t')
            .ok_or_else(||refused("original runtime file line missing SHA256"))?;
        if digest.len()!=64||
            !digest.bytes().all(|b|b.is_ascii_digit()||(b'a'..=b'f').contains(&b))||
            rel.is_empty()||rel.len()>260||rel.contains('\t')||
            !rel.bytes().all(|b|b.is_ascii_graphic()||b==b' ')||
            rel<=last{
            return Err(refused("noncanonical or reordered approved runtime filename/digest"));
        }
        last=rel;
        let relative=Path::new(rel);
        if relative.is_absolute()||
           relative.components().any(|part|!matches!(part,Component::Normal(_))){
            return Err(refused("runtime attempted relative traversal"));
        }
        let file=root.join(relative);
        if file.is_symlink()||!file.is_file(){
            return Err(refused("original frozen import/DLL missing or redirected"));
        }
        let actual=file.canonicalize().map_err(|_|refused("runtime file unresolved"))?;
        if !actual.starts_with(&pinned_root)||
           actual.as_os_str()==pinned_root.as_os_str(){
            return Err(refused("original runtime DLL escaped frozen package root"));
        }
        let meta=fs::metadata(&file)?;
        if !meta.is_file()||meta.len()>MAX_FILE as u64 {
            return Err(refused("original frozen dependency exceeds size bound"));
        }
        let raw=fs::read(&file)?;
        if sha(&raw)?!=digest{
            return Err(refused("pinned runtime binary, Python import or DLL tampered"));
        }
    }
    if count==0{
        return Err(refused("empty original full-import manifest"));
    }
    // Additional executable/script hash is checked against separately build-
    // pinned CNG source SHA in ssm_fixture::prepare before first child.
    Ok(())
}
