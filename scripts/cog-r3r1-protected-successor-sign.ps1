# R3-R1 local owner ECC-GPG detached signature over an independently
# reviewed exact protected-successor candidate. Never builds or installs,
# changes original no-worker service, provisions CNG, enrolls Core, or ACKs.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$ExactSourceSha,
 [Parameter(Mandatory=$true)][string]$ApprovedCandidateManifestSha256,
 [Parameter(Mandatory=$true)][string]$StageRoot,
 [Parameter(Mandatory=$true)][string]$OwnerPrimaryFingerprint,
 [Parameter(Mandatory=$true)][string]$GpgExecutable,
 [Parameter(Mandatory=$true)][string]$TrustedPublicKeyFile
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function Refuse([string]$reason){throw ('COG_R3R1_PROTECTED_SIGN_REFUSED: '+$reason)}
if($env:OS -cne 'Windows_NT' -or $env:GITHUB_ACTIONS -eq 'true' -or
   $env:CI -eq 'true' -or -not [Environment]::Is64BitProcess){
 Refuse 'Original personal 64-bit Windows GPG signing host required, not CI'
}
if($ExactSourceSha -cnotmatch '^[0-9a-f]{40}$' -or
   $ApprovedCandidateManifestSha256 -cnotmatch '^[0-9a-f]{64}$' -or
   $ApprovedCandidateManifestSha256 -ceq ('0'*64) -or
   $OwnerPrimaryFingerprint -cnotmatch '^([A-Fa-f0-9]{40}|[A-Fa-f0-9]{64})$'){
 Refuse 'Exact independently reviewed source/manifest/owner primary pins required'
}
$fp=$OwnerPrimaryFingerprint.ToUpperInvariant()
foreach($path in @($StageRoot,$GpgExecutable,$TrustedPublicKeyFile)){
 if(-not [IO.Path]::IsPathRooted($path)){Refuse 'Trusted owner key/tool/stage must be absolute'}
}
foreach($path in @($GpgExecutable,$TrustedPublicKeyFile)){
 if(-not (Test-Path -LiteralPath $path -PathType Leaf)){Refuse 'Existing owner public key/GPG tool unavailable'}
}
if($GpgExecutable -match '(?i)\\Git\\(usr|mingw64)\\bin\\gpg\.exe$'){
 Refuse 'Protected successor sign gate requires native GnuPG path semantics'
}
$stage=[IO.Path]::GetFullPath($StageRoot).TrimEnd('\')
$release=Join-Path $stage ('r3r1-protected-'+$ExactSourceSha.Substring(0,16))
if(-not (Test-Path -LiteralPath $release -PathType Container)){
 Refuse 'Original unsigned reviewed protected candidate not staged'
}
$manifest=Join-Path $release 'protected-successor.json'
$signature=Join-Path $release 'protected-successor.json.asc'
if(Test-Path -LiteralPath $signature){Refuse 'Original detached signature exists; never rewrite or re-sign'}
$acl=Get-Acl -LiteralPath $stage
$trusted=@('S-1-5-18','S-1-5-32-544')
if($trusted -cnotcontains $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -or
   -not $acl.AreAccessRulesProtected){
 Refuse 'Owner signing stage requires protected administrator custody'
}
if((Get-FileHash -LiteralPath $manifest -Algorithm SHA256).Hash.ToLowerInvariant() -cne
   $ApprovedCandidateManifestSha256){Refuse 'Original candidate bytes differ from exact reviewed digest'}
$source=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$git=@(& git.exe -C $source rev-parse HEAD)
if($LASTEXITCODE -ne 0 -or $git.Count -ne 1 -or $git[0] -cne $ExactSourceSha){
 Refuse 'Owner release signer source tool not at original reviewed exact SHA'
}
$dirty=@(& git.exe -C $source status --porcelain --untracked-files=no)
if($LASTEXITCODE -ne 0 -or $dirty.Count -ne 0){Refuse 'Signer source tree is not clean'}
# The signing preflight must NOT trust python.exe on PATH or reuse the
# candidate creator's validation code. Use only the original pinned frozen
# Python image, then run the separately implemented read-only byte reviewer.
try{$candidate=Get-Content -LiteralPath $manifest -Raw|ConvertFrom-Json}
catch{Refuse 'Exact reviewed candidate cannot be parsed'}
$python=Join-Path $release 'payload\runtime\python.exe'
if(-not(Test-Path -LiteralPath $python -PathType Leaf) -or
   $candidate.frozen_python_image_sha256 -cnotmatch '^[0-9a-f]{64}
$secret=@(& $GpgExecutable --batch --no-tty --with-colons --fingerprint --list-secret-keys $fp 2>&1)
if($LASTEXITCODE -ne 0 -or -not(($secret -join [char]10).ToUpperInvariant().Contains($fp))){
 Refuse 'Local owner GPG signing private key not available'
}
& $GpgExecutable --batch --no-tty --armor --local-user $fp --output $signature --detach-sign $manifest
if($LASTEXITCODE -ne 0 -or -not(Test-Path -LiteralPath $signature -PathType Leaf)){
 Refuse 'Original locally held ECC-GPG key could not sign exact candidate'
}
$home=Join-Path $env:TEMP ('cog-r3r1-sig-public-'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $home -ErrorAction Stop |Out-Null
try{
 $null=@(& $GpgExecutable --homedir $home --batch --no-tty --no-auto-key-retrieve --import $TrustedPublicKeyFile 2>&1)
 if($LASTEXITCODE -ne 0){Refuse 'External trusted GPG public key unreadable'}
 $listing=@(& $GpgExecutable --homedir $home --batch --no-tty --with-colons --fingerprint --list-keys 2>&1)
 if($LASTEXITCODE -ne 0){Refuse 'Isolated public signer list failed'}
 $primary=@()
 $following=$false
 foreach($line in $listing){
  $parts=([string]$line).Split(':')
  if($parts[0] -ceq 'pub'){$following=$true;continue}
  if($parts[0] -ceq 'sub'){$following=$false;continue}
  if($parts[0] -ceq 'fpr' -and $following){
   $primary+=([string]$parts[9]).ToUpperInvariant()
   $following=$false
  }
 }
 if($primary.Count -ne 1 -or $primary[0] -cne $fp){
  Refuse 'Independent primary public owner GPG fingerprint does not match'
 }
 $verified=@(& $GpgExecutable --homedir $home --batch --no-tty --no-auto-key-retrieve --status-fd 1 --verify $signature $manifest 2>&1)
 if($LASTEXITCODE -ne 0 -or
    @($verified|Where-Object{([string]$_) -match '^\[GNUPG:\] VALIDSIG '}).Count -ne 1){
  Refuse 'Exact original owner detached signature failed public verification'
 }
}finally{
 Remove-Item -LiteralPath $home -Recurse -Force -WhatIf:$false -ErrorAction Stop
}
if((Get-FileHash -LiteralPath $manifest -Algorithm SHA256).Hash.ToLowerInvariant() -cne
   $ApprovedCandidateManifestSha256){Refuse 'GPG signing modified original reviewed bytes'}
[pscustomobject]@{
 schema='cognitum.ssm.r3r1.protected_owner_gpg_release.v1'
 status='PASS_OWNER_GPG_PROTECTED_CANDIDATE_SIGNED_NO_INSTALL'
 exact_source_sha=$ExactSourceSha
 reviewed_candidate_manifest_sha256=$ApprovedCandidateManifestSha256
 owner_gpg_primary_fingerprint=$fp
 independent_reviewer_approval_cryptographically_verified=$false
 physically_installed_protected_worker=$false
 preexisting_production_CNG_signer_accepted=$false
 external_antirollback_freshness_verified=$false
 original_Lu_Core_operation_grant_verified=$false
 output_or_ACK_authorized=$false
}|ConvertTo-Json -Compress
 -or
   (Get-FileHash -LiteralPath $python -Algorithm SHA256).Hash.ToLowerInvariant() -cne
      $candidate.frozen_python_image_sha256){
 Refuse 'Original reviewed frozen Python image unavailable or changed before sign'
}
$reviewer=Join-Path $PSScriptRoot 'cog_r3r1_independent_byte_review.py'
if(-not(Test-Path -LiteralPath $reviewer -PathType Leaf)){
 Refuse 'Separate original read-only full-byte reviewer missing'
}
$reviewArgs=@(
 $reviewer,'--stage',$release,
 '--source-sha',$ExactSourceSha,
 '--owner-fingerprint',$fp,
 '--source-checkout',$source,
 '--expected-candidate-sha256',$ApprovedCandidateManifestSha256
)
$review=@(& $python -I -B @reviewArgs)
if($LASTEXITCODE -ne 0){Refuse 'Independent original pre-sign byte/source review refused'}
try{$observed=($review|Out-String)|ConvertFrom-Json}
catch{Refuse 'Independent original review did not return closed evidence'}
if($observed.status -cne 'PASS_INDEPENDENT_IMPLEMENTATION_BYTE_REVIEW_OBSERVATION_ONLY' -or
   $observed.read_only_source_checkout_verified -ne $true -or
   $observed.all_installer_native_and_runtime_hashes_verified -ne $true -or
   $observed.manifest_sha256 -cne $ApprovedCandidateManifestSha256 -or
   $observed.independent_reviewer_approved -ne $false -or
   $observed.original_owner_GPG_signature_verified -ne $false -or
   $observed.output_or_ACK_authorized -ne $false){
 Refuse 'Original independent review mismatched source/bytes or falsely granted authority'
}
$secret=@(& $GpgExecutable --batch --no-tty --with-colons --fingerprint --list-secret-keys $fp 2>&1)
if($LASTEXITCODE -ne 0 -or -not(($secret -join [char]10).ToUpperInvariant().Contains($fp))){
 Refuse 'Local owner GPG signing private key not available'
}
& $GpgExecutable --batch --no-tty --armor --local-user $fp --output $signature --detach-sign $manifest
if($LASTEXITCODE -ne 0 -or -not(Test-Path -LiteralPath $signature -PathType Leaf)){
 Refuse 'Original locally held ECC-GPG key could not sign exact candidate'
}
$home=Join-Path $env:TEMP ('cog-r3r1-sig-public-'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $home -ErrorAction Stop |Out-Null
try{
 $null=@(& $GpgExecutable --homedir $home --batch --no-tty --no-auto-key-retrieve --import $TrustedPublicKeyFile 2>&1)
 if($LASTEXITCODE -ne 0){Refuse 'External trusted GPG public key unreadable'}
 $listing=@(& $GpgExecutable --homedir $home --batch --no-tty --with-colons --fingerprint --list-keys 2>&1)
 if($LASTEXITCODE -ne 0){Refuse 'Isolated public signer list failed'}
 $primary=@()
 $following=$false
 foreach($line in $listing){
  $parts=([string]$line).Split(':')
  if($parts[0] -ceq 'pub'){$following=$true;continue}
  if($parts[0] -ceq 'sub'){$following=$false;continue}
  if($parts[0] -ceq 'fpr' -and $following){
   $primary+=([string]$parts[9]).ToUpperInvariant()
   $following=$false
  }
 }
 if($primary.Count -ne 1 -or $primary[0] -cne $fp){
  Refuse 'Independent primary public owner GPG fingerprint does not match'
 }
 $verified=@(& $GpgExecutable --homedir $home --batch --no-tty --no-auto-key-retrieve --status-fd 1 --verify $signature $manifest 2>&1)
 if($LASTEXITCODE -ne 0 -or
    @($verified|Where-Object{([string]$_) -match '^\[GNUPG:\] VALIDSIG '}).Count -ne 1){
  Refuse 'Exact original owner detached signature failed public verification'
 }
}finally{
 Remove-Item -LiteralPath $home -Recurse -Force -WhatIf:$false -ErrorAction Stop
}
if((Get-FileHash -LiteralPath $manifest -Algorithm SHA256).Hash.ToLowerInvariant() -cne
   $ApprovedCandidateManifestSha256){Refuse 'GPG signing modified original reviewed bytes'}
[pscustomobject]@{
 schema='cognitum.ssm.r3r1.protected_owner_gpg_release.v1'
 status='PASS_OWNER_GPG_PROTECTED_CANDIDATE_SIGNED_NO_INSTALL'
 exact_source_sha=$ExactSourceSha
 reviewed_candidate_manifest_sha256=$ApprovedCandidateManifestSha256
 owner_gpg_primary_fingerprint=$fp
 independent_reviewer_approval_cryptographically_verified=$false
 physically_installed_protected_worker=$false
 preexisting_production_CNG_signer_accepted=$false
 external_antirollback_freshness_verified=$false
 original_Lu_Core_operation_grant_verified=$false
 output_or_ACK_authorized=$false
}|ConvertTo-Json -Compress
