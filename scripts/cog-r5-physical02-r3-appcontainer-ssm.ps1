# R3 full Python SSM inside actual Windows lowbox AppContainer CI admission.
# Requires independently created/test-only user profile, original process
# generation, exact Python/script hashes, CNG key and SCM Job. No fallback.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$Executable,
 [Parameter(Mandatory=$true)][string]$FixtureRoot,
 [Parameter(Mandatory=$true)][string]$EvidencePath
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($env:OS -ne 'Windows_NT'){throw 'Native Windows AppContainer SSM required'}
$root=[IO.Path]::GetFullPath($FixtureRoot)
$manifest=Join-Path $root 'r3-external-appcontainer.json'
$witness=Join-Path $root 'r3-original-appcontainer-witness.json'
$refusal=Join-Path $root 'r3-appcontainer-refusal.json'
if(!(Test-Path -LiteralPath $manifest -PathType Leaf) -or
   (Test-Path -LiteralPath $witness) -or
   (Test-Path -LiteralPath $refusal)){
  throw 'Independent low-privilege original profile absent, stale or reused'
}
$enroll=Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if($enroll.schema -cne 'cognitum.ssm.r3.external_CI_AppContainer_profile.v1' -or
   $enroll.profile -cne 'CognitumSsmR3CiSandboxV1' -or
   $enroll.original_peer_pid -ne [uint32]$env:COG_R3_CI_PEER_PID -or
   $enroll.original_peer_user_sid -cne $env:COG_R3_CI_PEER_SID -or
   $enroll.profile_sid -cne $env:COG_R3_CI_APP_SID -or
   $enroll.original_peer_birth -ne [ulong]$env:COG_R3_CI_PEER_BIRTH){
  throw 'Exact original peer/package SID installer-style pins differ'
}
# The real R1 harness performs SCM create/start/OS process+owner checks,
# native JOB, numerical recomputation, CNG signed terminal stop and restart
# refusal, then verifies the temporary native service deletion.
try{
 & ./scripts/cog-r5-physical02-r1-real-ssm-scm.ps1 -Executable $Executable -FixtureRoot $root -EvidencePath "$PWD/r3-app-r1-result.json"
}catch{
 if(Test-Path -LiteralPath $refusal -PathType Leaf){
   $stage=Get-Content -LiteralPath $refusal -Raw | ConvertFrom-Json
   throw ("R3 native AppContainer original SSM refused "+$stage.stage+": "+$stage.reason)
 }
 throw
}
if(!(Test-Path -LiteralPath $witness -PathType Leaf)){
 throw 'Original kernel AppContainer user SID/witness not written before worker resume'
}
$proof=Get-Content -LiteralPath $witness -Raw | ConvertFrom-Json
$r1=Get-Content -LiteralPath "$PWD/r3-app-r1-result.json" -Raw | ConvertFrom-Json
if($proof.schema -cne 'cognitum.ssm.r3.original_appcontainer_kernel_witness.v1' -or
   $proof.native_TokenIsAppContainer -ne $true -or
   $proof.native_TokenUser_is_SYSTEM -ne $false -or
   $proof.checked_before_worker_resume -ne $true -or
   $proof.source_user_sid -cne $env:COG_R3_CI_PEER_SID -or
   $proof.appcontainer_sid -cne $env:COG_R3_CI_APP_SID -or
   [uint32]$proof.worker_pid -ne [uint32]$r1.numerical_worker_pid -or
   [ulong]$proof.original_peer_birth -ne [ulong]$env:COG_R3_CI_PEER_BIRTH -or
   $r1.real_SSM_output_matches_independent_factory -ne $true -or
   $r1.kernel_job_empty_after_stop -ne $true -or
   $r1.original_one_use_restart_replay_denied -ne $true){
 throw 'Native AppContainer real fixed SSM, OS SID or original SCM kernel proof not accepted'
}
$stopjson=& python scripts/cog_r5_r2_verify_signed_stop.py --root "$root"
if($LASTEXITCODE -ne 0){throw 'R3 native AppContainer original signed terminal stop refused'}
$terminal=$stopjson | ConvertFrom-Json
if($terminal.real_native_CNG_signature_valid -ne $true -or
   $terminal.external_output_release_authorized -ne $false){
 throw 'Original AppContainer terminal receipt invalid/overclaimed authorization'
}
$restartJson=& python scripts/cog_r5_r3_verify_recovery.py --root "$root" --expected-kind replay_refused
if($LASTEXITCODE -ne 0){throw 'Original kernel AppContainer signed restart refusal invalid'}
$restart=$restartJson | ConvertFrom-Json
if($restart.signed_original_restart -ne $true -or
   $restart.restart_kind -cne 'replay_refused' -or
   $restart.external_output_release_authorized -ne $false){
 throw 'AppContainer original replay suppression/uncertain refusal invalid'
}
[ordered]@{
 schema='cognitum.ssm.r3.native_original_appcontainer_full_ssm_CI.v1'
 status='PASS_FULL_PYTHON_SSM_NATIVE_NON_SYSTEM_APP_CONTAINER_CI_ONLY'
 true_OS_TokenIsAppContainer_before_resuming_original_worker=$true
 true_OS_TokenUser_non_SYSTEM=$true
 exact_profile_SID_and_live_non_SYSTEM_user_generation_pinned=$true
 real_fixed_Python_SSM_original_numerical_result=$true
 original_kernel_job_owned_by_real_Windows_SCM=$true
 original_terminal_kernel_empty_and_machine_CNG_signed=$true
 original_signed_prelaunch_and_restart_refusal=$true
 signed_original_output_authorized=$false
 installed_signed_publisher_verified=$false
 authentic_Core_Health_verified=$false
 independently_approved_production_CNG_issuer=$false
 externally_monotonic_antirollback_verified=$false
 }|ConvertTo-Json -Depth 4|Set-Content -LiteralPath $EvidencePath -Encoding utf8
Write-Host 'PASS_FULL_PYTHON_SSM_NATIVE_NON_SYSTEM_APP_CONTAINER_CI_ONLY'
