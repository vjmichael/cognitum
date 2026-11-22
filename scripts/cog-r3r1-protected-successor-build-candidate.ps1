# R3-R1 protected successor CANDIDATE only: no signer, installer execution,
# service registration, Core authorization, CNG provisioning, or output.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$ExactSourceSha,
 [Parameter(Mandatory=$true)][string]$ApprovedRuntimeRoot,
 [Parameter(Mandatory=$true)][string]$ApprovedRuntimeManifestSha256,
 [Parameter(Mandatory=$true)][string]$ApprovedRuntimeProvenanceSha256,
 [Parameter(Mandatory=$true)][string]$ProtectedStageRoot,
 [Parameter(Mandatory=$true)][string]$ApprovedOwnerGpgPrimaryFingerprint,
 [Parameter(Mandatory=$true)][string]$ExistingCngKeyName,
 [Parameter(Mandatory=$true)][string]$ApprovedCngPublicBlobSha256,
 [Parameter(Mandatory=$true)][string]$ApprovedAntirollbackPublicSha256,
 [Parameter(Mandatory=$true)][string]$ApprovedLuIssuerPublicSha256,
 [Parameter(Mandatory=$true)][string]$MakeNsisExecutable
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function Refuse([string]$why){throw ('COG_R3R1_PROTECTED_CANDIDATE_REFUSED: '+$why)}
if($env:OS -cne 'Windows_NT' -or $env:CI -eq 'true' -or $env:GITHUB_ACTIONS -eq 'true' -or
   -not [Environment]::Is64BitProcess){Refuse 'Original physical x64 Windows build required'}
if($ExactSourceSha -cnotmatch '^[0-9a-f]{40}$' -or
   $ExactSourceSha -ceq '8c45869214255fc91af53e88e0bfaff6b943696c'){
 Refuse 'New reviewed exact-source protected successor required'
}
$source=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$head=@(& git.exe -C $source rev-parse HEAD)
if($LASTEXITCODE -ne 0 -or $head.Count -ne 1 -or $head[0] -cne $ExactSourceSha){
 Refuse 'Original build checkout does not equal reviewed Git source'
}
$dirty=@(& git.exe -C $source status --porcelain --untracked-files=no)
if($LASTEXITCODE -ne 0 -or $dirty.Count -ne 0){Refuse 'Tracked original source not clean'}
foreach($p in @($ApprovedRuntimeRoot,$ProtectedStageRoot,$MakeNsisExecutable)){
 if(-not [IO.Path]::IsPathRooted($p)){Refuse 'Absolute reviewed frozen input/tool/stage required'}
}
$runtime=[IO.Path]::GetFullPath($ApprovedRuntimeRoot).TrimEnd('\')
$stage=[IO.Path]::GetFullPath($ProtectedStageRoot).TrimEnd('\')
if(-not (Test-Path -LiteralPath $runtime -PathType Container) -or
   -not (Test-Path -LiteralPath $stage -PathType Container) -or
   -not (Test-Path -LiteralPath $MakeNsisExecutable -PathType Leaf)){
 Refuse 'Approved runtime, protected stage or NSIS unavailable'
}
$acl=Get-Acl -LiteralPath $stage -ErrorAction Stop
$trusted=@('S-1-5-18','S-1-5-32-544')
if($trusted -cnotcontains $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -or
   -not $acl.AreAccessRulesProtected){
 Refuse 'Protected source stage must be SYSTEM/Administrators owned without inheritance'
}
$writeMask=[int64]0x500D0156L
foreach($ace in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])){
 if($ace.AccessControlType -eq [Security.AccessControl.AccessControlType]::Allow -and
    ([int64]$ace.FileSystemRights -band $writeMask) -ne 0 -and
    $trusted -cnotcontains $ace.IdentityReference.Value){
  Refuse 'Source release stage permits untrusted modification'
 }
}
function Digest([string]$path){(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}
$manifest=Join-Path $runtime 'r3-r1-runtime.manifest'
$provenance=Join-Path $runtime 'r3-r1-runtime-provenance.json'
if((Digest $manifest) -cne $ApprovedRuntimeManifestSha256 -or
   (Digest $provenance) -cne $ApprovedRuntimeProvenanceSha256){
 Refuse 'Original reviewed full frozen import source disagrees with external SHA256'
}
$p=Get-Content -LiteralPath $provenance -Raw|ConvertFrom-Json
if($p.schema -cne 'cognitum.ssm.r3r1.production_installer_runtime.v1' -or
   $p.original_production_source_sha -cne $ExactSourceSha -or
   $p.external_manifest_approved_for_production -ne $true -or
   $p.runtime_manifest_sha256 -cne $ApprovedRuntimeManifestSha256){
 Refuse 'CI-only frozen runtime or incorrect production source'
}
$out=Join-Path $stage ('r3r1-protected-'+$ExactSourceSha.Substring(0,16))
if(Test-Path -LiteralPath $out){Refuse 'Existing candidate never overwritten'}
New-Item -ItemType Directory -Path $out -ErrorAction Stop|Out-Null
$payload=Join-Path $out 'payload'
New-Item -ItemType Directory -Path $payload -ErrorAction Stop|Out-Null
& cargo.exe build --manifest-path (Join-Path $source 'native/windows_scm_production/Cargo.toml') --release --locked --offline --no-default-features --features protected-ssm-production
if($LASTEXITCODE -ne 0){Refuse 'Native distinct protected SCM compilation failed'}
$built=Join-Path $source 'native/windows_scm_production/target/release/cognitum-scm-production.exe'
$exe=Join-Path $payload 'cognitum-scm-production.exe'
Copy-Item -LiteralPath $built -Destination $exe -ErrorAction Stop
Copy-Item -LiteralPath $runtime -Destination (Join-Path $payload 'runtime') -Recurse -ErrorAction Stop
$nsis=Join-Path $out 'Cognitum-SSM-R3R1-Protected.exe'
$defines=@('/V2',('/DCOG_PAYLOAD_DIR='+$payload),('/DCOG_OUTPUT_FILE='+$nsis))
& $MakeNsisExecutable @defines (Join-Path $source 'deployment/windows/cognitum-ssm-protected-successor.nsi') |Out-Null
if($LASTEXITCODE -ne 0 -or -not(Test-Path -LiteralPath $nsis -PathType Leaf)){
 Refuse 'NSIS protected successor carrier compilation failed'
}
$python=Join-Path $payload 'runtime\python.exe'
$argv=@(
 (Join-Path $PSScriptRoot 'cog_r3r1_protected_successor_candidate.py'),
 'candidate','--stage',$out,'--source-sha',$ExactSourceSha,
 '--owner-fingerprint',$ApprovedOwnerGpgPrimaryFingerprint.ToUpperInvariant(),
 '--runtime-manifest',$ApprovedRuntimeManifestSha256,
 '--runtime-provenance',$ApprovedRuntimeProvenanceSha256,
 '--cng-key-name',$ExistingCngKeyName,
 '--cng-public',$ApprovedCngPublicBlobSha256,
 '--antirollback-public',$ApprovedAntirollbackPublicSha256,
 '--lu-issuer-public',$ApprovedLuIssuerPublicSha256
)
& $python -I -B @argv
if($LASTEXITCODE -ne 0){Refuse 'Closed byte-for-byte successor manifest refused'}
