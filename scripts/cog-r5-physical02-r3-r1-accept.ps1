# R3-R1: ACTUAL external nonadministrator AppContainer SSM acceptance, CI only.
# No model tool, Lu grant, publisher approval or output delivery ever follows.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$Executable,
 [Parameter(Mandatory=$true)][string]$HostRoot,
 [Parameter(Mandatory=$true)][string]$WorkerRoot,
 [Parameter(Mandatory=$true)][string]$ProvisionRoot,
 [Parameter(Mandatory=$true)][string]$RuntimeRoot,
 [Parameter(Mandatory=$true)][string]$EvidencePath
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($env:OS -ne 'Windows_NT'){throw 'Actual native Windows SCM Job required'}
$hostDir=[IO.Path]::GetFullPath($HostRoot)
$io=[IO.Path]::GetFullPath($WorkerRoot)
$provision=[IO.Path]::GetFullPath($ProvisionRoot)
$runtime=[IO.Path]::GetFullPath($RuntimeRoot)
$identity=Join-Path $provision 'r3-r1-external-nonadmin.json'
if(!(Test-Path $identity -PathType Leaf)){throw 'Original dedicated nonadmin OS identity missing'}
$peer=Get-Content -LiteralPath $identity -Raw|ConvertFrom-Json
if($peer.schema -cne 'cognitum.ssm.r3r1.external_nonadministrator_CI_profile.v1' -or
   $peer.user_sid -cne $env:COG_R3_CI_PEER_SID -or
   $peer.profile_sid -cne $env:COG_R3_CI_APP_SID -or
   $peer.original_peer_pid -ne [uint32]$env:COG_R3_CI_PEER_PID -or
   $peer.original_peer_birth -ne [ulong]$env:COG_R3_CI_PEER_BIRTH -or
   $peer.user_is_member_of_Administrators -ne $false -or
   $peer.AppContainer_created_as_own_nonadmin_user -ne $true -or
   $peer.no_network_capabilities -ne $true){
 throw 'R3-R1 runtime is not pinned to external nonadministrator package identity'
}
$rootValues=@($hostDir,$io,$provision,$runtime)|Select-Object -Unique
if(@($rootValues).Count -ne 4){throw 'Numerical and host-owned signed/immutable directories must differ'}
function Refuse-Writable([string]$directory,[bool]$shouldBeWritable){
 $acl=Get-Acl -LiteralPath $directory
 $ids=@($peer.user_sid,$peer.profile_sid)
 $records=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
 $writes=@($records|Where-Object{
    $_.AccessControlType -eq [Security.AccessControl.AccessControlType]::Allow -and
    $ids -ccontains $_.IdentityReference.Value -and
    (([int64]$_.FileSystemRights -band 0x000d0116L) -ne 0)
 })
 if($shouldBeWritable -and !$writes){throw 'Numerical I/O missing bounded AppContainer write'}
 if(!$shouldBeWritable -and $writes){throw 'AppContainer/nonadmin can modify signed original/installer runtime files'}
}
Refuse-Writable $hostDir $false
Refuse-Writable $runtime $false
Refuse-Writable $io $true
# Actual native SCM Job and P256 original terminal and replay lifecycle.
& ./scripts/cog-r5-physical02-r1-real-ssm-scm.ps1 -Executable $Executable -FixtureRoot $hostDir -WorkerRoot $io -EvidencePath "$PWD/r3-r1-original-scm.json"
$proof=Get-Content -LiteralPath (Join-Path $hostDir 'r3-original-appcontainer-witness.json') -Raw|ConvertFrom-Json
$r1=Get-Content -LiteralPath "$PWD/r3-r1-original-scm.json" -Raw|ConvertFrom-Json
if($proof.schema -cne 'cognitum.ssm.r3.original_appcontainer_kernel_witness.v1' -or
   $proof.native_TokenIsAppContainer -ne $true -or
   $proof.native_TokenUser_is_SYSTEM -ne $false -or
   $proof.native_TokenElevation_is_zero -ne $true -or
   $proof.checked_before_worker_resume -ne $true -or
   $proof.source_user_sid -cne $peer.user_sid -or
   $proof.appcontainer_sid -cne $peer.profile_sid -or
   $proof.original_peer_birth -ne [ulong]$peer.original_peer_birth -or
   $proof.worker_pid -ne $r1.numerical_worker_pid -or
   $r1.real_SSM_output_matches_independent_factory -ne $true -or
   $r1.kernel_job_empty_after_stop -ne $true -or
   $r1.original_one_use_restart_replay_denied -ne $true){
 throw 'Native nonadministrator/AppContainer actual SSM worker, kernel Job or math verification failed'
}
$terminalRaw=& python scripts/cog_r5_r2_verify_signed_stop.py --root "$hostDir"
if($LASTEXITCODE -ne 0){throw 'OS CNG signed original worker terminal receipt invalid'}
$terminal=$terminalRaw|ConvertFrom-Json
if($terminal.real_native_CNG_signature_valid -ne $true -or
   $terminal.external_output_release_authorized -ne $false){
 throw 'Original kernel stop signature/authorization invalid'
}
$replayRaw=& python scripts/cog_r5_r3_verify_recovery.py --root "$hostDir" --expected-kind replay_refused
if($LASTEXITCODE -ne 0){throw 'CNG signed original replay refusal invalid'}
$replay=$replayRaw|ConvertFrom-Json
if($replay.signed_original_restart -ne $true -or
   $replay.two_distinct_kernel_service_generations -ne $true -or
   $replay.external_output_release_authorized -ne $false){
 throw 'Original restarted SCM returned invalid replay/uncertain claim'
}
$manifest=Join-Path $runtime 'r3-r1-runtime.manifest'
$manifestSha=(Get-FileHash -LiteralPath $manifest -Algorithm SHA256).Hash.ToLowerInvariant()
if($manifestSha -cne $env:COG_R3_R1_RUNTIME_MANIFEST_SHA256){
 throw 'Original prelaunch image manifest no longer matches pinned build'
}
[ordered]@{
 schema='cognitum.ssm.r3r1.nonadmin_frozen_appcontainer_native_CI.v1'
 status='PASS_NATIVE_NONADMIN_APP_CONTAINER_FULL_SSM_AND_CNG_STOP_REPLAY_CI_ONLY'
 original_nonadministrator_user_sid=$peer.user_sid
 original_appcontainer_sid=$peer.profile_sid
 actual_TokenElevation_zero=$true
 actual_TokenIsAppContainer_one=$true
 appcontainer_SCM_Job_attached_before_first_instruction=$true
 actual_frozen_Python_NumPy_SciPy_result_independently_recomputed=$true
 runtime_manifest_SHA256=$manifestSha
 original_machine_CNG_signed_terminal_and_replay_refusal=$true
 original_kernel_Job_empty_after_terminal_stop=$true
 host_signer_directory_not_writable_by_worker=$true
 runtime_imports_not_writable_by_worker=$true
 installer_publisher_independently_approved=$false
 separate_production_signer_approved=$false
 physical_installed_signed_package_accepted=$false
 Lu_Core_Health_authenticated=$false
 original_Core_PURE_COMPUTE_grant=$false
 output_release_or_ACK_authorized=$false
}|ConvertTo-Json -Depth 4|Set-Content -LiteralPath $EvidencePath -Encoding utf8
Write-Host 'PASS_NATIVE_NONADMIN_APP_CONTAINER_FULL_SSM_AND_CNG_STOP_REPLAY_CI_ONLY'
