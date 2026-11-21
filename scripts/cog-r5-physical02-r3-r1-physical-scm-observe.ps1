# R3-R1 physical signed Windows SCM lifecycle observer (no SSM admission).
# Requires a separately signed production installer and independently approved
# hashes. It never self-signs, enrolls Core or releases numerical results.
[CmdletBinding(SupportsShouldProcess=$true,ConfirmImpact='High')]
param(
 [Parameter(Mandatory=$true)][string]$SignedInstallerPackage,
 [Parameter(Mandatory=$true)][string]$ApprovedInstallerSha256,
 [Parameter(Mandatory=$true)][string]$InstalledExecutable,
 [Parameter(Mandatory=$true)][string]$ApprovedInstallRoot,
 [Parameter(Mandatory=$true)][string]$ApprovedImageSha256,
 [Parameter(Mandatory=$true)][string]$ApprovedSignerCertificateSha256,
 [Parameter(Mandatory=$true)][string]$RuntimeRoot,
 [Parameter(Mandatory=$true)][string]$ApprovedRuntimeManifestSha256,
 [Parameter(Mandatory=$true)][string]$ApprovedRuntimeProvenanceSha256
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function Refuse([string]$why){throw ("COG_R3R1_PHYSICAL_SCM_REFUSED: "+$why)}
if($env:OS -cne 'Windows_NT'){Refuse 'Physical original Windows required'}
$admin=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if(-not $admin.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){
 Refuse 'Elevated physical installed observer required'
}
$gate=Join-Path $PSScriptRoot 'cog-r5-physical02-r3-r1-installed-preflight.ps1'
if(-not(Test-Path -LiteralPath $gate -PathType Leaf)){Refuse 'Original installed release preflight missing'}
$parameters=@{
 SignedInstallerPackage=$SignedInstallerPackage
 ApprovedInstallerSha256=$ApprovedInstallerSha256
 InstalledExecutable=$InstalledExecutable
 ApprovedInstallRoot=$ApprovedInstallRoot
 ApprovedImageSha256=$ApprovedImageSha256
 ApprovedSignerCertificateSha256=$ApprovedSignerCertificateSha256
 RuntimeRoot=$RuntimeRoot
 ApprovedRuntimeManifestSha256=$ApprovedRuntimeManifestSha256
 ApprovedRuntimeProvenanceSha256=$ApprovedRuntimeProvenanceSha256
}
function Assert-Installed{
 $raw=& $gate @parameters
 if(-not $raw){Refuse 'No independently signed installed host/runtime observation'}
 $p=($raw|Out-String)|ConvertFrom-Json
 if($p.schema -cne 'cognitum.ssm.r3r1.physical_installed_readonly_preflight.v1' -or
    $p.status -cne 'PASS_SIGNED_INSTALLER_SCM_AND_RUNTIME_CUSTODY_OBSERVATION_ONLY' -or
    $p.physical_full_installed_acceptance -ne $false -or
    $p.output_release_or_ACK_authorized -ne $false){
  Refuse 'Original signed installed host/runtime refuses independent integrity'
 }
 $p
}
$initial=Assert-Installed
$service='CognitumSsmSupervisorV1'
function Wait-State([string]$want){
 for($i=0;$i -lt 80;$i++){
  $found=Get-CimInstance Win32_Service -Filter "Name='$service'"
  if($found -and $found.State -ceq $want){return $found}
  Start-Sleep -Milliseconds 125
 }
 Refuse ('Original SCM bounded '+$want+' state unavailable')
}
function PidBirth([uint32]$processId){
 $proc=Get-CimInstance Win32_Process -Filter ("ProcessId="+$processId)
 if(-not $proc){Refuse 'Original process generation cannot be observed'}
 [string]$proc.CreationDate
}
$before=Wait-State 'Running'
$pidBefore=[uint32]$before.ProcessId
if($pidBefore -eq 0){Refuse 'Original SCM supervisor absent'}
$birthBefore=PidBirth $pidBefore
if(-not $PSCmdlet.ShouldProcess($service,'Stop and restart approved signed production no-worker SCM service for independent lifecycle witness')){
 return
}
& sc.exe stop $service |Out-Null
if($LASTEXITCODE -ne 0){Refuse 'Original protected SCM stop rejected'}
$stopped=Wait-State 'Stopped'
if([uint32]$stopped.ProcessId -ne 0){Refuse 'Original signed SCM process remains registered after stop'}
$reaped=$false
for($i=0;$i -lt 80;$i++){
 $proc=Get-CimInstance Win32_Process -Filter ("ProcessId="+$pidBefore)
 if(-not $proc -or [string]$proc.CreationDate -cne $birthBefore){
  $reaped=$true;break
 }
 Start-Sleep -Milliseconds 125
}
if(-not $reaped){Refuse 'Original protected SCM PID generation survived stop'}
& sc.exe start $service |Out-Null
if($LASTEXITCODE -ne 0){Refuse 'Original protected signed SCM restart failed'}
$after=Wait-State 'Running'
$pidAfter=[uint32]$after.ProcessId
if($pidAfter -eq 0){Refuse 'Restarted SCM lacks original PID'}
$birthAfter=PidBirth $pidAfter
if($pidAfter -eq $pidBefore -and $birthAfter -ceq $birthBefore){
 Refuse 'Original process generation reused after restart'
}
$rechecked=Assert-Installed
if($rechecked.signed_SCM_image_sha256 -cne $initial.signed_SCM_image_sha256 -or
   $rechecked.frozen_runtime_manifest_sha256 -cne $initial.frozen_runtime_manifest_sha256 -or
   $rechecked.signed_installer_package_sha256 -cne $initial.signed_installer_package_sha256){
 Refuse 'Signed installer/image/frozen runtime identity changed across restart'
}
[pscustomobject]@{
 schema='cognitum.ssm.r3r1.physical_scm_lifecycle_observation.v1'
 status='PASS_SIGNED_INSTALLED_SCM_STOP_RESTART_OBSERVATION_ONLY'
 approved_installer_sha256=$initial.signed_installer_package_sha256
 approved_image_sha256=$initial.signed_SCM_image_sha256
 frozen_runtime_manifest_sha256=$initial.frozen_runtime_manifest_sha256
 service_pid_before=$pidBefore
 service_pid_after=$pidAfter
 independently_approved_original_Core_grant=$false
 nonadmin_AppContainer_execution_verified=$false
 production_signed_CNG_termination_verified=$false
 full_physical_installed_acceptance=$false
 output_release_or_ACK_authorized=$false
}|ConvertTo-Json -Compress
