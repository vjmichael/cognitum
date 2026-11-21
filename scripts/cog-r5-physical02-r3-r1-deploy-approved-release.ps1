# Cognitum R3-R1 physical Windows signed-release deployment coordinator.
# REQUIRES an approved independent detached release signature BEFORE installer
# execution. Does not self-sign, provision CNG/worker or grant Core operations.
[CmdletBinding(SupportsShouldProcess=$true,ConfirmImpact='High')]
param(
 [Parameter(Mandatory=$true)][string]$ReleaseRoot,
 [Parameter(Mandatory=$true)][string]$ApprovalJson,
 [Parameter(Mandatory=$true)][string]$DetachedSignatureP7s,
 [Parameter(Mandatory=$true)][string]$ApprovedReleaseAuthorityCertificateSha256,
 [Parameter(Mandatory=$true)][string]$ApprovedPublisherCertificateSha256,
 [Parameter(Mandatory=$true)][string]$ExpectedSourceSha
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function Refuse([string]$why){throw ('COG_R3R1_PHYSICAL_DEPLOY_REFUSED: '+$why)}
if($env:OS -cne 'Windows_NT' -or $env:GITHUB_ACTIONS -eq 'true'){
 Refuse 'Original physical Windows deployment cannot run in hosted CI'
}
if(-not [Environment]::Is64BitProcess -or -not [Environment]::Is64BitOperatingSystem){
 Refuse 'Physical production package requires native 64-bit Windows process'
}
$principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){
 Refuse 'Explicitly elevated authorized Windows installer required'
}
if(-not [IO.Path]::IsPathRooted($ReleaseRoot)){Refuse 'Approved protected release directory must be absolute'}
$root=[IO.Path]::GetFullPath($ReleaseRoot).TrimEnd('\')
$admit=Join-Path $PSScriptRoot 'cog-r5-physical02-r3-r1-admit-signed-release.ps1'
$enroll=Join-Path $PSScriptRoot 'cog-r5-physical02-r3-r1-enroll-production.ps1'
$observe=Join-Path $PSScriptRoot 'cog-r5-physical02-r3-r1-physical-scm-observe.ps1'
foreach($p in @($admit,$enroll,$observe)){
 if(-not(Test-Path -LiteralPath $p -PathType Leaf)){Refuse 'Reviewed original physical release gate absent'}
}
$approvalArgs=@{
 ReleaseRoot=$root
 ApprovalJson=$ApprovalJson
 DetachedSignatureP7s=$DetachedSignatureP7s
 ApprovedReleaseAuthorityCertificateSha256=$ApprovedReleaseAuthorityCertificateSha256
 ApprovedPublisherCertificateSha256=$ApprovedPublisherCertificateSha256
 ExpectedSourceSha=$ExpectedSourceSha
}
$approvedRaw=& $admit @approvalArgs
if(-not $approvedRaw){Refuse 'Original signed release and independent approval missing'}
$a=($approvedRaw|Out-String)|ConvertFrom-Json
if($a.status -cne 'PASS_SIGNED_RELEASE_AND_DETACHED_APPROVAL_OBSERVATION_ONLY' -or
   $a.exact_source_sha -cne $ExpectedSourceSha -or
   $a.output_release_or_ACK_authorized -ne $false){
 Refuse 'Original independently pinned release not admitted'
}
$installedRoot=Join-Path $env:ProgramW6432 'Cognitum\SSM'
$service='CognitumSsmSupervisorV1'
if(Test-Path -LiteralPath $installedRoot){Refuse 'Existing or interrupted installation may not be adopted'}
if($null -ne (Get-CimInstance Win32_Service -Filter "Name='$service'")){
 Refuse 'Existing production SCM service may not be replaced'
}
$installer=Join-Path $root 'Cognitum-SSM-R3R1-Bootstrap.exe'
$approvedInstallerHash=[string]$a.signed_installer_sha256
if(-not $PSCmdlet.ShouldProcess($installedRoot,'Install independently pinned signed package, enroll protected zero-worker SCM service, and verify physical stop/restart')){
 return
}
# Revalidate the signed source and full package hashes immediately before any
# installation mutation. No CI/private signing key can be created by this path.
$recheckedRaw=& $admit @approvalArgs
if(-not $recheckedRaw){Refuse 'Signed release approval disappeared before execution'}
$rechecked=($recheckedRaw|Out-String)|ConvertFrom-Json
if($rechecked.status -cne $a.status -or
   $rechecked.signed_installer_sha256 -cne $approvedInstallerHash -or
   $rechecked.signed_service_sha256 -cne $a.signed_service_sha256 -or
   $rechecked.runtime_manifest_sha256 -cne $a.runtime_manifest_sha256 -or
   $rechecked.runtime_provenance_sha256 -cne $a.runtime_provenance_sha256){
 Refuse 'Release candidate changed after operator admission'
}
$installedStarted=$false
try{
 $installation=Start-Process -FilePath $installer -ArgumentList @('/S') -Wait -PassThru -ErrorAction Stop
 if($installation.ExitCode -ne 0){Refuse ('Original signed installer execution refused exit '+$installation.ExitCode)}
 $installedStarted=$true
 if(-not(Test-Path -LiteralPath $installedRoot -PathType Container)){
  Refuse 'Original signed installer did not create protected Program Files root'
 }
 $enrollArgs=@{
  SignedInstallerPackage=$installer
  ApprovedInstallerSha256=$approvedInstallerHash
  ApprovedSignerCertificateSha256=$ApprovedPublisherCertificateSha256
  ApprovedInstallRoot=$installedRoot
  InstalledExecutable=(Join-Path $installedRoot 'cognitum-scm-production.exe')
  ApprovedExecutableSha256=$a.signed_service_sha256
  RuntimeRoot=(Join-Path $installedRoot 'runtime')
  ApprovedRuntimeManifestSha256=$a.runtime_manifest_sha256
  ApprovedRuntimeProvenanceSha256=$a.runtime_provenance_sha256
 }
 $registeredRaw=& $enroll @enrollArgs -Confirm:$false
 if(-not $registeredRaw){Refuse 'Installed signed SCM enrollment witness missing'}
 $registered=($registeredRaw|Out-String)|ConvertFrom-Json
 if($registered.status -cne 'PASS_SIGNED_INSTALLED_SERVICE_BOOTSTRAP_ONLY' -or
    $registered.output_release_or_ACK_authorized -ne $false){
  Refuse 'Actual installed signed SCM bootstrap enrollment not verified'
 }
 $observeArgs=@{
  SignedInstallerPackage=$installer
  ApprovedInstallerSha256=$approvedInstallerHash
  InstalledExecutable=(Join-Path $installedRoot 'cognitum-scm-production.exe')
  ApprovedInstallRoot=$installedRoot
  ApprovedImageSha256=$a.signed_service_sha256
  ApprovedSignerCertificateSha256=$ApprovedPublisherCertificateSha256
  RuntimeRoot=(Join-Path $installedRoot 'runtime')
  ApprovedRuntimeManifestSha256=$a.runtime_manifest_sha256
  ApprovedRuntimeProvenanceSha256=$a.runtime_provenance_sha256
 }
 $observedRaw=& $observe @observeArgs -Confirm:$false
 if(-not $observedRaw){Refuse 'Physical signed SCM lifecycle witness absent'}
 $observed=($observedRaw|Out-String)|ConvertFrom-Json
 if($observed.status -cne 'PASS_SIGNED_INSTALLED_SCM_STOP_RESTART_OBSERVATION_ONLY' -or
    $observed.output_release_or_ACK_authorized -ne $false){
  Refuse 'Physical signed SCM lifecycle not admitted'
 }
 [pscustomobject]@{
  schema='cognitum.ssm.r3r1.physical_signed_installation_chain.v1'
  status='PASS_SIGNED_RELEASE_INSTALLED_SCM_AND_RESTART_OBSERVATION_ONLY'
  exact_source_sha=$ExpectedSourceSha
  signed_installer_sha256=$approvedInstallerHash
  signed_service_sha256=$a.signed_service_sha256
  frozen_runtime_manifest_sha256=$a.runtime_manifest_sha256
  publisher_certificate_sha256=$ApprovedPublisherCertificateSha256
  detached_release_authority_certificate_sha256=$ApprovedReleaseAuthorityCertificateSha256
  original_service_pid_before=$observed.service_pid_before
  original_service_pid_after=$observed.service_pid_after
  independent_physical_operator_attestation_verified=$false
  production_CNG_key_verified=$false
  nonadmin_AppContainer_SSM_operation_verified=$false
  original_Lu_Core_grant_verified=$false
  physical_full_installed_acceptance=$false
  output_release_or_ACK_authorized=$false
 }|ConvertTo-Json -Compress
}catch{
 # Never silently remove a partially installed protected tree, delete an
 # existing service, or treat aborted operations as successful admissions.
 # The original state remains for separately authorized forensic recovery.
 $reason=$_.Exception.Message
 if($installedStarted -or (Test-Path -LiteralPath $installedRoot)){
  Refuse ('Original signed installation INCOMPLETE; independent recovery required: '+$reason)
 }
 Refuse ('Signed package installation refused before protected deployment: '+$reason)
}
