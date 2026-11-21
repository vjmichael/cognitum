# Verify a genuine Windows SCM service owns a native fixed diagnostic Job.
# This is temporary unsigned CI fixture acceptance, NEVER signed production.
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Executable,
  [Parameter(Mandatory=$true)][string]$EvidencePath
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($env:OS -ne 'Windows_NT'){throw 'SCM requires actual Windows'}
$service='CognitumSsmNativeFixtureV1'
$resolved=[IO.Path]::GetFullPath($Executable)
if(-not (Test-Path -LiteralPath $resolved -PathType Leaf)){throw 'Fixed SCM binary is missing'}
if(-not [IO.Path]::IsPathRooted($EvidencePath)){throw 'Absolute CI evidence destination required'}
if(Get-CimInstance Win32_Service -Filter "Name='$service'"){
  throw 'Foreign prior service with same fixed name exists; refuse to mutate it'
}
$created=$false
$observed=$null
$pidWorker=0
try {
  & $resolved
  if($LASTEXITCODE -eq 0){throw 'Manual non-SCM invocation did not refuse'}
  & sc.exe create $service 'binPath=' ('"'+$resolved+'"') 'start=' 'demand' 'obj=' 'LocalSystem'
  if($LASTEXITCODE -ne 0){throw 'SCM CreateService failed'}
  $created=$true
  & sc.exe start $service
  if($LASTEXITCODE -ne 0){throw 'SCM StartService failed'}
  $deadline=[DateTime]::UtcNow.AddSeconds(10)
  while([DateTime]::UtcNow -lt $deadline) {
    $observed=Get-CimInstance Win32_Service -Filter "Name='$service'"
    if($observed -and $observed.State -eq 'Running' -and [uint32]$observed.ProcessId -gt 0){break}
    Start-Sleep -Milliseconds 150
  }
  if(!$observed -or $observed.State -ne 'Running' -or [uint32]$observed.ProcessId -eq 0){
    throw 'Real SCM service never reached RUNNING'
  }
  if($observed.ServiceType -notlike '*Own Process*' -or
     $observed.StartName -notin @('LocalSystem','NT AUTHORITY\\LocalSystem')){
    throw 'SCM own-process LocalSystem identity not observed'
  }
  $pidService=[uint32]$observed.ProcessId
  $main=Get-CimInstance Win32_Process -Filter ("ProcessId="+$pidService)
  if(!$main -or [uint32]$main.SessionId -ne 0){throw 'Live SCM service session 0 missing'}
  $owner=Invoke-CimMethod -InputObject $main -MethodName GetOwnerSid
  if($owner.ReturnValue -ne 0 -or $owner.Sid -cne 'S-1-5-18'){
    throw 'Live SCM process does not have SYSTEM token SID'
  }
  $deadline=[DateTime]::UtcNow.AddSeconds(6)
  $child=$null
  while([DateTime]::UtcNow -lt $deadline){
    $candidates=@(Get-CimInstance Win32_Process -Filter ("ParentProcessId="+$pidService))
    $child=$candidates | Where-Object { $_.CommandLine -like '*--cognitum-fixed-custody-child*' } | Select-Object -First 1
    if($child){break}
    Start-Sleep -Milliseconds 100
  }
  if(!$child){throw 'SCM worker child not observed under original service process'}
  $pidWorker=[uint32]$child.ProcessId
  Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class NativeCognitumJobWitness {
  [DllImport("kernel32.dll", SetLastError=true)] public static extern IntPtr OpenProcess(uint access,bool inherit,int pid);
  [DllImport("kernel32.dll", SetLastError=true)] [return: MarshalAs(UnmanagedType.Bool)] public static extern bool IsProcessInJob(IntPtr process,IntPtr job,[MarshalAs(UnmanagedType.Bool)] out bool result);
  [DllImport("kernel32.dll", SetLastError=true)] [return: MarshalAs(UnmanagedType.Bool)] public static extern bool CloseHandle(IntPtr handle);
}
'@
  $handle=[NativeCognitumJobWitness]::OpenProcess(0x1000,$false,[int]$pidWorker)
  if($handle -eq [IntPtr]::Zero){throw 'Unable to independently open SCM worker process'}
  try {
    $inJob=$false
    if(-not [NativeCognitumJobWitness]::IsProcessInJob($handle,[IntPtr]::Zero,[ref]$inJob) -or !$inJob){
      throw 'OS does not independently observe fixed child Job membership'
    }
  } finally { [void][NativeCognitumJobWitness]::CloseHandle($handle) }
  & sc.exe stop $service
  if($LASTEXITCODE -ne 0){throw 'SCM StopService command failed'}
  $deadline=[DateTime]::UtcNow.AddSeconds(10)
  while([DateTime]::UtcNow -lt $deadline){
    $status=Get-CimInstance Win32_Service -Filter "Name='$service'"
    if($status -and $status.State -eq 'Stopped'){break}
    Start-Sleep -Milliseconds 150
  }
  if(!$status -or $status.State -ne 'Stopped') {throw 'SCM service not stopped'}
  if(Get-Process -Id $pidWorker -ErrorAction SilentlyContinue){
    throw 'Fixed Job child survived SCM stop'
  }
  $report=[ordered]@{
    schema='cognitum.ssm_r5.scminternal_ephemeral_fixture.v1';
    status='PASS_GENUINE_CI_SCM_FIXTURE_ONLY';
    service=$service; service_pid=$pidService; child_pid=$pidWorker;
    service_local_system_sid_observed=$true;
    service_session_zero_observed=$true;
    child_parent_is_scm_service=$true;
    child_kernel_job_membership_observed=$true;
    child_gone_after_scm_stop=$true;
    installed_signed_cognitum_production_service=$false;
    fixed_ssm_operation_executed_under_scm=$false;
    independent_signed_stop_receipt_issued=$false;
    actual_lu_core_health_authenticated=$false;
    model_tool_or_outbox_authorized=$false;
  }
  ($report | ConvertTo-Json -Depth 4) | Set-Content -LiteralPath $EvidencePath -Encoding utf8
  Write-Host 'PASS_GENUINE_CI_SCM_FIXTURE_ONLY'
} finally {
  if($created){
    try{& sc.exe stop $service | Out-Null}catch{}
    try{& sc.exe delete $service | Out-Null}catch{}
  }
}
