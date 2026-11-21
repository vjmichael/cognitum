# R2 real Windows SCM-owned SSM restricted token & external CI machine CNG signer.
# This is test-only evidence, never signed production installation admission.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$Executable,
 [Parameter(Mandatory=$true)][string]$FixtureRoot,
 [Parameter(Mandatory=$true)][string]$EvidencePath,
 [switch]$RequireRestrictedToken
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($env:OS -ne 'Windows_NT'){throw 'Native Windows R2 SCM required'}
$root=[IO.Path]::GetFullPath($FixtureRoot)
$evidence=[IO.Path]::GetFullPath($EvidencePath)
$public=Join-Path $root 'r2-public-p256.blob'
$enrollment=Join-Path $root 'r2-external-provision.json'
$signed=Join-Path $root 'r2-signed-stop.json'
if(!(Test-Path $public -PathType Leaf) -or
   !(Test-Path $enrollment -PathType Leaf) -or (Test-Path $signed)){
 throw 'External original CNG key proof missing or already consumed'
}
$approved=Get-Content -LiteralPath $enrollment -Raw | ConvertFrom-Json
if($approved.schema -cne 'cognitum.ssm.r2.CI_external_KSP_enrollment.v1' -or
   $approved.public_blob_sha256 -cne $env:COG_R2_CI_PUBLIC_SHA256 -or
   $approved.name -cne $env:COG_R2_CI_KEY_NAME){
 throw 'Foreign test-only signer key or missing independently provided pin'
}
if($RequireRestrictedToken){
# The genuine Windows restricted primary token has BUILTIN Users as
# a *restricting SID*. Grant READ/EXECUTE, NOT write, on Python and reviewed
# Cognitum source strictly inside this disposable CI runner.
# Production must use an installer-controlled dedicated SID/AppContainer and
# immutable verified file handles; never use Users for production image ACL.
$readOnlyRoots=@(
  [IO.Path]::GetDirectoryName($env:COG_R1_CI_PYTHON),
  (Join-Path $PWD 'cognitum')
)
foreach($item in $readOnlyRoots){
  if(!(Test-Path -LiteralPath $item -PathType Container) -or
     ((Get-Item -LiteralPath $item -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)){
    throw 'Original restricted worker exact read-only source directory refused'
  }
  & icacls.exe $item /grant '*S-1-5-32-545:(OI)(CI)RX' /T
  if($LASTEXITCODE -ne 0){throw 'Cannot grant restricted test SID source read/execute'}
}
# BUILTIN Users WRITE is limited to the disposable numerical input/output
# staging directory (never to the source tree or Python executable).
& icacls.exe $root /grant '*S-1-5-32-545:(OI)(CI)M' /T
if($LASTEXITCODE -ne 0){throw 'Windows temporary restricted SID fixture ACL unavailable'}
}
& ./scripts/cog-r5-physical02-r1-real-ssm-scm.ps1 -Executable $Executable -FixtureRoot $root -EvidencePath "$PWD/r2-r1-windows.json"
$r1=Get-Content -LiteralPath "$PWD/r2-r1-windows.json" -Raw | ConvertFrom-Json
if($r1.status -cne 'PASS_REAL_FIXED_SSM_UNDER_SCM_FIXTURE_ONLY' -or
   $r1.original_one_use_restart_replay_denied -ne $true -or
   $r1.independent_child_job_membership_observed -ne $true -or
   ($RequireRestrictedToken -and $r1.independently_observed_restricted_token -ne $true)){
 throw 'Actual OS independently observed restricted primary token/Job missing'
}
$raw=& python scripts/cog_r5_r2_verify_signed_stop.py --root "$root"
if($LASTEXITCODE -ne 0){throw 'Independent ECDSA P256 signed CNG stop refused'}
$verified=$raw | ConvertFrom-Json
if($verified.real_native_CNG_signature_valid -ne $true -or
   $verified.exact_original_SSM_request_and_nonce_bound -ne $true -or
   $verified.production_issuer_independently_enrolled -ne $false -or
   $verified.external_output_release_authorized -ne $false){
 throw 'Original OS signer claim or authority mismatch'
}
Copy-Item -LiteralPath $enrollment -Destination "$PWD/r2-public-test-enrollment.json"
$pubsha=(Get-FileHash -LiteralPath $public -Algorithm SHA256).Hash.ToLowerInvariant()
$signedsha=(Get-FileHash -LiteralPath $signed -Algorithm SHA256).Hash.ToLowerInvariant()
$status=if($RequireRestrictedToken){'PASS_REAL_RESTRICTED_SSM_CNG_SIGNED_CI_ONLY'}else{'PASS_SCM_OWNED_SSM_CNG_SIGNED_CI_ONLY'}
$report=[ordered]@{
 schema='cognitum.ssm.r2.real_native_CNG_test.v1'
 status=$status
 genuine_SCM_service_Job_owned_fixed_SSM=$true
 original_one_use_HMAC_test_intent=$true
 real_OS_restricted_primary_token_independently_observed=[bool]($RequireRestrictedToken -and $r1.independently_observed_restricted_token)
 real_OS_Job_membership_independently_observed=$true
 numerical_SSM_output_independently_recalculated=$true
 original_service_restart_replay_denied=$true
 real_OS_KSP_nonexportable_P256_signer=$true
 externally_provisioned_public_blob_pin=$pubsha
 signed_stop_file_sha256=$signedsha
 original_kernel_empty_local_stop_authenticated=$true
 ephemerally_provisioned_test_signer_only=$true
 original_worker_AppContainer=$false
 original_worker_low_privilege_user_not_SYSTEM=$false
 installed_signed_production_publisher=$false
 installer_protected_image_and_data_ACL=$false
 independent_production_receipt_issuer=$false
 independently_pinned_monotonic_restart_anchor=$false
 authentic_Core_Health_authenticated=$false
 original_Core_pure_compute_grant=$false
 output_delivery_or_ack_authorized=$false
}
($report|ConvertTo-Json -Depth 5) | Set-Content -LiteralPath $evidence -Encoding utf8
Write-Host $status
