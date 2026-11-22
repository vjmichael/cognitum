# R3-R1: READ-ONLY personally GPG-signed PROTECTED successor custody.
# Never install, provision, start, sign, authorize Lu, or deliver output.
# Source-level preflight, not protected worker or external antirollback acceptance.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$Stage,
 [Parameter(Mandatory=$true)][string]$InstalledRoot,
 [Parameter(Mandatory=$true)][string]$ApprovedManifestSha256,
 [Parameter(Mandatory=$true)][string]$ApprovedSourceSha,
 [Parameter(Mandatory=$true)][string]$ApprovedGpgPrimaryFingerprint,
 [Parameter(Mandatory=$true)][string]$TrustedPublicKeyFile,
 [Parameter(Mandatory=$true)][string]$NativeGpgExe
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function Refuse([string]$reason){throw ('COG_R3R1_PROTECTED_CUSTODY_REFUSED: '+$reason)}
if($env:OS -cne 'Windows_NT' -or -not [Environment]::Is64BitProcess -or $env:GITHUB_ACTIONS -eq 'true'){
 Refuse 'Physical 64-bit Windows only; hosted CI cannot attest installed custody'
}
if($ApprovedSourceSha -cnotmatch '^[0-9a-f]{40}$' -or
   $ApprovedManifestSha256 -cnotmatch '^[0-9a-f]{64}$' -or
   $ApprovedManifestSha256 -ceq ('0'*64) -or
   $ApprovedGpgPrimaryFingerprint -cnotmatch '^([0-9A-F]{40}|[0-9A-F]{64})$'){
 Refuse 'Externally approved source/manifest/GPG identities absent'
}
foreach($path in @($Stage,$InstalledRoot,$TrustedPublicKeyFile,$NativeGpgExe)){
 if(-not [IO.Path]::IsPathRooted($path)){Refuse 'Absolute trusted paths required'}
}
$stageRoot=[IO.Path]::GetFullPath($Stage).TrimEnd('\')
$installed=[IO.Path]::GetFullPath($InstalledRoot).TrimEnd('\')
if($stageRoot.Equals($installed,[StringComparison]::OrdinalIgnoreCase)){
 Refuse 'Staging and installed root must be independent'
}
$manifest=Join-Path $stageRoot 'protected-successor.json'
$signature=Join-Path $stageRoot 'protected-successor.json.asc'
$installer=Join-Path $stageRoot 'Cognitum-SSM-R3R1-Protected.exe'
$exe=Join-Path $installed 'cognitum-scm-production.exe'
# The installed successor is an elevated SCM production service. Refuse a
# user-writable local checkout or portable folder even if it has the expected
# SHA-256 today: parent replacement after verification would be unsafe.
$programFiles=[IO.Path]::GetFullPath($env:ProgramFiles).TrimEnd('\')
if(-not $installed.StartsWith(($programFiles+'\'),[StringComparison]::OrdinalIgnoreCase)){
 Refuse 'Protected successor must reside under native Program Files'
}
$runtime=Join-Path $installed 'runtime'
$python=Join-Path $runtime 'python.exe'
$child=Join-Path $runtime 'cognitum\mel\ssm_r5_production_child.py'
foreach($path in @($stageRoot,$installed,$manifest,$signature,$installer,
                   $exe,$runtime,$python,$child,$TrustedPublicKeyFile,$NativeGpgExe)){
 if(-not (Test-Path -LiteralPath $path)){Refuse 'Original approved successor file absent'}
 if(((Get-Item -LiteralPath $path -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
  Refuse 'Redirected protected staged/installed file refused'
 }
}
if((Get-Item -LiteralPath $manifest).Length -gt 8192 -or
   (Get-Item -LiteralPath $signature).Length -gt 16384 -or
   (Get-Item -LiteralPath $TrustedPublicKeyFile).Length -gt 65536){
 Refuse 'Original detached approval/public key exceeded size bounds'
}
if($NativeGpgExe -match '(?i)\\Git\\(usr|mingw64)\\bin\\gpg\.exe$'){
 Refuse 'Require native GnuPG path semantics for this successor audit'
}
if((Get-FileHash -LiteralPath $manifest -Algorithm SHA256).Hash.ToLowerInvariant() -cne
   $ApprovedManifestSha256){Refuse 'Original GPG manifest differs from external pin'}
$home=Join-Path $env:TEMP ('cog-r3r1-protected-gpg-'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $home -WhatIf:$false -ErrorAction Stop | Out-Null
try {
 $null=@(& $NativeGpgExe --homedir $home --batch --no-tty --no-auto-key-retrieve --import $TrustedPublicKeyFile 2>&1)
 if($LASTEXITCODE -ne 0){Refuse 'Cannot load external GPG public key'}
 $lines=@(& $NativeGpgExe --homedir $home --batch --no-tty --with-colons --fingerprint --list-keys 2>&1)
 if($LASTEXITCODE -ne 0){Refuse 'Original GPG primary identity unavailable'}
 $primaries=@()
 $follow=$false
 foreach($line in $lines){
  $parts=([string]$line).Split(':')
  if($parts[0] -ceq 'pub'){$follow=$true;continue}
  if($parts[0] -ceq 'sub'){$follow=$false;continue}
  if($parts[0] -ceq 'fpr' -and $follow){
   $primaries+=([string]$parts[9]).ToUpperInvariant()
   $follow=$false
  }
 }
 if($primaries.Count -ne 1 -or $primaries[0] -cne $ApprovedGpgPrimaryFingerprint){
  Refuse 'Signed candidate GPG primary differs from independently selected owner'
 }
 $verified=@(& $NativeGpgExe --homedir $home --batch --no-tty --no-auto-key-retrieve --status-fd 1 --verify $signature $manifest 2>&1)
 if($LASTEXITCODE -ne 0 -or
    @($verified|Where-Object{([string]$_) -match '^\[GNUPG:\] VALIDSIG '}).Count -ne 1){
  Refuse 'Exactly one valid original detached owner GPG signature required'
 }
}finally {
 Remove-Item -LiteralPath $home -Recurse -Force -WhatIf:$false -ErrorAction Stop
}
try{$claim=Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json -AsHashtable}
catch{Refuse 'Unparseable closed successor candidate'}
if($claim.source_sha -cne $ApprovedSourceSha -or
   $claim.protected_service_name -cne 'CognitumSsmProtectedV1' -or
   $claim.replaced_bootstrap_service_name -cne 'CognitumSsmSupervisorV1' -or
   $claim.output_or_ACK_authorized -ne $false){
 Refuse 'Signed successor source/service is old no-worker or CI fixture'
}
function Pin([string]$file,[string]$approved) {
 if($approved -cnotmatch '^[0-9a-f]{64}$' -or
    (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -cne $approved){
  Refuse 'Actual protected successor artifact differs from approved bytes'
 }
}
# Protect the native SCM binary from replacement after owner-GPG hash
# observation. Evaluate the executable AND every ancestor to Program Files.
# TrustedInstaller is a legitimate default Windows directory owner.
$trustedOwners=@(
 'S-1-5-18',
 'S-1-5-32-544',
 'S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464'
)
$writeMask=[int64]0x500D0156L
$cursor=$exe
while($true){
 $obj=Get-Item -LiteralPath $cursor -Force -ErrorAction Stop
 if(($obj.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
  Refuse 'Redirected service binary or Program Files ancestry refused'
 }
 $acl=Get-Acl -LiteralPath $cursor -ErrorAction Stop
 try{$owner=$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value}
 catch{Refuse 'Native protected executable owner unavailable'}
 if($trustedOwners -cnotcontains $owner){
  Refuse 'Untrusted native SCM image or ancestor ownership'
 }
 foreach($ace in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])){
  if($ace.AccessControlType -eq [Security.AccessControl.AccessControlType]::Allow -and
     ([int64]$ace.FileSystemRights -band $writeMask) -ne 0 -and
     $trustedOwners -cnotcontains $ace.IdentityReference.Value){
   Refuse 'Untrusted native SCM image/ancestor mutation rights'
  }
 }
 if($cursor.Equals($programFiles,[StringComparison]::OrdinalIgnoreCase)){break}
 $parent=[IO.Directory]::GetParent($cursor)
 if($null -eq $parent){Refuse 'Native SCM image escaped approved Program Files root'}
 $cursor=$parent.FullName.TrimEnd('\')
}
Pin $installer ([string]$claim.protected_nsis_installer_sha256)
Pin $exe ([string]$claim.protected_service_image_sha256)
Pin $python ([string]$claim.frozen_python_image_sha256)
Pin $child ([string]$claim.protected_ssm_child_sha256)
$contract=Join-Path $PSScriptRoot 'cog_r3r1_protected_successor_contract.py'
if(-not (Test-Path -LiteralPath $contract -PathType Leaf)){
 Refuse 'Reviewed closed successor admission contract unavailable'
}
$claimJson=& $python -I -B $contract --manifest $manifest --approved-manifest-sha256 $ApprovedManifestSha256 --approved-source-sha $ApprovedSourceSha --approved-gpg-primary-fingerprint $ApprovedGpgPrimaryFingerprint
if($LASTEXITCODE -ne 0){Refuse 'Original signed successor candidate contract refused'}
try{$policy=($claimJson|Out-String)|ConvertFrom-Json}
catch{Refuse 'Closed candidate policy returned invalid evidence'}
if($policy.status -cne 'PASS_CLOSED_PROTECTED_SUCCESSOR_METADATA_PINS_OBSERVATION_ONLY' -or
   $policy.output_or_ACK_authorized -ne $false){
 Refuse 'Signed candidate policy did not remain observation only'
}
$auditor=Join-Path $PSScriptRoot 'cog-r5-physical02-r3-r1-runtime-audit.ps1'
$runtimeRaw=& $auditor -ApprovedInstallRoot $installed -RuntimeRoot $runtime -ApprovedManifestSha256 ([string]$claim.frozen_runtime_manifest_sha256) -ApprovedProvenanceSha256 ([string]$claim.frozen_runtime_provenance_sha256)
try{$r=($runtimeRaw|Out-String)|ConvertFrom-Json}catch{Refuse 'Full immutable runtime auditor unavailable'}
if($r.status -cne 'PASS_INSTALLED_RUNTIME_DIGEST_ACL_OBSERVATION_ONLY' -or
   $r.original_file_count -ne [int]$claim.protected_runtime_file_count -or
   $r.output_release_authorized -ne $false){
 Refuse 'Pinned full frozen Python import closure/ACL not accepted'
}
# No future protected service may impersonate the existing NO-WORKER service
# or the disposable Windows CI qualifier.
$service='CognitumSsmProtectedV1'
$scm=Get-CimInstance Win32_Service -Filter "Name='$service'"
if($null -eq $scm -or
   $scm.StartName -notin @('LocalSystem','NT AUTHORITY\LocalSystem') -or
   $scm.State -cne 'Running' -or [uint32]$scm.ProcessId -le 0 -or
   $scm.PathName.Trim('"') -cne $exe){
 Refuse 'Genuine distinct installed protected SCM service/image missing'
}
$proc=Get-CimInstance Win32_Process -Filter ("ProcessId="+[uint32]$scm.ProcessId)
if($null -eq $proc -or [uint32]$proc.SessionId -ne 0){
 Refuse 'Native installed protected service not running in Session 0'
}
$who=Invoke-CimMethod -InputObject $proc -MethodName GetOwnerSid
if($who.ReturnValue -ne 0 -or $who.Sid -cne 'S-1-5-18'){
 Refuse 'Native protected SCM supervisor is not LocalSystem'
}
$ksp=Join-Path $PSScriptRoot 'cog-r3r1-production-cng-observe.ps1'
$raw=& $ksp -ExistingMachineKeyName ([string]$claim.preprovisioned_machine_cng_key_name) -ApprovedPublicBlobSha256 ([string]$claim.preprovisioned_machine_cng_public_blob_sha256)
try{$cng=($raw|Out-String)|ConvertFrom-Json}catch{Refuse 'Native CNG signer observation absent'}
if($cng.status -cne 'PASS_PREEXISTING_MACHINE_CNG_PUBLIC_IDENTITY_OBSERVATION_ONLY' -or
   $cng.private_export_policy_disabled -ne $true -or
   $cng.key_created_or_changed -ne $false -or
   $cng.public_blob_sha256 -cne $claim.preprovisioned_machine_cng_public_blob_sha256){
 Refuse 'Original independent persistent machine CNG signer identity not established'
}
[pscustomobject]@{
 schema='cognitum.ssm.r3r1.protected_successor_installed_custody_observation.v1'
 status='PASS_DISTINCT_GPG_PINNED_PROTECTED_SCM_RUNTIME_CNG_OBSERVATION_ONLY'
 installed_service=$service
 installed_service_pid=[uint32]$scm.ProcessId
 approved_source_sha=$ApprovedSourceSha
 complete_frozen_runtime_inventory_observed=$true
 existing_machine_cng_public_pin_observed=$true
 old_no_worker_installation_promoted=$false
 owner_GPG_is_Windows_Authenticode=$false
 actual_protected_worker_run_verified=$false
 production_CNG_terminal_receipts_verified=$false
 persistent_external_antirollback_accepted=$false
 authentic_Lu_Core_operation_grant_verified=$false
 physical_full_successor_acceptance=$false
 output_or_ACK_authorized=$false
}|ConvertTo-Json -Compress
