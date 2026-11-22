# CI-only source-lineage qualification. NEVER register/replace the
# owner-accepted CognitumSsmSupervisorV1 production no-worker service.
# Explicitly proves actual Windows SCM (SYSTEM/session0) -> original
# nonadmin AppContainer -> suspended Job -> fixed SSM result candidate.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$Executable,
 [Parameter(Mandatory=$true)][string]$WitnessRoot,
 [Parameter(Mandatory=$true)][string]$WorkerRoot,
 [Parameter(Mandatory=$true)][string]$EvidencePath
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($env:OS -ne 'Windows_NT' -or $env:GITHUB_ACTIONS -ne 'true'){
 throw 'Disposable Windows CI-only qualification; not accepted installed release'
}
$service='CognitumSsmProductionQualifierV1'
$exe=[IO.Path]::GetFullPath($Executable)
$hostRoot=[IO.Path]::GetFullPath($WitnessRoot)
$worker=[IO.Path]::GetFullPath($WorkerRoot)
$evidence=[IO.Path]::GetFullPath($EvidencePath)
$original=Join-Path $hostRoot 'r3-original-appcontainer-witness.json'
$qualification=Join-Path $hostRoot 'production-qualification.json'
$answer=Join-Path $worker 'output.frame'
if(!(Test-Path $exe -PathType Leaf) -or
   !(Test-Path $hostRoot -PathType Container) -or
   !(Test-Path $worker -PathType Container) -or
   (Get-CimInstance Win32_Service -Filter "Name='$service'") -or
   (Test-Path $original) -or (Test-Path $qualification) -or
   (Test-Path $answer) -or (Test-Path $evidence)){
 throw 'Fresh pinned production qualifier service or output not available'
}
$created=$false
$observedPid=0
try{
 & $exe
 if($LASTEXITCODE -eq 0){throw 'Direct non-SCM execution was incorrectly admitted'}
 & sc.exe create $service 'binPath=' ('"'+$exe+'"') 'start=' 'demand' 'obj=' 'LocalSystem' |Out-Null
 if($LASTEXITCODE -ne 0){throw 'Dedicated qualifier SCM CreateService failed'}
 $created=$true
 & sc.exe start $service |Out-Null
 if($LASTEXITCODE -ne 0){throw 'Dedicated qualifier SCM start failed'}
 $deadline=[DateTime]::UtcNow.AddSeconds(65)
 $running=$false
 while([DateTime]::UtcNow -lt $deadline){
  $svc=Get-CimInstance Win32_Service -Filter "Name='$service'"
  if($svc -and $svc.State -eq 'Running' -and [uint32]$svc.ProcessId -gt 0){
   $running=$true
   $observedPid=[uint32]$svc.ProcessId
  }
  if($running -and (Test-Path $qualification -PathType Leaf) -and
     (Test-Path $original -PathType Leaf) -and (Test-Path $answer -PathType Leaf)){break}
  if($svc -and $svc.State -eq 'Stopped'){
   throw 'SCM rejected protected numerical worker; no permission to fall back'
  }
  Start-Sleep -Milliseconds 150
 }
 if(!$running -or !(Test-Path $qualification -PathType Leaf) -or
    !(Test-Path $original -PathType Leaf) -or
    !(Test-Path $answer -PathType Leaf)){
  throw 'SCM stopped, child failed, or protected original math candidate missing'
 }
 $current=Get-CimInstance Win32_Service -Filter "Name='$service'"
 if($current.StartName -notin @('LocalSystem','NT AUTHORITY\LocalSystem') -or
    [uint32]$current.ProcessId -ne $observedPid){
  throw 'Production lineage service did not keep genuine LocalSystem SCM identity'
 }
 $serviceProcess=Get-CimInstance Win32_Process -Filter ("ProcessId="+$observedPid)
 if(!$serviceProcess -or [uint32]$serviceProcess.SessionId -ne 0){
  throw 'Production lineage SCM session-0 custody missing'
 }
 $who=Invoke-CimMethod -InputObject $serviceProcess -MethodName GetOwnerSid
 if($who.ReturnValue -ne 0 -or $who.Sid -cne 'S-1-5-18'){
  throw 'Production lineage SCM token is not actually LocalSystem'
 }
 $token=Get-Content -LiteralPath $original -Raw|ConvertFrom-Json
 $math=Get-Content -LiteralPath $qualification -Raw|ConvertFrom-Json
 $response=Get-Content -LiteralPath $answer -Raw|ConvertFrom-Json
 if($token.native_TokenIsAppContainer -ne $true -or
    $token.native_TokenUser_is_SYSTEM -ne $false -or
    $token.native_TokenElevation_is_zero -ne $true -or
    $token.checked_before_worker_resume -ne $true -or
    $token.appcontainer_sid -cnotmatch '^S-1-15-2-[0-9-]+$' -or
    $token.worker_pid -le 0 -or
    $math.worker_pid -ne $token.worker_pid -or
    $math.kernel_job_empty_after_wait -ne $true -or
    $math.output_release_authorized -ne $false -or
    $response.status -cne 'ok' -or
    !$response.reply){
  throw 'Native OS token/Job receipt or real mathematical output did not qualify'
 }
 $resultHash=(Get-FileHash -LiteralPath $answer -Algorithm SHA256).Hash.ToLowerInvariant()
 if($resultHash -cne $math.worker_result_sha256){throw 'Worker math output hash does not match original SCM Job evidence'}
 & sc.exe stop $service |Out-Null
 if($LASTEXITCODE -ne 0){throw 'SCM qualifier stop failed'}
 $deadline=[DateTime]::UtcNow.AddSeconds(20)
 do{
  $svc=Get-CimInstance Win32_Service -Filter "Name='$service'"
  if($svc -and $svc.State -eq 'Stopped'){break}
  Start-Sleep -Milliseconds 100
 }while([DateTime]::UtcNow -lt $deadline)
 if(!$svc -or $svc.State -ne 'Stopped'){
  throw 'Qualified SCM could not be stopped'
 }
 [ordered]@{
  schema='cognitum.ssm.r3r1.production_lineage_qualification.v1'
  status='PASS_CI_PRODUCTION_LINEAGE_NATIVE_APP_CONTAINER_SSM_JOB'
  exact_source_sha=(git rev-parse HEAD).Trim()
  scm_service=$service
  scm_pid=$observedPid
  original_non_SYSTEM_worker_pid=[uint32]$token.worker_pid
  original_AppContainer_SID=$token.appcontainer_sid
  actual_kernel_job_empty=$true
  output_sha256=$resultHash
  mathematical_candidate_created=$true
  actual_owner_installed_service_changed=$false
  installed_Core_authorized=$false
  production_CNG_signed_receipts=$false
  output_or_ACK_authorized=$false
 }|ConvertTo-Json -Depth 4 -Compress|Set-Content -LiteralPath $evidence -Encoding ascii
 Write-Host 'PASS_CI_PRODUCTION_LINEAGE_NATIVE_APP_CONTAINER_SSM_JOB'
}finally{
 if($created){
  $svc=Get-CimInstance Win32_Service -Filter "Name='$service'"
  if($svc -and $svc.State -ne 'Stopped'){& sc.exe stop $service |Out-Null}
  $deadline=[DateTime]::UtcNow.AddSeconds(20)
  do{
   $svc=Get-CimInstance Win32_Service -Filter "Name='$service'"
   if(!$svc -or $svc.State -eq 'Stopped'){break}
   Start-Sleep -Milliseconds 100
  }while([DateTime]::UtcNow -lt $deadline)
  if($svc -and $svc.State -eq 'Stopped'){
   & sc.exe delete $service |Out-Null
   if($LASTEXITCODE -ne 0){throw 'Cannot delete OWN disposable qualifier service'}
  }else{throw 'Refuse deleting active or foreign SCM service'}
 }
}
