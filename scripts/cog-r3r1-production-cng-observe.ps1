# R3-R1 PRODUCTION SUCCESSOR: read-only machine CNG signer custody observation.
# The signer is PREEXISTING and independently provisioned. This tool may only
# OPEN, inspect and hash its public ECDSA_P256 identity. Never create/import,
# sign, export private material, weaken ACLs, enroll Core, start an SCM worker,
# consume an operation, or deliver/ACK output. CI may run the same verifier
# against a separately created disposable CI signer with explicit opt-in.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$ExistingMachineKeyName,
 [Parameter(Mandatory=$true)][string]$ApprovedPublicBlobSha256,
 [switch]$CiDiagnosticOnly
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function Refuse([string]$why){throw ('COG_R3R1_PRODUCTION_CNG_REFUSED: '+$why)}
if($env:OS -cne 'Windows_NT' -or -not [Environment]::Is64BitProcess){
 Refuse 'Original native 64-bit Windows CNG KSP required'
}
if($CiDiagnosticOnly -and $env:GITHUB_ACTIONS -cne 'true'){
 Refuse 'Disposable diagnostic flag forbidden outside GitHub Actions'
}
if(-not $CiDiagnosticOnly -and $env:GITHUB_ACTIONS -eq 'true'){
 Refuse 'CI machine identity cannot masquerade as enrolled production signer'
}
if($ExistingMachineKeyName -cnotmatch '^[A-Za-z][A-Za-z0-9_-]{7,95}$' -or
   $ApprovedPublicBlobSha256 -cnotmatch '^[0-9a-f]{64}$' -or
   $ApprovedPublicBlobSha256 -ceq ('0'*64)){
 Refuse 'Externally pinned nonzero key name and full lowercase digest required'
}
# This native API uses *only* NCryptOpenKey(MACHINE_KEY_FLAG). A matching
# current-user key or caller-supplied file cannot substitute for OS custody.
# The public blob has 8-byte BCRYPT_ECCKEY_BLOB header + 32-byte X + 32-byte Y.
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class CognitumR3R1CngObserve {
 const int Machine=0x20;
 const uint ECDSA_P256_PUBLIC_MAGIC=0x31534345; // "ECS1", little endian
 [DllImport("ncrypt.dll",CharSet=CharSet.Unicode)]
 static extern int NCryptOpenStorageProvider(out IntPtr provider,string name,int flags);
 [DllImport("ncrypt.dll",CharSet=CharSet.Unicode)]
 static extern int NCryptOpenKey(IntPtr provider,out IntPtr key,string name,int legacy,int flags);
 [DllImport("ncrypt.dll",CharSet=CharSet.Unicode)]
 static extern int NCryptGetProperty(IntPtr key,string name,byte[] data,int dataLen,out int used,int flags);
 [DllImport("ncrypt.dll",CharSet=CharSet.Unicode)]
 static extern int NCryptExportKey(IntPtr key,IntPtr export,string blobKind,IntPtr parameters,byte[] output,int length,out int used,int flags);
 [DllImport("ncrypt.dll")] static extern int NCryptFreeObject(IntPtr obj);
 static void Need(bool ok, string what){
   if(!ok)throw new InvalidOperationException("Machine CNG observation refused: "+what);
 }
 public static byte[] Inspect(string name){
   IntPtr provider=IntPtr.Zero,key=IntPtr.Zero;
   try{
     int s=NCryptOpenStorageProvider(out provider,"Microsoft Software Key Storage Provider",0);
     Need(s==0 && provider!=IntPtr.Zero,"named native machine provider absent");
     s=NCryptOpenKey(provider,out key,name,0,Machine);
     Need(s==0 && key!=IntPtr.Zero,"preexisting machine key missing");
     byte[] policy=new byte[4];int length=0;
     s=NCryptGetProperty(key,"Export Policy",policy,policy.Length,out length,0);
     Need(s==0 && length==4 && BitConverter.ToUInt32(policy,0)==0,
          "key allows private material export or export policy unreadable");
     byte[] alg=new byte[128];
     length=0;
     s=NCryptGetProperty(key,"Algorithm Name",alg,alg.Length,out length,0);
     Need(s==0 && length>=4 && length<=alg.Length && (length%2)==0,
          "original key algorithm identity unavailable");
     string algorithm=System.Text.Encoding.Unicode.GetString(alg,0,length).TrimEnd('\0');
     Need(algorithm=="ECDSA_P256","unexpected key algorithm");
     byte[] usage=new byte[4];
     length=0;
     s=NCryptGetProperty(key,"Key Usage",usage,usage.Length,out length,0);
     Need(s==0 && length==4 && (BitConverter.ToUInt32(usage,0)&2u)!=0,
          "native signing usage not allowed");
     byte[] blob=new byte[72];
     length=0;
     s=NCryptExportKey(key,IntPtr.Zero,"ECCPUBLICBLOB",IntPtr.Zero,
                       blob,blob.Length,out length,0);
     Need(s==0 && length==72,"complete ECDSA P256 public blob missing");
     Need(BitConverter.ToUInt32(blob,0)==ECDSA_P256_PUBLIC_MAGIC &&
          BitConverter.ToUInt32(blob,4)==32u,
          "not an exact Microsoft ECDSA P256 public representation");
     return blob;
   } finally {
     if(key!=IntPtr.Zero)NCryptFreeObject(key);
     if(provider!=IntPtr.Zero)NCryptFreeObject(provider);
   }
 }
}
'@ -ErrorAction Stop
try{
 $publicBytes=[CognitumR3R1CngObserve]::Inspect($ExistingMachineKeyName)
}catch{
 # Do not expose native key provider output, certificate store paths, or any
 # private-key details in observational release receipts.
 Refuse 'Preexisting native nonexportable ECDSA_P256 machine signer not admitted'
}
if($publicBytes.Length -ne 72){Refuse 'Noncanonical Windows P256 public blob'}
$observed=([Convert]::ToHexString(
 [Security.Cryptography.SHA256]::HashData($publicBytes))).ToLowerInvariant()
if($observed -cne $ApprovedPublicBlobSha256){
 Refuse 'Existing signer differs from independently approved public identity'
}
[pscustomobject]@{
 schema='cognitum.ssm.r3r1.production_cng_observation.v1'
 status=if($CiDiagnosticOnly){
   'PASS_CI_PREEXISTING_MACHINE_CNG_PUBLIC_IDENTITY_OBSERVATION_ONLY'
 }else{
   'PASS_PREEXISTING_MACHINE_CNG_PUBLIC_IDENTITY_OBSERVATION_ONLY'
 }
 public_blob_sha256=$observed
 machine_key_existing=$true
 algorithm='ECDSA_P256'
 provider='Microsoft Software Key Storage Provider'
 private_export_policy_disabled=$true
 signing_usage_present=$true
 key_created_or_changed=$false
 private_key_exported=$false
 original_installed_publisher_approved=$false
 external_Core_issuer_enrolled=$false
 one_use_Core_grant_verified=$false
 durable_terminal_receipts_signed=$false
 installed_worker_accepted=$false
 output_or_ACK_authorized=$false
}|ConvertTo-Json -Compress
