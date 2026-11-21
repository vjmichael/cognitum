# R3-R1 read-only Windows installed host and frozen runtime preflight.
# Externally signed installed code must already exist; no CI fixture promotion.
[CmdletBinding()]
param(
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
$hostGate=Join-Path $PSScriptRoot 'cog-r5-physical02-r2-signed-host-preflight.ps1'
$runtimeGate=Join-Path $PSScriptRoot 'cog-r5-physical02-r3-r1-runtime-audit.ps1'
foreach($gate in @($hostGate,$runtimeGate)){
 if(-not (Test-Path -LiteralPath $gate -PathType Leaf)){
  throw 'COG_R3R1_INSTALLED_REFUSED: reviewed admission gate missing'
 }
}
$rawHost=& $hostGate -InstalledExecutable $InstalledExecutable -ApprovedInstallRoot $ApprovedInstallRoot -ApprovedImageSha256 $ApprovedImageSha256 -ApprovedSignerCertificateSha256 $ApprovedSignerCertificateSha256
if(-not $rawHost){throw 'COG_R3R1_INSTALLED_REFUSED: no signed SCM host witness'}
$hostClaim=($rawHost|Out-String)|ConvertFrom-Json
if($hostClaim.schema -cne 'cognitum.ssm.r2.production_installed_readonly_preflight.v1' -or
   $hostClaim.status -cne 'PASS_SIGNED_SCM_IDENTITY_OBSERVATION_ONLY' -or
   $hostClaim.external_output_release_authorized -ne $false){
 throw 'COG_R3R1_INSTALLED_REFUSED: production SCM identity not verified'
}
$rawRuntime=& $runtimeGate -ApprovedInstallRoot $ApprovedInstallRoot -RuntimeRoot $RuntimeRoot -ApprovedManifestSha256 $ApprovedRuntimeManifestSha256 -ApprovedProvenanceSha256 $ApprovedRuntimeProvenanceSha256
if(-not $rawRuntime){throw 'COG_R3R1_INSTALLED_REFUSED: no frozen runtime witness'}
$runtimeClaim=($rawRuntime|Out-String)|ConvertFrom-Json
if($runtimeClaim.schema -cne 'cognitum.ssm.r3r1.installed_runtime_readonly_audit.v1' -or
   $runtimeClaim.status -cne 'PASS_INSTALLED_RUNTIME_DIGEST_ACL_OBSERVATION_ONLY' -or
   $runtimeClaim.output_release_authorized -ne $false){
 throw 'COG_R3R1_INSTALLED_REFUSED: protected runtime not verified'
}
[pscustomobject]@{
 schema='cognitum.ssm.r3r1.physical_installed_readonly_preflight.v1'
 status='PASS_SIGNED_SCM_AND_RUNTIME_CUSTODY_OBSERVATION_ONLY'
 signed_SCM_image_sha256=$hostClaim.executable_sha256
 signed_publisher_sha256=$hostClaim.approved_signer_sha256
 frozen_runtime_manifest_sha256=$runtimeClaim.manifest_sha256
 frozen_runtime_provenance_sha256=$runtimeClaim.provenance_sha256
 frozen_runtime_original_file_count=$runtimeClaim.original_file_count
 OS_nonadmin_AppContainer_worker_verified=$false
 production_SCM_owned_CNG_receipts_verified=$false
 Lu_Core_operation_authorization_verified=$false
 physical_full_installed_acceptance=$false
 output_release_or_ACK_authorized=$false
}|ConvertTo-Json -Compress
