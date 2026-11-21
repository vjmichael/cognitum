# R3-R1 externally invoked AS the new nonadministrator Windows account.
# This process has no signing key, no SCM control privileges, no model tools.
# Profile generation must happen in the actual target user's logon context.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][ValidateSet('create','delete')][string]$Mode,
 [Parameter(Mandatory=$true)][string]$Root,
 [Parameter(Mandatory=$true)][string]$ExpectedUserSid
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$moniker='CognitumSsmR3CiSandboxV1'
if($env:OS -ne 'Windows_NT'){throw 'Native Windows profile creation required'}
$root=[IO.Path]::GetFullPath($Root)
if(!(Test-Path -LiteralPath $root -PathType Container)){throw 'Exact nonadmin profile I/O folder missing'}
$me=[Security.Principal.WindowsIdentity]::GetCurrent()
if($me.User.Value -cne $ExpectedUserSid -or
   $me.User.Value -in @('S-1-5-18','S-1-5-7') -or
   $me.IsSystem -or
   ([Security.Principal.WindowsPrincipal]::new($me)).IsInRole(
       [Security.Principal.WindowsBuiltInRole]::Administrator)){
 throw 'Profile owner is not the separately enrolled nonadministrator user'
}
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class CognitumR3R1OwnProfile {
 [DllImport("userenv.dll",CharSet=CharSet.Unicode)] public static extern int CreateAppContainerProfile(string name,string display,string description,IntPtr capabilities,int count,out IntPtr sid);
 [DllImport("userenv.dll",CharSet=CharSet.Unicode)] public static extern int DeleteAppContainerProfile(string name);
 [DllImport("advapi32.dll")] public static extern IntPtr FreeSid(IntPtr sid);
 [DllImport("advapi32.dll",CharSet=CharSet.Unicode,SetLastError=true)] public static extern bool ConvertSidToStringSidW(IntPtr sid,out IntPtr str);
 [DllImport("kernel32.dll")] public static extern IntPtr LocalFree(IntPtr ptr);
}
'@
$receipt=Join-Path $root 'r3-r1-user-owned-profile.json'
if($Mode -eq 'create'){
 if(Test-Path -LiteralPath $receipt){throw 'Refuse reused original user-owned profile'}
 $sid=[IntPtr]::Zero
 $hr=[CognitumR3R1OwnProfile]::CreateAppContainerProfile(
   $moniker,$moniker,'Cognitum disposable nonadmin numeric sandbox - no capabilities',
   [IntPtr]::Zero,0,[ref]$sid)
 if($hr -ne 0 -or $sid -eq [IntPtr]::Zero){
   throw ("Original nonadministrator user AppContainer registration refused HRESULT 0x"+$hr.ToString('x'))
 }
 try{
   $ptr=[IntPtr]::Zero
   if(-not [CognitumR3R1OwnProfile]::ConvertSidToStringSidW($sid,[ref]$ptr) -or
      $ptr -eq [IntPtr]::Zero){throw 'Actual AppContainer SID not issued'}
   try{$packageSid=[Runtime.InteropServices.Marshal]::PtrToStringUni($ptr)}
   finally{[void][CognitumR3R1OwnProfile]::LocalFree($ptr)}
 }finally{[void][CognitumR3R1OwnProfile]::FreeSid($sid)}
 if($packageSid -cnotmatch '^S-1-15-2-[0-9-]+$'){
   throw 'Original nonadmin profile SID not a Windows package SID'
 }
 [ordered]@{
   schema='cognitum.ssm.r3r1.CI_user_owned_appcontainer.v1'
   owner_user_sid=$ExpectedUserSid
   appcontainer_sid=$packageSid
   no_network_capabilities=$true
   owner_is_nonadministrator=$true
   production_publisher_accepted=$false
   original_Core_grant=$false
 }|ConvertTo-Json -Compress|Set-Content -LiteralPath $receipt -Encoding ascii
 Write-Output 'PASS_CI_NONADMIN_OS_USER_OWNED_APP_CONTAINER_CREATED'
}else{
 if(!(Test-Path -LiteralPath $receipt -PathType Leaf)){
   throw 'Original nonadmin created package receipt absent; cannot delete unrelated'
 }
 $old=Get-Content -LiteralPath $receipt -Raw|ConvertFrom-Json
 if($old.schema -cne 'cognitum.ssm.r3r1.CI_user_owned_appcontainer.v1' -or
    $old.owner_user_sid -cne $ExpectedUserSid -or
    $old.owner_is_nonadministrator -ne $true){
   throw 'Foreign/installer AppContainer profile deletion refused'
 }
 $hr=[CognitumR3R1OwnProfile]::DeleteAppContainerProfile($moniker)
 if($hr -ne 0){
   throw ("Cannot delete original nonadmin package from owner session HRESULT 0x"+$hr.ToString('x'))
 }
 Remove-Item -LiteralPath $receipt -Force
 Write-Output 'PASS_CI_NONADMIN_OS_USER_OWNED_APP_CONTAINER_DELETED'
}
