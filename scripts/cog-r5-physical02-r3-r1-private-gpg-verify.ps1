# R3-R1 personal/private GPG release — READ ONLY, no Windows Authenticode.
# Trust anchor is a user's independently checked primary GPG fingerprint, not
# an untrusted field in the signed record or the key file alone.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$ReleaseRoot,
 [Parameter(Mandatory=$true)][string]$TrustedPublicKeyFile,
 [Parameter(Mandatory=$true)][string]$ExpectedPrimaryFingerprint,
 [Parameter(Mandatory=$true)][string]$ExpectedSourceSha,
 [Parameter(Mandatory=$true)][string]$GpgExecutable
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function Refuse([string]$why){throw ('COG_R3R1_PRIVATE_GPG_REFUSED: '+$why)}
if($env:OS -cne 'Windows_NT'){Refuse 'Original Windows GPG release gate required'}
if($ExpectedPrimaryFingerprint -cnotmatch '^([0-9A-Fa-f]{40}|[0-9A-Fa-f]{64})$' -or
   $ExpectedSourceSha -cnotmatch '^[0-9a-f]{40}$'){
 Refuse 'Externally checked complete GPG fingerprint and exact Git SHA required'
}
$expectedFp=$ExpectedPrimaryFingerprint.ToUpperInvariant()
foreach($p in @($ReleaseRoot,$TrustedPublicKeyFile,$GpgExecutable)){
 if(-not [IO.Path]::IsPathRooted($p)){Refuse 'Original absolute release/key/tool paths required'}
}
if(-not (Test-Path -LiteralPath $TrustedPublicKeyFile -PathType Leaf) -or
   -not (Test-Path -LiteralPath $GpgExecutable -PathType Leaf) -or
   -not (Test-Path -LiteralPath $ReleaseRoot -PathType Container)){
 Refuse 'Original public verification material or staged release unavailable'
}
$root=[IO.Path]::GetFullPath($ReleaseRoot).TrimEnd('\')
$release=Join-Path $root 'private-release.json'
$sig=Join-Path $root 'private-release.json.asc'
$installer=Join-Path $root 'Cognitum-SSM-R3R1-Bootstrap.exe'
$exe=Join-Path $root 'payload\cognitum-scm-production.exe'
$runtime=Join-Path $root 'payload\runtime'
$manifest=Join-Path $runtime 'r3-r1-runtime.manifest'
$provenance=Join-Path $runtime 'r3-r1-runtime-provenance.json'
foreach($p in @($release,$sig,$installer,$exe,$manifest,$provenance)){
 if(-not (Test-Path -LiteralPath $p -PathType Leaf)){Refuse 'Original complete private release input missing'}
 if(((Get-Item -LiteralPath $p -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
  Refuse 'Private release must not contain redirecting file links'
 }
}
if((Get-Item -LiteralPath $release).Length -gt 8192 -or
   (Get-Item -LiteralPath $sig).Length -gt 16384 -or
   (Get-Item -LiteralPath $TrustedPublicKeyFile).Length -gt 65536){
 Refuse 'Unbounded original private signed manifest/public key input'
}
# Git-for-Windows GnuPG is an MSYS executable; Gpg4win is native Windows.
$isMsysGpg=$GpgExecutable -match '(?i)\\Git\\(usr|mingw64)\\bin\\gpg\.exe$'
$cygpath=if($isMsysGpg){Join-Path (Split-Path $GpgExecutable -Parent) 'cygpath.exe'}else{''}
if($isMsysGpg -and -not(Test-Path -LiteralPath $cygpath -PathType Leaf)){
 Refuse 'Original Git GPG cygpath path translator missing'
}
function Gpg-Path([string]$path){
 if(-not $isMsysGpg){return $path}
 $converted=@(& $cygpath -u $path)
 if($LASTEXITCODE -ne 0 -or $converted.Count -ne 1){Refuse 'Original GPG file path translation unavailable'}
 [string]$converted[0]
}
# Isolate public-key verification: never allow a default keyring, keyserver or
# TOFU trust state to choose an identity. GPG validates cryptography; the
# independent expected fingerprint identifies the owner's authorized key.
$verifyHome=Join-Path $env:TEMP ('cog-r3r1-gpg-verify-'+[Guid]::NewGuid().ToString('N'))
$gpgHomeArg=Gpg-Path $verifyHome
$publicArg=Gpg-Path $TrustedPublicKeyFile
$sigArg=Gpg-Path $sig
$releaseArg=Gpg-Path $release
New-Item -ItemType Directory -Path $verifyHome -ErrorAction Stop|Out-Null
try{
 $oldExit=$null
 $importLines=@(& $GpgExecutable --homedir $gpgHomeArg --batch --no-tty --no-auto-key-retrieve --import $publicArg 2>&1)
 if($LASTEXITCODE -ne 0){Refuse 'Cannot import original trusted public GPG identity'}
 $listed=@(& $GpgExecutable --homedir $gpgHomeArg --batch --no-tty --with-colons --fingerprint --list-keys 2>&1)
 if($LASTEXITCODE -ne 0){Refuse 'Independent public GPG fingerprint inventory unavailable'}
 $primaries=@()
 $primaryFollowing=$false
 foreach($line in $listed){
  $fields=([string]$line).Split(':')
  if($fields[0] -eq 'pub'){$primaryFollowing=$true;continue}
  if($fields[0] -eq 'sub'){$primaryFollowing=$false;continue}
  if($fields[0] -eq 'fpr' -and $primaryFollowing){
   $primaries+=([string]$fields[9]).ToUpperInvariant()
   $primaryFollowing=$false
  }
 }
 if($primaries.Count -ne 1 -or $primaries[0] -cne $expectedFp){
  Refuse 'Imported public GPG identity differs from exact externally pinned owner'
 }
 $result=@(& $GpgExecutable --homedir $gpgHomeArg --batch --no-tty --no-auto-key-retrieve --status-fd 1 --verify $sigArg $releaseArg 2>&1)
 if($LASTEXITCODE -ne 0){Refuse 'Original detached release GPG signature invalid'}
 $valid=@($result | Where-Object { ([string]$_) -match '^\[GNUPG:\] VALIDSIG ' })
 if($valid.Count -ne 1){Refuse 'Exactly one valid original GPG release signature required'}
 $tokens=([string]$valid[0]).Split(' ',[StringSplitOptions]::RemoveEmptyEntries)
 if($tokens.Count -lt 3){Refuse 'Original GPG verified identity unparseable'}
 $signingFp=$tokens[2].ToUpperInvariant()
 # GnuPG provides the primary fingerprint at the end when a subkey signs.
 $primaryFp=if($tokens.Count -ge 12 -and $tokens[-1] -match '^([0-9A-Fa-f]{40}|[0-9A-Fa-f]{64})$'){$tokens[-1].ToUpperInvariant()}else{$signingFp}
 if($primaryFp -cne $expectedFp){Refuse 'Original GPG signer differs from externally approved primary key'}
}finally{
 Remove-Item -LiteralPath $verifyHome -Force -Recurse -ErrorAction Stop
}
try{$r=Get-Content -LiteralPath $release -Raw|ConvertFrom-Json -AsHashtable}
catch{Refuse 'Signed personal release manifest JSON invalid'}
$keys=@('schema','lane','exact_source_sha','gpg_primary_fingerprint',
 'installer_sha256','service_sha256','runtime_manifest_sha256',
 'runtime_provenance_sha256','permits_core_grant','permits_output_release')
if($r.Count -ne $keys.Count){Refuse 'Unexpected/missing signed private release fields'}
foreach($key in $keys){if(-not $r.Contains($key)){Refuse 'Signed private release field absent'}}
if($r.schema -cne 'cognitum.ssm.r3r1.private_gpg_release.v1' -or
   $r.lane -cne 'personal_local_only' -or
   $r.exact_source_sha -cne $ExpectedSourceSha -or
   $r.gpg_primary_fingerprint -cne $expectedFp -or
   $r.permits_core_grant -cne $false -or
   $r.permits_output_release -cne $false){
 Refuse 'Signed private release source, key or authorization bounds invalid'
}
$actual=@{
 installer_sha256=(Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
 service_sha256=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()
 runtime_manifest_sha256=(Get-FileHash -LiteralPath $manifest -Algorithm SHA256).Hash.ToLowerInvariant()
 runtime_provenance_sha256=(Get-FileHash -LiteralPath $provenance -Algorithm SHA256).Hash.ToLowerInvariant()
}
foreach($key in $actual.Keys){
 if($r[$key] -isnot [string] -or $r[$key] -cne $actual[$key]){
  Refuse ('Tampered/mismatched signed private artifact: '+$key)
 }
}
try{$prov=Get-Content -LiteralPath $provenance -Raw|ConvertFrom-Json}
catch{Refuse 'Original runtime provenance invalid'}
if($prov.schema -cne 'cognitum.ssm.r3r1.production_installer_runtime.v1' -or
   $prov.runtime_manifest_sha256 -cne $actual.runtime_manifest_sha256 -or
   $prov.original_production_source_sha -cne $ExpectedSourceSha -or
   $prov.external_manifest_approved_for_production -ne $true){
 Refuse 'Test-only runtime or original source pin cannot enter private release'
}
# A detached signature over the runtime manifest does not itself authenticate
# staged import bytes. Close the actual shipped runtime over the signed
# manifest before allowing the package to be accepted for physical use.
$manifestBytes=[IO.File]::ReadAllBytes($manifest)
if($manifestBytes.Length -lt 1 -or $manifestBytes.Length -gt 3145728){
 Refuse 'Original runtime manifest exceeds the bounded release inventory'
}
foreach($byte in $manifestBytes){
 if($byte -gt 126 -or ($byte -lt 32 -and $byte -ne 9 -and $byte -ne 10)){
  Refuse 'Noncanonical original runtime manifest encoding'
 }
}
$manifestText=[Text.Encoding]::ASCII.GetString($manifestBytes)
if(-not $manifestText.EndsWith([string][char]10)){Refuse 'Original runtime manifest lacks canonical LF termination'}
$manifestLines=@($manifestText.Substring(0,$manifestText.Length-1).Split([char]10))
if($manifestLines.Count -lt 1 -or $manifestLines.Count -gt 12000){
 Refuse 'Original runtime manifest entry count outside release bounds'
}
$expectedImports=[Collections.Generic.Dictionary[string,string]]::new([StringComparer]::OrdinalIgnoreCase)
$previous=''
foreach($line in $manifestLines){
 $match=[regex]::Match($line,'^([0-9a-f]{64})\t([ -~]+)
 status='PASS_PRIVATE_GPG_PACKAGE_DIGESTS_OBSERVATION_ONLY'
 exact_source_sha=$ExpectedSourceSha
 gpg_primary_fingerprint=$expectedFp
 installer_sha256=$actual.installer_sha256
 service_sha256=$actual.service_sha256
 runtime_manifest_sha256=$actual.runtime_manifest_sha256
 runtime_provenance_sha256=$actual.runtime_provenance_sha256
 windows_authenticode_required=$false
 physical_windows_installed_accepted=$false
 protected_worker_verified=$false
 core_grant_verified=$false
 output_release_or_ACK_authorized=$false
}|ConvertTo-Json -Compress
)
 if(-not $match.Success){Refuse 'Noncanonical original runtime manifest entry'}
 $relative=$match.Groups[2].Value
 $segments=@($relative.Split('/'))
 $badParts=@($segments|Where-Object{$_ -eq '' -or $_ -eq '.' -or $_ -eq '..'})
 if([string]::CompareOrdinal($relative,$previous) -le 0 -or
    $relative.StartsWith('/') -or $relative.Contains('\') -or
    $relative.IndexOfAny([char[]]@(':','*','?','"','<','>','|')) -ge 0 -or
    $badParts.Count -ne 0 -or
    $relative -in @('r3-r1-runtime.manifest','r3-r1-runtime-provenance.json') -or
    $expectedImports.ContainsKey($relative)){
  Refuse 'Unsafe, duplicate or out-of-order original runtime import path'
 }
 $expectedImports.Add($relative,$match.Groups[1].Value)
 $previous=$relative
}
foreach($dir in @($root,(Join-Path $root 'payload'),$runtime)){
 $directory=Get-Item -LiteralPath $dir -Force
 if(-not $directory.PSIsContainer -or
    ($directory.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
  Refuse 'Redirecting release or runtime root'
 }
}
$children=@(Get-ChildItem -LiteralPath $runtime -Recurse -Force -ErrorAction Stop)
if($children.Count -gt 24000){Refuse 'Unbounded shipped runtime directory inventory'}
$shippedFiles=@($children|Where-Object{-not $_.PSIsContainer})
if($shippedFiles.Count -ne $expectedImports.Count+2){
 Refuse 'Missing or unlisted files in shipped original runtime'
}
foreach($entry in $children){
 if(($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
  Refuse 'Redirecting staged original runtime import or directory'
 }
 if($entry.PSIsContainer){continue}
 if(-not $entry.FullName.StartsWith($runtime+'\',[StringComparison]::OrdinalIgnoreCase)){
  Refuse 'Staged original runtime escaped package root'
 }
 $relative=$entry.FullName.Substring($runtime.Length+1).Replace('\','/')
 if($relative -in @('r3-r1-runtime.manifest','r3-r1-runtime-provenance.json')){
  continue
 }
 if(-not $expectedImports.ContainsKey($relative)){
  Refuse 'Unlisted staged original runtime import'
 }
 $actualImportSha=(Get-FileHash -LiteralPath $entry.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
 if($actualImportSha -cne $expectedImports[$relative]){
  Refuse 'Tampered staged original runtime import'
 }
}
[pscustomobject]@{
 schema='cognitum.ssm.r3r1.private_gpg_release_verified.v1'
 status='PASS_PRIVATE_GPG_PACKAGE_DIGESTS_OBSERVATION_ONLY'
 exact_source_sha=$ExpectedSourceSha
 gpg_primary_fingerprint=$expectedFp
 installer_sha256=$actual.installer_sha256
 service_sha256=$actual.service_sha256
 runtime_manifest_sha256=$actual.runtime_manifest_sha256
 runtime_provenance_sha256=$actual.runtime_provenance_sha256
 windows_authenticode_required=$false
 physical_windows_installed_accepted=$false
 protected_worker_verified=$false
 core_grant_verified=$false
 output_release_or_ACK_authorized=$false
}|ConvertTo-Json -Compress
