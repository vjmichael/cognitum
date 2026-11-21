# R3-R1 unsigned hosted Windows SCM lifecycle qualification.
# Never run as a production enrollment or physical acceptance.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$CompiledBootstrap)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function Refuse([string]$message){throw ("COG_R3R1_CI_SCM_REFUSED: "+$message)}
if($env:OS -cne 'Windows_NT' -or $env:GITHUB_ACTIONS -cne 'true' -or
   $env:RUNNER_OS -cne 'Windows'){Refuse 'Genuine hosted Windows GitHub runner required'}
$admin=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if(-not $admin.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){
 Refuse 'Hosted Windows SCM test requires elevated runner'
}
if(-not [IO.Path]::IsPathRooted($CompiledBootstrap)){
 Refuse 'Original separately compiled absolute bootstrap path missing'
}
$exe=[IO.Path]::GetFullPath($CompiledBootstrap)
if(-not $exe.EndsWith('\cognitum-scm-production.exe',[StringComparison]::OrdinalIgnoreCase) -or
   -not (Test-Path -LiteralPath $exe -PathType Leaf)){
 Refuse 'Only separate genuine no-worker SCM bootstrap may execute'
}
$exeSha=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()
$sign=Get-AuthenticodeSignature -LiteralPath $exe
if($sign.Status -ne [Management.Automation.SignatureStatus]::NotSigned){
 Refuse 'CI-only lifecycle cannot adopt a signed or independently approved executable'
}
$service='CognitumSsmSupervisorV1'
if(Get-CimInstance Win32_Service -Filter "Name='$service'"){
 Refuse 'Preexisting service cannot be taken over for CI'
}
function Wait-State([string]$expected,[int]$maxTries=80){
 for($i=0;$i -lt $maxTries;$i++){
  $svc=Get-CimInstance Win32_Service -Filter "Name='$service'"
  if($svc -and $svc.State -ceq $expected){return $svc}
  Start-Sleep -Milliseconds 125
 }
 Refuse ('Bounded real SCM state '+$expected+' not observed')
}
function Witness-Running{
 $svc=Wait-State 'Running'
 if([uint32]$svc.ProcessId -eq 0 -or $svc.StartName -notin @('LocalSystem','NT AUTHORITY\LocalSystem') -or
    $svc.ServiceType -notlike '*Own Process*'){
  Refuse 'Real SCM process is not a dedicated LocalSystem service'
 }
 $process=Get-CimInstance Win32_Process -Filter ("ProcessId="+[uint32]$svc.ProcessId)
 if(-not $process -or
    -not $process.ExecutablePath.Equals($exe,[StringComparison]::OrdinalIgnoreCase) -or
    [uint32]$process.SessionId -ne 0 -or $null -eq $process.CreationDate){
  Refuse 'Original Windows process image/birth/session mismatch'
 }
 $owner=Invoke-CimMethod -InputObject $process -MethodName GetOwnerSid
 if($owner.ReturnValue -ne 0 -or $owner.Sid -cne 'S-1-5-18'){
  Refuse 'Original kernel LocalSystem process ownership absent'
 }
 if((Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant() -cne $exeSha){
  Refuse 'Original native bootstrap changed during SCM execution'
 }
 [pscustomobject]@{
  pid=[uint32]$svc.ProcessId
  birth=[string]$process.CreationDate
 }
}
$owned=$false
try{
 # This exercise uses an unsigned, ephemeral hosted Windows build.
 # It does NOT call the production signed-only enrollment script.
 & sc.exe create $service binPath= ('"'+$exe+'"') type= own start= demand obj= LocalSystem | Out-Null
 if($LASTEXITCODE -ne 0){Refuse 'Temporary original SCM registration failed'}
 $owned=$true
 & sc.exe sidtype $service restricted |Out-Null
 if($LASTEXITCODE -ne 0){Refuse 'Temporary restricted service SID rejected'}
 $reg=Get-ItemProperty -LiteralPath ("HKLM:\SYSTEM\CurrentControlSet\Services\"+$service)
 if($reg.Type -ne 16 -or $reg.Start -ne 3 -or $reg.ServiceSidType -ne 3){
  Refuse 'Original temporary SCM own-process/restricted identity invalid'
 }
 & sc.exe start $service |Out-Null
 if($LASTEXITCODE -ne 0){Refuse 'Original SCM bootstrap refused first startup'}
 $first=Witness-Running
 & sc.exe stop $service |Out-Null
 if($LASTEXITCODE -ne 0){Refuse 'Original SCM stop control was refused'}
 $stopped=Wait-State 'Stopped'
 if([uint32]$stopped.ProcessId -ne 0){Refuse 'SCM worker process not vacated after first stop'}
 for($i=0;$i -lt 80;$i++){
  $old=Get-CimInstance Win32_Process -Filter ("ProcessId="+[uint32]$first.pid)
  if(-not $old -or [string]$old.CreationDate -cne $first.birth){break}
  Start-Sleep -Milliseconds 125
 }
 if($old -and [string]$old.CreationDate -ceq $first.birth){
  Refuse 'Original first SCM process generation survived stop'
 }
 & sc.exe start $service |Out-Null
 if($LASTEXITCODE -ne 0){Refuse 'Original SCM bootstrap refused restart'}
 $second=Witness-Running
 if($second.pid -eq $first.pid -and $second.birth -ceq $first.birth){
  Refuse 'Restart used original live service process generation'
 }
 & sc.exe stop $service |Out-Null
 if($LASTEXITCODE -ne 0){Refuse 'Restarted SCM stop control refused'}
 $again=Wait-State 'Stopped'
 if([uint32]$again.ProcessId -ne 0){Refuse 'Restarted SCM process did not stop'}
 Write-Host 'PASS_CI_ONLY_ORIGINAL_SCM_START_STOP_RESTART_RESTRICTED_SID_NO_WORKER_BOOTSTRAP'
 Write-Host ('ORIGINAL_UNSIGNED_BOOTSTRAP_SHA256='+$exeSha)
}finally{
 if($owned){
  try{
   $existing=Get-CimInstance Win32_Service -Filter "Name='$service'"
   if($existing -and $existing.State -ne 'Stopped'){
    & sc.exe stop $service |Out-Null
    for($i=0;$i -lt 60;$i++){
     $existing=Get-CimInstance Win32_Service -Filter "Name='$service'"
     if(-not $existing -or $existing.State -eq 'Stopped'){break}
     Start-Sleep -Milliseconds 150
    }
   }
   & sc.exe delete $service |Out-Null
   if($LASTEXITCODE -ne 0){throw 'CI-owned original temporary SCM service could not be deleted'}
  }catch{
   throw 'COG_R3R1_CI_SCM_REFUSED: temporary SCM service cleanup failed'
  }
 }
}
