# R3 externally provisioned CI-only AppContainer profile and original user peer.
# Never production profile approval. No passwords, no elevation of SCM child,
# no network capabilities, no LocalSystem worker fallback.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][ValidateSet('provision','remove')][string]$Mode,
 [Parameter(Mandatory=$true)][string]$FixtureRoot,
 [string]$EnvFile
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($env:OS -ne 'Windows_NT'){throw 'Real Windows AppContainer required'}
$root=[IO.Path]::GetFullPath($FixtureRoot)
if(!(Test-Path -LiteralPath $root -PathType Container)){throw 'Fixed R3 original staging folder missing'}
$manifest=Join-Path $root 'r3-external-appcontainer.json'
$profile='CognitumSsmR3CiSandboxV1'
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class CognitumR3AppProfile {
 [DllImport("userenv.dll",CharSet=CharSet.Unicode)] static extern int CreateAppContainerProfile(string name,string display,string description,IntPtr capabilities,int count,out IntPtr sid);
 [DllImport("userenv.dll",CharSet=CharSet.Unicode)] static extern int DeleteAppContainerProfile(string name);
 [DllImport("advapi32.dll")] static extern IntPtr FreeSid(IntPtr sid);
 [DllImport("advapi32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern bool ConvertSidToStringSidW(IntPtr sid,out IntPtr str);
 [DllImport("kernel32.dll")] static extern IntPtr LocalFree(IntPtr ptr);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool GetProcessTimes(IntPtr process,out long creation,out long exit,out long kernel,out long user);
 public static string Provision(string name) {
   IntPtr sid=IntPtr.Zero;
   int hr=CreateAppContainerProfile(name,name,"Cognitum temporary R3 numerical source test - no capabilities",IntPtr.Zero,0,out sid);
   if(hr!=0||sid==IntPtr.Zero)throw new InvalidOperationException("Native AppContainer profile was not registered, HRESULT 0x"+hr.ToString("x"));
   try {
     IntPtr raw=IntPtr.Zero;
     if(!ConvertSidToStringSidW(sid,out raw)||raw==IntPtr.Zero)
       throw new InvalidOperationException("Profile SID unavailable from Windows");
     try{return Marshal.PtrToStringUni(raw);}
     finally{LocalFree(raw);}
   }finally{FreeSid(sid);}
 }
 public static void Remove(string name) {
   int hr=DeleteAppContainerProfile(name);
   if(hr!=0)throw new InvalidOperationException("Original temporary AppContainer profile deletion failed 0x"+hr.ToString("x"));
 }
 public static ulong Birth(IntPtr handle) {
   long creation,exit,kernel,user;
   if(!GetProcessTimes(handle,out creation,out exit,out kernel,out user)||creation<=0)
     throw new InvalidOperationException("Original peer process FILETIME unavailable");
   return (ulong)creation;
 }
}
'@
if($Mode -eq 'provision'){
  if(-not $EnvFile -or -not [IO.Path]::IsPathRooted($EnvFile)){
    throw 'Exact GitHub environment file must be absolute'
  }
  if(Test-Path -LiteralPath $manifest){throw 'Foreign preexisting AppContainer fixture cannot be adopted'}
  $python=[IO.Path]::GetFullPath($env:COG_R1_CI_PYTHON)
  if(!(Test-Path -LiteralPath $python -PathType Leaf)){throw 'Original Python interpreter not pinned'}
  $source=[IO.Path]::GetFullPath((Join-Path $PWD 'cognitum'))
  if(!(Test-Path -LiteralPath $source -PathType Container)){throw 'Reviewed Cognitum original source missing'}
  $sid=$null
  $peer=$null
  try {
    $sid=[CognitumR3AppProfile]::Provision($profile)
    if($sid -cnotmatch '^S-1-15-2-[0-9-]+$'){
      throw 'Windows AppContainer profile not independently given a package SID'
    }
    $peer=Start-Process -FilePath $python -ArgumentList @('-c','"import time;time.sleep(180)"') -PassThru -WindowStyle Hidden
    Start-Sleep -Milliseconds 100
    $peer.Refresh()
    if($peer.HasExited){throw 'Test-only original user peer died before OS admission'}
    $pidPeer=[uint32]$peer.Id
    $wmi=Get-CimInstance Win32_Process -Filter ("ProcessId="+$pidPeer)
    if(!$wmi){throw 'Original non-System peer process session unavailable'}
    # Session 0 can belong to a dedicated non-System service worker identity.
    # Actual TokenUser is still verified and SYSTEM is refused below.
    $owner=Invoke-CimMethod -InputObject $wmi -MethodName GetOwnerSid
    if($owner.ReturnValue -ne 0 -or !$owner.Sid -or
       $owner.Sid -in @('S-1-5-18','S-1-5-7')){
      throw 'Original peer token is SYSTEM/anonymous or not OS identifiable'
    }
    $birth=[CognitumR3AppProfile]::Birth($peer.Handle)
    $imageSha=(Get-FileHash -LiteralPath $python -Algorithm SHA256).Hash.ToLowerInvariant()
    # Grant only the AppContainer package SID read-execute on native Python
    # runtime and reviewed source, and test-data write access in the isolated
    # ephemeral staging root. No BUILTIN Users/Everyone write on installed code.
    $grantRX='*'+$sid+':(OI)(CI)RX'
    $grantM='*'+$sid+':(OI)(CI)M'
    $pythonRoot=Split-Path -Parent $python
    # Restricted/AppContainer tokens cannot rely on privileged traverse
    # rights of the service host. Grant this exact test package READ/TRAVERSE
    # (not WRITE, not inheritance) on every existing ancestor, including
    # the drive and GitHub-hosted Python/runtime and source ancestors.
    foreach($protectedLeaf in @($pythonRoot,$source,$root)){
      $cursor=Get-Item -LiteralPath $protectedLeaf -Force
      while($cursor){
        if(($cursor.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
          throw 'Fixed Python/SSM/AppContainer parent ancestry contains reparse point'
        }
        $parent=$cursor.Parent
        if($parent){
          $traverse='*'+$sid+':(RX)'
          & icacls.exe $parent.FullName /grant $traverse /Q
          if($LASTEXITCODE -ne 0){
            throw 'Temporary AppContainer SID missing exact ancestor read/traverse grant'
          }
        }
        $cursor=$parent
      }
    }
    & icacls.exe $pythonRoot /grant $grantRX /T /C /Q
    if($LASTEXITCODE -ne 0){throw 'R3 AppContainer read-only pinned Python runtime ACL not installed'}
    & icacls.exe $source /grant $grantRX /T /C /Q
    if($LASTEXITCODE -ne 0){throw 'R3 AppContainer read-only Cognitum source ACL not installed'}
    & icacls.exe $root /grant $grantM /T /C /Q
    if($LASTEXITCODE -ne 0){throw 'R3 AppContainer temporary numerical data ACL unavailable'}
    $witness=Join-Path $root 'r3-original-appcontainer-witness.json'
    [ordered]@{
      schema='cognitum.ssm.r3.external_CI_AppContainer_profile.v1'
      profile=$profile
      profile_sid=$sid
      original_peer_pid=$pidPeer
      original_peer_session=[uint32]$wmi.SessionId
      original_peer_birth=$birth
      original_peer_user_sid=$owner.Sid
      original_peer_image_sha256=$imageSha
      profile_created_outside_SCM=$true
      network_capabilities_granted=$false
      original_worker_USER_not_SYSTEM=$true
      production_installed_publisher_approved=$false
      independent_Core_enrollment=$false
    } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $manifest -Encoding utf8
    $lines=@(
      "COG_R3_CI_PEER_PID=$pidPeer",
      "COG_R3_CI_PEER_BIRTH=$birth",
      ("COG_R3_CI_PEER_SID="+$owner.Sid),
      "COG_R3_CI_PEER_IMAGE_SHA256=$imageSha",
      "COG_R3_CI_PROFILE=$profile",
      "COG_R3_CI_APP_SID=$sid",
      "COG_R3_CI_APP_WITNESS=$witness"
    )
    [IO.File]::AppendAllText($EnvFile,[string]::Join([Environment]::NewLine,$lines)+[Environment]::NewLine)
    Write-Host 'PASS_CI_NATIVE_EXTERNALLY_PINNED_NON_SYSTEM_APP_CONTAINER_PROFILE'
  }catch {
    if($peer -and -not $peer.HasExited) {
      try{Stop-Process -Id $peer.Id -Force -ErrorAction Stop}catch{}
    }
    if($sid){try{[CognitumR3AppProfile]::Remove($profile)}catch{}}
    throw
  }
}else{
  if(!(Test-Path -LiteralPath $manifest -PathType Leaf)){throw 'No reviewed exact external AppContainer fixture identity to clean'}
  $body=Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
  if($body.schema -cne 'cognitum.ssm.r3.external_CI_AppContainer_profile.v1' -or
     $body.profile -cne $profile -or
     $body.production_installed_publisher_approved -ne $false){
    throw 'Foreign/production AppContainer profile cannot be removed by CI'
  }
  $oldPid=[uint32]$body.original_peer_pid
  $live=Get-Process -Id $oldPid -ErrorAction SilentlyContinue
  if($live){
    $birth=[CognitumR3AppProfile]::Birth($live.Handle)
    if([ulong]$birth -ne [ulong]$body.original_peer_birth){
      throw 'Original peer PID recycled: refuse unrelated process termination'
    }
    Stop-Process -Id $oldPid -Force -ErrorAction Stop
  }
  [CognitumR3AppProfile]::Remove($profile)
  Remove-Item -LiteralPath $manifest -Force
  Write-Host 'PASS_CI_APP_CONTAINER_PROFILE_DELETION_REQUESTED_AND_ORIGINAL_PEER_REAPED'
}
