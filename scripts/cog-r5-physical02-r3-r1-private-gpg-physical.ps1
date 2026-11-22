# Cognitum R3-R1 PRIVATE GPG Windows installation + genuine SCM observation.
# This is NOT Windows Authenticode and never grants numerical worker access.
[CmdletBinding(SupportsShouldProcess=$true,ConfirmImpact='High')]
param(
 [Parameter(Mandatory=$true)][string]$ReleaseRoot,
 [Parameter(Mandatory=$true)][string]$TrustedPublicKeyFile,
 [Parameter(Mandatory=$true)][string]$ExpectedPrimaryFingerprint,
 [Parameter(Mandatory=$true)][string]$ExpectedSourceSha,
 [Parameter(Mandatory=$true)][string]$GpgExecutable
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function Refuse([string]$why){throw ('COG_R3R1_PRIVATE_PHYSICAL_REFUSED: '+$why)}
if($env:OS -cne 'Windows_NT' -or $env:GITHUB_ACTIONS -eq 'true' -or $env:CI -eq 'true'){
 Refuse 'Private physically installed acceptance requires original non-CI Windows'
}
if(-not [Environment]::Is64BitOperatingSystem -or -not [Environment]::Is64BitProcess){
 Refuse 'Native 64-bit Windows installed SCM is required'
}
$principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){
 Refuse 'Explicit elevated operator required for original SCM enrollment'
}
$gpgGate=Join-Path $PSScriptRoot 'cog-r5-physical02-r3-r1-private-gpg-verify.ps1'
$runtimeGate=Join-Path $PSScriptRoot 'cog-r5-physical02-r3-r1-runtime-audit.ps1'
foreach($gate in @($gpgGate,$runtimeGate)){
 if(-not(Test-Path -LiteralPath $gate -PathType Leaf)){Refuse 'Reviewed original GPG or runtime gate missing'}
}
$verifyArgs=@{
 ReleaseRoot=$ReleaseRoot
 TrustedPublicKeyFile=$TrustedPublicKeyFile
 ExpectedPrimaryFingerprint=$ExpectedPrimaryFingerprint
 ExpectedSourceSha=$ExpectedSourceSha
 GpgExecutable=$GpgExecutable
}
function Verify-Gpg{
 $raw=& $gpgGate @verifyArgs
 if(-not $raw){Refuse 'Original GPG release verification missing'}
 $p=($raw|Out-String)|ConvertFrom-Json
 if($p.schema -cne 'cognitum.ssm.r3r1.private_gpg_release_verified.v1' -or
    $p.status -cne 'PASS_PRIVATE_GPG_PACKAGE_DIGESTS_OBSERVATION_ONLY' -or
    $p.exact_source_sha -cne $ExpectedSourceSha -or
    $p.output_release_or_ACK_authorized -ne $false){
  Refuse 'Original privately signed release or explicit output denial not admitted'
 }
 $p
}
$approved=Verify-Gpg
$installRoot=Join-Path $env:ProgramW6432 'Cognitum\SSM'
$installedExe=Join-Path $installRoot 'cognitum-scm-production.exe'
$installedRuntime=Join-Path $installRoot 'runtime'
$installer=Join-Path ([IO.Path]::GetFullPath($ReleaseRoot)) 'Cognitum-SSM-R3R1-Bootstrap.exe'
$service='CognitumSsmSupervisorV1'
if(Test-Path -LiteralPath $installRoot){Refuse 'Existing private or interrupted installation requires independent recovery'}
if(Get-CimInstance Win32_Service -Filter "Name='$service'"){
 Refuse 'Existing SCM service must not be adopted or overwritten'
}
if(-not $PSCmdlet.ShouldProcess($installRoot,'Install GPG-pinned private package and qualify original protected SCM stop/restart')){
 return
}
$confirmed=Verify-Gpg
foreach($key in @('installer_sha256','service_sha256','runtime_manifest_sha256','runtime_provenance_sha256')){
 if($confirmed.$key -cne $approved.$key){Refuse 'Signed private release changed before execution'}
}
$installationStarted=$false
try{
 $installation=Start-Process -FilePath $installer -ArgumentList '/S' -PassThru -Wait -ErrorAction Stop
 $installationStarted=$true
 if($installation.ExitCode -ne 0){Refuse ('Original NSIS private install refused exit '+$installation.ExitCode)}
 if(-not (Test-Path -LiteralPath $installedExe -PathType Leaf)){
  Refuse 'Protected original SCM image missing from installed Program Files'
 }
 $imageHash=(Get-FileHash -LiteralPath $installedExe -Algorithm SHA256).Hash.ToLowerInvariant()
 if($imageHash -cne $approved.service_sha256){
  Refuse 'Installed production SCM binary differs from original GPG-signed release'
 }
 $trusted=@('S-1-5-18','S-1-5-32-544')
 $writeMask=[int64]0x500D0156L
 $cursor=$installedExe
 while($true){
  $item=Get-Item -LiteralPath $cursor -Force
  if(($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){Refuse 'Installed service image reparse ancestry'}
  $acl=Get-Acl -LiteralPath $cursor
  $owner=$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value
  if($trusted -cnotcontains $owner){Refuse 'Installed protected SCM image owner untrusted'}
  foreach($ace in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])){
   if($ace.AccessControlType -eq [Security.AccessControl.AccessControlType]::Allow -and
      (([int64]$ace.FileSystemRights -band $writeMask) -ne 0) -and
      $trusted -cnotcontains $ace.IdentityReference.Value){
    Refuse 'Installed original SCM code writable by untrusted account'
   }
  }
  if($cursor.Equals($installRoot,[StringComparison]::OrdinalIgnoreCase)){break}
  $parent=[IO.Directory]::GetParent($cursor)
  if($null -eq $parent){Refuse 'Installed service escaped Program Files custody root'}
  $cursor=$parent.FullName
 }
 $runtimeRaw=& $runtimeGate -ApprovedInstallRoot $installRoot -RuntimeRoot $installedRuntime -ApprovedManifestSha256 $approved.runtime_manifest_sha256 -ApprovedProvenanceSha256 $approved.runtime_provenance_sha256
 $r=($runtimeRaw|Out-String)|ConvertFrom-Json
 if($r.status -cne 'PASS_INSTALLED_RUNTIME_DIGEST_ACL_OBSERVATION_ONLY' -or
    $r.output_release_authorized -ne $false){
  Refuse 'Installed frozen Python/NumPy/SciPy runtime cannot pass original full-file gate'
 }
 if(Get-CimInstance Win32_Service -Filter "Name='$service'"){
  Refuse 'NSIS package unexpectedly created or adopted an SCM service'
 }
 & sc.exe create $service binPath= ('"'+$installedExe+'"') type= own start= demand obj= LocalSystem |Out-Null
 if($LASTEXITCODE -ne 0){Refuse 'Original local SCM registration failed'}
 & sc.exe sidtype $service restricted |Out-Null
 if($LASTEXITCODE -ne 0){Refuse 'Restricted service SID registration failed'}
 $registration=Get-ItemProperty -LiteralPath ("HKLM:\SYSTEM\CurrentControlSet\Services\"+$service)
 if($registration.Type -ne 16 -or $registration.Start -ne 3 -or $registration.ServiceSidType -ne 3){
  Refuse 'Original service own-process/restricted-SID/demand-start identity invalid'
 }
 function Wait-ServiceState([string]$expected){
  for($i=0;$i -lt 100;$i++){
   $current=Get-CimInstance Win32_Service -Filter "Name='$service'"
   if($current -and $current.State -ceq $expected){return $current}
   Start-Sleep -Milliseconds 150
  }
  Refuse ('Bounded original SCM '+$expected+' state absent')
 }
 function Witness-Running {
  $svc=Wait-ServiceState 'Running'
  if([uint32]$svc.ProcessId -eq 0 -or $svc.StartName -notin @('LocalSystem','NT AUTHORITY\LocalSystem') -or
     $svc.ServiceType -notlike '*Own Process*'){
   Refuse 'Original running SCM service process identity invalid'
  }
  $proc=Get-CimInstance Win32_Process -Filter ('ProcessId='+[uint32]$svc.ProcessId)
  if(-not $proc -or -not $proc.ExecutablePath.Equals($installedExe,[StringComparison]::OrdinalIgnoreCase) -or
     [uint32]$proc.SessionId -ne 0 -or $null -eq $proc.CreationDate){
   Refuse 'Original installed SCM PID/birth/Session 0 image identity invalid'
  }
  $owner=Invoke-CimMethod -InputObject $proc -MethodName GetOwnerSid
  if($owner.ReturnValue -ne 0 -or $owner.Sid -cne 'S-1-5-18'){
   Refuse 'Original installed SCM image did not execute as LocalSystem'
  }
  if((Get-FileHash -LiteralPath $installedExe -Algorithm SHA256).Hash.ToLowerInvariant() -cne $imageHash){
   Refuse 'Original SCM binary changed during physical operation'
  }
  [pscustomobject]@{pid=[uint32]$svc.ProcessId;birth=[string]$proc.CreationDate}
 }
 & sc.exe start $service |Out-Null
 if($LASTEXITCODE -ne 0){Refuse 'Original SCM start failed'}
 $first=Witness-Running
 & sc.exe stop $service |Out-Null
 if($LASTEXITCODE -ne 0){Refuse 'Original SCM stop failed'}
 $stopped=Wait-ServiceState 'Stopped'
 if([uint32]$stopped.ProcessId -ne 0){Refuse 'Original SCM PID persisted in stopped state'}
 for($i=0;$i -lt 100;$i++){
  $old=Get-CimInstance Win32_Process -Filter ('ProcessId='+$first.pid)
  if(-not $old -or [string]$old.CreationDate -cne $first.birth){break}
  Start-Sleep -Milliseconds 150
 }
 if($old -and [string]$old.CreationDate -ceq $first.birth){
  Refuse 'Original SCM PID generation survived stop'
 }
 & sc.exe start $service |Out-Null
 if($LASTEXITCODE -ne 0){Refuse 'Original SCM restart failed'}
 $second=Witness-Running
 if($first.pid -eq $second.pid -and $first.birth -ceq $second.birth){
  Refuse 'Original SCM process generation was reused after stop'
 }
 $again=& $runtimeGate -ApprovedInstallRoot $installRoot -RuntimeRoot $installedRuntime -ApprovedManifestSha256 $approved.runtime_manifest_sha256 -ApprovedProvenanceSha256 $approved.runtime_provenance_sha256
 if((($again|Out-String)|ConvertFrom-Json).status -cne 'PASS_INSTALLED_RUNTIME_DIGEST_ACL_OBSERVATION_ONLY'){
  Refuse 'Frozen installed runtime changed over SCM restart'
 }
 $verifiedAfter=Verify-Gpg
 if($verifiedAfter.installer_sha256 -cne $approved.installer_sha256 -or
    (Get-FileHash -LiteralPath $installedExe -Algorithm SHA256).Hash.ToLowerInvariant() -cne $approved.service_sha256){
  Refuse 'Signed origin or physical original SCM image changed during installed acceptance'
 }
 [pscustomobject]@{
  schema='cognitum.ssm.r3r1.private_gpg_physical_scm_observation.v1'
  status='PASS_GPG_PRIVATE_INSTALLED_SCM_STOP_RESTART_OBSERVATION_ONLY'
  exact_source_sha=$ExpectedSourceSha
  gpg_primary_fingerprint=$approved.gpg_primary_fingerprint
  signed_release_installer_sha256=$approved.installer_sha256
  installed_scm_sha256=$approved.service_sha256
  runtime_manifest_sha256=$approved.runtime_manifest_sha256
  service_pid_before=$first.pid
  service_pid_after=$second.pid
  windows_authenticode_required=$false
  independently_attested_physical_machine=$false
  production_appcontainer_worker_verified=$false
  original_core_grant_verified=$false
  production_CNG_signed_receipts_verified=$false
  output_release_or_ACK_authorized=$false
 }|ConvertTo-Json -Compress
}catch{
 $cause=$_.Exception.Message
 if($installationStarted -or (Test-Path -LiteralPath $installRoot)){
  Refuse ('Original private installation INCOMPLETE; preserve installed state for operator investigation: '+$cause)
 }
 Refuse ('Original private package refused before install: '+$cause)
}
