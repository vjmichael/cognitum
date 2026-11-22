# R3-R1 personal Windows GPG release builder. Never creates Authenticode
# signatures, never exports private keys, never grants SSM/Core authority.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$ExactSourceSha,
 [Parameter(Mandatory=$true)][string]$ApprovedRuntimeRoot,
 [Parameter(Mandatory=$true)][string]$ApprovedRuntimeManifestSha256,
 [Parameter(Mandatory=$true)][string]$ApprovedRuntimeProvenanceSha256,
 [Parameter(Mandatory=$true)][string]$GpgPrimaryFingerprint,
 [Parameter(Mandatory=$true)][string]$TrustedPublicKeyFile,
 [Parameter(Mandatory=$true)][string]$GpgExecutable,
 [Parameter(Mandatory=$true)][string]$MakeNsisExecutable,
 [Parameter(Mandatory=$true)][string]$ProtectedStageRoot
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function Refuse([string]$reason){throw ('COG_R3R1_PRIVATE_GPG_BUILD_REFUSED: '+$reason)}
if($env:OS -cne 'Windows_NT' -or $env:GITHUB_ACTIONS -eq 'true' -or $env:CI -eq 'true'){
 Refuse 'Original Windows personal signing host required, not hosted CI'
}
if(-not [Environment]::Is64BitProcess){Refuse '64-bit Windows original host required'}
if($ExactSourceSha -cnotmatch '^[0-9a-f]{40}$' -or
   $GpgPrimaryFingerprint -cnotmatch '^([0-9A-Fa-f]{40}|[0-9A-Fa-f]{64})$'){
 Refuse 'External exact Git source and complete GPG primary fingerprint required'
}
$fp=$GpgPrimaryFingerprint.ToUpperInvariant()
foreach($hash in @($ApprovedRuntimeManifestSha256,$ApprovedRuntimeProvenanceSha256)){
 if($hash -cnotmatch '^[0-9a-f]{64}$' -or $hash -ceq ('0'*64)){
  Refuse 'Externally reviewed original frozen-runtime SHA256 pins required'
 }
}
foreach($p in @($ApprovedRuntimeRoot,$TrustedPublicKeyFile,$GpgExecutable,
                $MakeNsisExecutable,$ProtectedStageRoot)){
 if(-not [IO.Path]::IsPathRooted($p)){Refuse 'Absolute original paths required'}
}
foreach($p in @($TrustedPublicKeyFile,$GpgExecutable,$MakeNsisExecutable)){
 if(-not(Test-Path -LiteralPath $p -PathType Leaf)){Refuse 'GPG public key/CLI or NSIS compiler absent'}
}
# Git-for-Windows GnuPG uses MSYS POSIX file arguments.
$isMsysGpg=$GpgExecutable -match '(?i)\\Git\\(usr|mingw64)\\bin\\gpg\.exe$'
$cygpath=if($isMsysGpg){Join-Path (Split-Path $GpgExecutable -Parent) 'cygpath.exe'}else{''}
if($isMsysGpg -and -not(Test-Path -LiteralPath $cygpath -PathType Leaf)){
 Refuse 'Git GPG requires original cygpath.exe'
}
function Gpg-Path([string]$path){
 if(-not $isMsysGpg){return $path}
 $translated=@(& $cygpath -u $path)
 if($LASTEXITCODE -ne 0 -or $translated.Count -ne 1){Refuse 'Original GPG path conversion failed'}
 [string]$translated[0]
}
$stage=[IO.Path]::GetFullPath($ProtectedStageRoot).TrimEnd('\')
if(-not(Test-Path -LiteralPath $stage -PathType Container)){Refuse 'Original protected staging directory absent'}
$trusted=@('S-1-5-18','S-1-5-32-544')
$writeMask=[int64]0x500D0156L
$cursor=$stage
while($true){
 $item=Get-Item -LiteralPath $cursor -Force
 if(($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){Refuse 'Release staging reparse path'}
 $acl=Get-Acl -LiteralPath $cursor
 $owner=$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value
 if($trusted -cnotcontains $owner){Refuse 'Release staging requires SYSTEM/Administrators ownership'}
 foreach($ace in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])){
  if($ace.AccessControlType -eq [Security.AccessControl.AccessControlType]::Allow -and
     (([int64]$ace.FileSystemRights -band $writeMask) -ne 0) -and
     $trusted -cnotcontains $ace.IdentityReference.Value){
   Refuse 'Release staging writable by untrusted account'
  }
 }
 $parent=[IO.Directory]::GetParent($cursor)
 if($null -eq $parent){break}
 $cursor=$parent.FullName
}
$source=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$git=@(& git.exe -C $source rev-parse HEAD)
if($LASTEXITCODE -ne 0 -or $git.Count -ne 1 -or $git[0] -cne $ExactSourceSha){
 Refuse 'Wrong selected original source revision'
}
$dirty=@(& git.exe -C $source status --porcelain --untracked-files=no)
if($LASTEXITCODE -ne 0 -or $dirty.Count -ne 0){Refuse 'Tracked source tree modified'}
$runtime=[IO.Path]::GetFullPath($ApprovedRuntimeRoot).TrimEnd('\')
$manifest=Join-Path $runtime 'r3-r1-runtime.manifest'
$provFile=Join-Path $runtime 'r3-r1-runtime-provenance.json'
foreach($p in @($manifest,$provFile)){
 if(-not(Test-Path -LiteralPath $p -PathType Leaf)){Refuse 'Fresh approved production runtime missing'}
}
if((Get-FileHash -LiteralPath $manifest -Algorithm SHA256).Hash.ToLowerInvariant() -cne $ApprovedRuntimeManifestSha256 -or
   (Get-FileHash -LiteralPath $provFile -Algorithm SHA256).Hash.ToLowerInvariant() -cne $ApprovedRuntimeProvenanceSha256){
 Refuse 'Original reviewed runtime differs from externally approved digest'
}
$prov=Get-Content -LiteralPath $provFile -Raw|ConvertFrom-Json
if($prov.schema -cne 'cognitum.ssm.r3r1.production_installer_runtime.v1' -or
   $prov.original_production_source_sha -cne $ExactSourceSha -or
   $prov.external_manifest_approved_for_production -ne $true -or
   $prov.runtime_manifest_sha256 -cne $ApprovedRuntimeManifestSha256){
 Refuse 'CI fixture, unapproved, or mismatched source runtime refused'
}
$raw=[IO.File]::ReadAllBytes($manifest)
if($raw.Length -lt 1 -or $raw.Length -gt 3145728){Refuse 'Unbounded original frozen manifest'}
$entries=@([Text.Encoding]::ASCII.GetString($raw).Split([char]10) | Where-Object {$_})
if($entries.Count -gt 12000){Refuse 'Frozen runtime import count exceeds bound'}
$expected=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
$prior=''
foreach($line in $entries){
 $m=[regex]::Match($line,'^([0-9a-f]{64})\t([ -~]+)$')
 if(-not $m.Success){Refuse 'Noncanonical original import manifest'}
 $rel=$m.Groups[2].Value
 if([String]::CompareOrdinal($rel,$prior) -le 0 -or $rel.StartsWith('/') -or
    $rel.Contains('\') -or $rel.Split('/') -contains '..' -or
    $rel.IndexOfAny([char[]]@(':','*','?','"','<','>','|')) -ge 0 -or
    -not $expected.Add($rel)){Refuse 'Unsafe original frozen runtime import'}
 $orig=Join-Path $runtime ($rel.Replace('/','\'))
 if(-not(Test-Path -LiteralPath $orig -PathType Leaf) -or
    (Get-FileHash -LiteralPath $orig -Algorithm SHA256).Hash.ToLowerInvariant() -cne $m.Groups[1].Value){
  Refuse 'Original reviewed import altered'
 }
 $prior=$rel
}
if(@(Get-ChildItem -LiteralPath $runtime -Recurse -Force -File).Count -ne $expected.Count+2){
 Refuse 'Unlisted frozen import in release source'
}
$secrets=@(& $GpgExecutable --batch --with-colons --fingerprint --list-secret-keys $fp 2>&1)
if($LASTEXITCODE -ne 0 -or -not (($secrets -join [char]10).ToUpperInvariant().Contains($fp))){
 Refuse 'Original owner GPG private signing key unavailable on selected machine'
}
$out=Join-Path $stage ('r3r1-private-'+$ExactSourceSha.Substring(0,16))
if(Test-Path -LiteralPath $out){Refuse 'Existing staged release cannot be overwritten'}
New-Item -ItemType Directory -Path $out -ErrorAction Stop|Out-Null
$payload=Join-Path $out 'payload'
New-Item -ItemType Directory -Path $payload -ErrorAction Stop|Out-Null
& cargo.exe build --manifest-path (Join-Path $source 'native/windows_scm_production/Cargo.toml') --release --locked --offline
if($LASTEXITCODE -ne 0){Refuse 'Original production SCM native build failed'}
$built=Join-Path $source 'native/windows_scm_production/target/release/cognitum-scm-production.exe'
if(-not(Test-Path -LiteralPath $built -PathType Leaf)){Refuse 'Production no-worker SCM image missing'}
$exe=Join-Path $payload 'cognitum-scm-production.exe'
Copy-Item -LiteralPath $built -Destination $exe -ErrorAction Stop
Copy-Item -LiteralPath $runtime -Destination (Join-Path $payload 'runtime') -Recurse -ErrorAction Stop
$copiedRuntime=Join-Path $payload 'runtime'
if((Get-FileHash -LiteralPath (Join-Path $copiedRuntime 'r3-r1-runtime.manifest') -Algorithm SHA256).Hash.ToLowerInvariant() -cne $ApprovedRuntimeManifestSha256 -or
   (Get-FileHash -LiteralPath (Join-Path $copiedRuntime 'r3-r1-runtime-provenance.json') -Algorithm SHA256).Hash.ToLowerInvariant() -cne $ApprovedRuntimeProvenanceSha256){
 Refuse 'Staged full runtime manifest/provenance mutated'
}
foreach($rel in $expected){
 $original=Join-Path $runtime ($rel.Replace('/','\'))
 $copy=Join-Path $copiedRuntime ($rel.Replace('/','\'))
 if(-not(Test-Path -LiteralPath $copy -PathType Leaf) -or
    (Get-FileHash -LiteralPath $copy -Algorithm SHA256).Hash.ToLowerInvariant() -cne
      (Get-FileHash -LiteralPath $original -Algorithm SHA256).Hash.ToLowerInvariant()){
  Refuse 'Staged original import differs from reviewed source'
 }
}
$installer=Join-Path $out 'Cognitum-SSM-R3R1-Bootstrap.exe'
& $MakeNsisExecutable '/V2' ('/DCOG_PAYLOAD_DIR='+$payload) ('/DCOG_OUTPUT_FILE='+$installer) (Join-Path $source 'deployment/windows/cognitum-ssm-bootstrap.nsi')|Out-Null
if($LASTEXITCODE -ne 0 -or -not(Test-Path -LiteralPath $installer -PathType Leaf)){
 Refuse 'Private NSIS package creation failed'
}
if((Get-AuthenticodeSignature -LiteralPath $installer).Status -ne [Management.Automation.SignatureStatus]::NotSigned){
 Refuse 'GPG private lane may not assume Windows Authenticode publisher signature'
}
$record=[ordered]@{
 schema='cognitum.ssm.r3r1.private_gpg_release.v1'
 lane='personal_local_only'
 exact_source_sha=$ExactSourceSha
 gpg_primary_fingerprint=$fp
 installer_sha256=(Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
 service_sha256=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()
 runtime_manifest_sha256=$ApprovedRuntimeManifestSha256
 runtime_provenance_sha256=$ApprovedRuntimeProvenanceSha256
 permits_core_grant=$false
 permits_output_release=$false
}
$recordFile=Join-Path $out 'private-release.json'
[IO.File]::WriteAllText($recordFile,($record|ConvertTo-Json -Compress)+[char]10,[Text.Encoding]::ASCII)
$signature=Join-Path $out 'private-release.json.asc'
& $GpgExecutable --batch --no-tty --armor --local-user $fp --output (Gpg-Path $signature) --detach-sign (Gpg-Path $recordFile)
if($LASTEXITCODE -ne 0){Refuse 'Original local GPG private-key signing failed'}
$gate=Join-Path $PSScriptRoot 'cog-r5-physical02-r3-r1-private-gpg-verify.ps1'
$verifiedRaw=& $gate -ReleaseRoot $out -TrustedPublicKeyFile $TrustedPublicKeyFile -ExpectedPrimaryFingerprint $fp -ExpectedSourceSha $ExactSourceSha -GpgExecutable $GpgExecutable
$verified=($verifiedRaw|Out-String)|ConvertFrom-Json
if($verified.status -cne 'PASS_PRIVATE_GPG_PACKAGE_DIGESTS_OBSERVATION_ONLY' -or
   $verified.output_release_or_ACK_authorized -ne $false){
 Refuse 'Original detached private release signature re-verification failed'
}
[pscustomobject]@{
 schema='cognitum.ssm.r3r1.private_gpg_release_candidate.v1'
 status='PASS_PRIVATE_GPG_RELEASE_PACKAGE_SIGNED_OBSERVATION_ONLY'
 exact_source_sha=$ExactSourceSha
 original_gpg_primary_fingerprint=$fp
 installer_sha256=$record.installer_sha256
 service_sha256=$record.service_sha256
 physical_windows_installed_accepted=$false
 production_worker_verified=$false
 core_grant_verified=$false
 output_release_or_ACK_authorized=$false
}|ConvertTo-Json -Compress
