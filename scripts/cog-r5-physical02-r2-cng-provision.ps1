# R2 CI-only independent OS CNG machine key provisioning; never production approval.
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][ValidateSet('provision','remove')][string]$Mode,
  [Parameter(Mandatory=$true)][string]$FixtureRoot,
  [string]$EnvFile
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($env:OS -ne 'Windows_NT'){throw 'Genuine Windows machine KSP required'}
$root=[IO.Path]::GetFullPath($FixtureRoot)
if(!(Test-Path -LiteralPath $root -PathType Container)){throw 'Missing fixture root'}
$marker=Join-Path $root 'r2-external-provision.json'
$public=Join-Path $root 'r2-public-p256.blob'
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class CognitumR2CngProvision {
 const int Machine=0x20;
 [DllImport("ncrypt.dll",CharSet=CharSet.Unicode)] static extern int NCryptOpenStorageProvider(out IntPtr provider,string name,int flags);
 [DllImport("ncrypt.dll",CharSet=CharSet.Unicode)] static extern int NCryptOpenKey(IntPtr provider,out IntPtr key,string name,int legacy,int flags);
 [DllImport("ncrypt.dll",CharSet=CharSet.Unicode)] static extern int NCryptCreatePersistedKey(IntPtr provider,out IntPtr key,string algorithm,string name,int legacy,int flags);
 [DllImport("ncrypt.dll",CharSet=CharSet.Unicode)] static extern int NCryptSetProperty(IntPtr key,string name,byte[] property,int length,int flags);
 [DllImport("ncrypt.dll")] static extern int NCryptFinalizeKey(IntPtr key,int flags);
 [DllImport("ncrypt.dll",CharSet=CharSet.Unicode)] static extern int NCryptExportKey(IntPtr key,IntPtr export,string blobType,IntPtr parameters,byte[] output,int outputSize,out int written,int flags);
 [DllImport("ncrypt.dll")] static extern int NCryptDeleteKey(IntPtr key,int flags);
 [DllImport("ncrypt.dll")] static extern int NCryptFreeObject(IntPtr handle);
 static IntPtr Provider(){
   IntPtr provider;
   int s=NCryptOpenStorageProvider(out provider,"Microsoft Software Key Storage Provider",0);
   if(s!=0||provider==IntPtr.Zero)throw new InvalidOperationException("Machine KSP unavailable 0x"+s.ToString("x"));
   return provider;
 }
 public static byte[] Provision(string name){
   IntPtr provider=Provider(),key=IntPtr.Zero;
   bool created=false;
   try{
     IntPtr old;
     int status=NCryptOpenKey(provider,out old,name,0,Machine);
     if(status==0){NCryptFreeObject(old);throw new InvalidOperationException("Foreign CNG key collision");}
     status=NCryptCreatePersistedKey(provider,out key,"ECDSA_P256",name,0,Machine);
     if(status!=0||key==IntPtr.Zero)throw new InvalidOperationException("CreatePersistedKey refused 0x"+status.ToString("x"));
     created=true;
     status=NCryptSetProperty(key,"Export Policy",new byte[]{0,0,0,0},4,0);
     if(status!=0)throw new InvalidOperationException("Nonexportable policy refused 0x"+status.ToString("x"));
     status=NCryptFinalizeKey(key,0);
     if(status!=0)throw new InvalidOperationException("FinalizeKey refused 0x"+status.ToString("x"));
     byte[] blob=new byte[72]; int written=0;
     status=NCryptExportKey(key,IntPtr.Zero,"ECCPUBLICBLOB",IntPtr.Zero,blob,72,out written,0);
     if(status!=0||written!=72||blob[0]!=0x45||blob[1]!=0x43||blob[2]!=0x53||blob[3]!=0x31)
       throw new InvalidOperationException("P256 ECCPUBLICBLOB invalid");
     return blob;
   }catch{
     if(created&&key!=IntPtr.Zero&&NCryptDeleteKey(key,0)==0)key=IntPtr.Zero;
     throw;
   }finally{
     if(key!=IntPtr.Zero)NCryptFreeObject(key);
     NCryptFreeObject(provider);
   }
 }
 public static void Remove(string name){
   IntPtr provider=Provider();
   try{
     IntPtr key;
     int s=NCryptOpenKey(provider,out key,name,0,Machine);
     if(s!=0||key==IntPtr.Zero)throw new InvalidOperationException("Original test CNG signer absent");
     s=NCryptDeleteKey(key,0);
     if(s!=0){NCryptFreeObject(key);throw new InvalidOperationException("CNG cleanup failed 0x"+s.ToString("x"));}
   }finally{NCryptFreeObject(provider);}
 }
}
'@
if($Mode -eq 'provision'){
  if(-not $EnvFile -or -not [IO.Path]::IsPathRooted($EnvFile)){throw 'Explicit absolute GitHub ENV destination required'}
  if(Test-Path -LiteralPath $marker){throw 'Foreign prior R2 enrollment; no silent replacement'}
  $name='CognitumR2CiStopP256V1-'+[Guid]::NewGuid().ToString('N').Substring(0,16)
  $blob=[CognitumR2CngProvision]::Provision($name)
  [IO.File]::WriteAllBytes($public,$blob)
  $hash=[Security.Cryptography.SHA256]::HashData($blob)
  $pin=[Convert]::ToHexString($hash).ToLowerInvariant()
  $body=[ordered]@{
    schema='cognitum.ssm.r2.CI_external_KSP_enrollment.v1'
    name=$name
    public_blob_sha256=$pin
    externally_provisioned_machine_key=$true
    nonexportable_key_policy=$true
    independent_production_publisher_approved=$false
    externally_anchored_antirollback=$false
  }
  ($body|ConvertTo-Json) | Set-Content -LiteralPath $marker -Encoding utf8
  $lines=@(
    "COG_R2_CI_KEY_NAME=$name",
    "COG_R2_CI_PUBLIC_SHA256=$pin",
    ("COG_R2_CI_SIGNED_STOP="+(Join-Path $root 'r2-signed-stop.json'))
  )
  [IO.File]::AppendAllText($EnvFile,(([string]::Join([Environment]::NewLine,$lines))+[Environment]::NewLine))
  Write-Host 'PASS_CI_EXTERNALLY_PROVISIONED_NONEXPORTABLE_MACHINE_CNG_ONLY'
}else{
  if(!(Test-Path -LiteralPath $marker -PathType Leaf)){throw 'No independent provision marker; refuse arbitrary key deletion'}
  $body=Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
  if($body.schema -cne 'cognitum.ssm.r2.CI_external_KSP_enrollment.v1' -or
     $body.name -cnotmatch '^CognitumR2CiStopP256V1-[0-9a-f]{16}$'){
    throw 'Foreign R2 signer key identity'
  }
  [CognitumR2CngProvision]::Remove([string]$body.name)
  Remove-Item -LiteralPath $marker -Force
  Write-Host 'PASS_CI_CNG_SIGNER_REVOKED'
}
