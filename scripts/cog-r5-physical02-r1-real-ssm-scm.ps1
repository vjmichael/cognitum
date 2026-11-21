# R1: genuine ephemeral Windows SCM-owned REAL fixed SSM fixture.
# Only the TEST-ONLY per-run HMAC intent is accepted, compiled into the
# unsigned binary. This is NOT trusted Core issuer / production service.
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Executable,
  [Parameter(Mandatory=$true)][string]$FixtureRoot,
  [Parameter(Mandatory=$true)][string]$EvidencePath
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($env:OS -ne 'Windows_NT'){throw 'Native Windows SCM required'}
$svc='CognitumSsmNativeFixtureV1'
$exe=[IO.Path]::GetFullPath($Executable)
$root=[IO.Path]::GetFullPath($FixtureRoot)
$evidence=[IO.Path]::GetFullPath($EvidencePath)
$stop=[IO.Path]::Combine($root,'stop.json')
$prelaunch=[IO.Path]::Combine($root,'prelaunch.json')
$output=[IO.Path]::Combine($root,'output.frame')
if(!(Test-Path -LiteralPath $exe -PathType Leaf) -or
   !(Test-Path -LiteralPath $root -PathType Container)){
  throw 'Missing exact fixed service binary or CI fixture root'
}
if(Get-CimInstance Win32_Service -Filter "Name='$svc'"){
  throw 'Refuse preexisting foreign SCM service'
}
$created=$false
$deletionConfirmed=$false
try {
  # Untrusted interactive launch MUST not substitute for SCM admission.
  & $exe
  if($LASTEXITCODE -eq 0){throw 'Direct non-SCM binary launch was accepted'}
  & sc.exe create $svc 'binPath=' ('"'+$exe+'"') 'start=' 'demand' 'obj=' 'LocalSystem'
  if($LASTEXITCODE -ne 0){throw 'CreateServiceW failed'}
  $created=$true
  & sc.exe start $svc
  if($LASTEXITCODE -ne 0){throw 'First native SCM start failed'}
  $deadline=[DateTime]::UtcNow.AddSeconds(10)
  $observed=$null
  while([DateTime]::UtcNow -lt $deadline){
    $observed=Get-CimInstance Win32_Service -Filter "Name='$svc'"
    if($observed -and $observed.State -eq 'Running' -and
       [uint32]$observed.ProcessId -gt 0){break}
    Start-Sleep -Milliseconds 100
  }
  if(!$observed -or $observed.State -ne 'Running' -or
     [uint32]$observed.ProcessId -eq 0){
    throw 'Real fixed SSM SCM service never entered RUNNING'
  }
  $pidService=[uint32]$observed.ProcessId
  if($observed.ServiceType -notlike '*Own Process*' -or
     $observed.StartName -notin @('LocalSystem','NT AUTHORITY\LocalSystem')){
    throw 'SCM dedicated LocalSystem service identity refused'
  }
  $main=Get-CimInstance Win32_Process -Filter ("ProcessId="+$pidService)
  if(!$main -or [uint32]$main.SessionId -ne 0){
    throw 'SCM process session zero unavailable'
  }
  $owner=Invoke-CimMethod -InputObject $main -MethodName GetOwnerSid
  if($owner.ReturnValue -ne 0 -or $owner.Sid -cne 'S-1-5-18'){
    throw 'SCM service live token is not LocalSystem'
  }
  $childObserved=$false
  $childJobObserved=$false
  $childRestrictedObserved=$false
  $deadline=[DateTime]::UtcNow.AddSeconds(10)
  # Parent service alone knows its exact Job HANDLE. Independent observer
  # can sometimes see a running Python child and its OS Job membership.
  Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class CognitumR1JobObserve {
  [DllImport("kernel32.dll", SetLastError=true)] public static extern IntPtr OpenProcess(uint access,bool inherit,int pid);
  [DllImport("kernel32.dll", SetLastError=true)] [return: MarshalAs(UnmanagedType.Bool)] public static extern bool IsProcessInJob(IntPtr process,IntPtr job,[MarshalAs(UnmanagedType.Bool)] out bool member);
  [DllImport("kernel32.dll", SetLastError=true)] [return: MarshalAs(UnmanagedType.Bool)] public static extern bool CloseHandle(IntPtr handle);
  [DllImport("advapi32.dll", SetLastError=true)] [return: MarshalAs(UnmanagedType.Bool)] public static extern bool OpenProcessToken(IntPtr process,uint access,out IntPtr token);
  [DllImport("advapi32.dll", SetLastError=true)] [return: MarshalAs(UnmanagedType.Bool)] public static extern bool IsTokenRestricted(IntPtr token);
}
'@
  while([DateTime]::UtcNow -lt $deadline){
    $children=@(Get-CimInstance Win32_Process -Filter ("ParentProcessId="+$pidService))
    $child=$children | Where-Object {
      $_.CommandLine -like '*ssm_r5_fixed_child.py*'
    } | Select-Object -First 1
    if($child){
      $childObserved=$true
      $handle=[CognitumR1JobObserve]::OpenProcess(0x1000,$false,[int]$child.ProcessId)
      if($handle -ne [IntPtr]::Zero){
        try{
          $member=$false
          if([CognitumR1JobObserve]::IsProcessInJob($handle,[IntPtr]::Zero,[ref]$member) -and $member){
            $childJobObserved=$true
          }
          if($env:COG_R2_CI_KEY_NAME) {
            $token=[IntPtr]::Zero
            if([CognitumR1JobObserve]::OpenProcessToken($handle,0x8,[ref]$token) -and
               $token -ne [IntPtr]::Zero){
              try {
                if([CognitumR1JobObserve]::IsTokenRestricted($token)){
                  $childRestrictedObserved=$true
                }
              } finally { [void][CognitumR1JobObserve]::CloseHandle($token) }
            }
          }
        }finally{[void][CognitumR1JobObserve]::CloseHandle($handle)}
      }
    }
    if(Test-Path -LiteralPath $output -PathType Leaf){break}
    Start-Sleep -Milliseconds 75
  }
  if(!(Test-Path -LiteralPath $output -PathType Leaf)){
    throw 'Actual SSM fixed worker did not produce its numerical candidate'
  }
  if(!(Test-Path -LiteralPath $prelaunch -PathType Leaf)){
    throw 'Durable original-operation-bound HMAC prelaunch missing'
  }
  $outputSha=(Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash.ToLowerInvariant()
  & sc.exe stop $svc
  if($LASTEXITCODE -ne 0){throw 'StopServiceW failed'}
  $deadline=[DateTime]::UtcNow.AddSeconds(10)
  $observedStop=$null
  while([DateTime]::UtcNow -lt $deadline){
    $observedStop=Get-CimInstance Win32_Service -Filter "Name='$svc'"
    if($observedStop -and $observedStop.State -eq 'Stopped'){break}
    Start-Sleep -Milliseconds 100
  }
  if(!$observedStop -or $observedStop.State -ne 'Stopped'){
    throw 'SCM-owned numerical worker service failed to STOP'
  }
  if(!(Test-Path -LiteralPath $stop -PathType Leaf)){
    throw 'Service-owned durable kernel-empty stop record absent'
  }
  $stopped=Get-Content -LiteralPath $stop -Raw | ConvertFrom-Json
  if($stopped.schema -cne 'cognitum.ssm.r1.scm_local_stop.v1' -or
     $stopped.independently_signed -ne $false -or
     $stopped.output_release_authorized -ne $false -or
     $stopped.kernel_job_empty -ne $true -or
     [uint32]$stopped.service_pid -ne $pidService){
    throw 'SCM service-owned stop record inconsistent with OS identity'
  }
  $pidWorker=[uint32]$stopped.worker_pid
  if($pidWorker -eq 0 -or $pidWorker -eq $pidService){
    throw 'Service/worker process identity invalid'
  }
  if(Get-Process -Id $pidWorker -ErrorAction SilentlyContinue){
    throw 'Numerical fixed child survived SCM Job termination'
  }
  $stopSha=(Get-FileHash -LiteralPath $stop -Algorithm SHA256).Hash.ToLowerInvariant()
  $signedStopSha=$null
  if($env:COG_R2_CI_SIGNED_STOP){
    if(!(Test-Path -LiteralPath $env:COG_R2_CI_SIGNED_STOP -PathType Leaf)){
      throw 'R2 independently provisioned CNG signed stop missing before restart'
    }
    $signedStopSha=(Get-FileHash -LiteralPath $env:COG_R2_CI_SIGNED_STOP -Algorithm SHA256).Hash.ToLowerInvariant()
  }
  $verifyOutput=& python scripts/cog_r5_r1_scm_ssm_fixture.py verify --root "$root"
  if($LASTEXITCODE -ne 0){throw 'Independently recalculated SSM math differs'}
  $verified=$verifyOutput | ConvertFrom-Json
  if($verified.real_ssm_factory_output_matches -ne $true -or
     $verified.stop_receipt_independently_signed -ne $false){
    throw 'Original SSM numerical verification or authority flags wrong'
  }
  # Same exact original intent must not run twice after restart, even though
  # it had a locally observed stop. SCM may START_PENDING briefly, but cannot
  # again reach RUNNING or alter the write-once original records.
  & sc.exe start $svc | Out-Host
  $deadline=[DateTime]::UtcNow.AddSeconds(7)
  $restartedRunning=$false
  $lastStatus=$null
  while([DateTime]::UtcNow -lt $deadline){
    $lastStatus=Get-CimInstance Win32_Service -Filter "Name='$svc'"
    if($lastStatus -and $lastStatus.State -eq 'Running'){$restartedRunning=$true;break}
    if($lastStatus -and $lastStatus.State -eq 'Stopped'){break}
    Start-Sleep -Milliseconds 150
  }
  if($restartedRunning -or !$lastStatus -or $lastStatus.State -ne 'Stopped'){
    throw 'SCM original-operation replay was not denied'
  }
  if((Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash.ToLowerInvariant() -cne $outputSha -or
     (Get-FileHash -LiteralPath $stop -Algorithm SHA256).Hash.ToLowerInvariant() -cne $stopSha){
    throw 'Original durable output/terminal record changed after restart'
  }
  if($signedStopSha -and
     (Get-FileHash -LiteralPath $env:COG_R2_CI_SIGNED_STOP -Algorithm SHA256).Hash.ToLowerInvariant() -cne $signedStopSha){
    throw 'Original OS-machine-signed stop receipt altered or replayed after service restart'
  }
  $report=[ordered]@{
    schema='cognitum.ssm.r1.actual_scm_fixed_ssm_ci.v1'
    status='PASS_REAL_FIXED_SSM_UNDER_SCM_FIXTURE_ONLY'
    original_source_test_only=$true
    original_mac_verified_by_service_before_worker=$true
    independent_child_process_observed=$childObserved
    independent_child_job_membership_observed=$childJobObserved
    independently_observed_restricted_token=$childRestrictedObserved
    service_local_system_session_zero=$true
    service_pid=$pidService
    numerical_worker_pid=$pidWorker
    real_SSM_output_matches_independent_factory=$true
    original_one_use_restart_replay_denied=$true
    local_service_owned_stop_record_verified=$true
    kernel_job_empty_after_stop=$true
    signed_installed_production_service=$false
    restricted_worker_token_verified=$false
    independent_production_stop_signer_verified=$false
    installed_core_health_verified=$false
    core_pure_compute_grant_verified=$false
    external_output_delivery_authorized=$false
    test_fixture_symmetric_key_recoverable_from_binary=$true
  }
  ($report|ConvertTo-Json -Depth 5) | Set-Content -LiteralPath $evidence -Encoding utf8
  Write-Host 'PASS_REAL_FIXED_SSM_UNDER_SCM_FIXTURE_ONLY'
}finally{
  if($created){
    try{& sc.exe stop $svc | Out-Null}catch{}
    try{& sc.exe delete $svc | Out-Null}catch{}
  }
  $deadline=[DateTime]::UtcNow.AddSeconds(10)
  do{
    $gone=!(Get-CimInstance Win32_Service -Filter "Name='$svc'")
    if($gone){$deletionConfirmed=$true;break}
    Start-Sleep -Milliseconds 150
  }while([DateTime]::UtcNow -lt $deadline)
  # Genuine final absence is checked, never declared from sc.exe status alone.
  if(!$deletionConfirmed){throw 'SCM temporary fixture deletion not independently confirmed'}
}
