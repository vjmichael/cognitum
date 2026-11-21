# R3-R1 signed Windows carrier build. Externally approved certificate REQUIRED.
# No self-issued certificate, CI fixture, Core grants, CNG key or output release.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$ExactSourceSha,
 [Parameter(Mandatory=$true)][string]$RuntimeSourceRoot,
 [Parameter(Mandatory=$true)][string]$ApprovedRuntimeManifestSha256,
 [Parameter(Mandatory=$true)][string]$ApprovedRuntimeProvenanceSha256,
 [Parameter(Mandatory=$true)][string]$ApprovedSignerCertificateSha256,
 [Parameter(Mandatory=$true)][string]$ApprovedSignerThumbprint,
 [Parameter(Mandatory=$true)][ValidateSet('LocalMachine','CurrentUser')][string]$SignerStore,
 [Parameter(Mandatory=$true)][string]$ProtectedStageRoot,
 [Parameter(Mandatory=$true)][string]$MakensisExecutable,
 [Parameter(Mandatory=$true)][string]$SignToolExecutable
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function Refuse([string]$why){throw ("COG_R3R1_SIGNED_BUILD_REFUSED: "+$why)}
if($env:OS -cne 'Windows_NT'){Refuse 'Genuine Windows required'}
foreach($h in @($ApprovedRuntimeManifestSha256,$ApprovedRuntimeProvenanceSha256,$ApprovedSignerCertificateSha256)){
 if($h -cnotmatch '^[0-9a-f]{64}$' -or $h -ceq ('0'*64)){Refuse 'External SHA256 release pins missing'}
}
if($ExactSourceSha -cnotmatch '^[0-9a-f]{40}$' -or $ApprovedSignerThumbprint -cnotmatch '^[0-9a-f]{40}$'){
 Refuse 'Exact source commit and approved publisher thumbprint required'
}
foreach($p in @($RuntimeSourceRoot,$ProtectedStageRoot,$MakensisExecutable,$SignToolExecutable)){
 if(-not [IO.Path]::IsPathRooted($p)){Refuse 'All original source, stage and signing paths must be absolute'}
}
foreach($p in @($MakensisExecutable,$SignToolExecutable)){
 if(-not(Test-Path -LiteralPath $p -PathType Leaf)){Refuse 'Original signing/NSIS toolchain missing'}
}
$source=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$revision=(& git.exe -C $source rev-parse HEAD)
if($LASTEXITCODE -ne 0 -or $revision -cne $ExactSourceSha){
 Refuse 'Exact original Git source revision is not selected'
}
$dirty=@(& git.exe -C $source status --porcelain --untracked-files=no)
if($LASTEXITCODE -ne 0 -or $dirty.Count -gt 0){Refuse 'Original tracked release source is modified'}
$certPath='Cert:\'+$SignerStore+'\My\'+$ApprovedSignerThumbprint
$cert=Get-Item -LiteralPath $certPath -ErrorAction Stop
if(-not $cert.HasPrivateKey -or (Get-Date) -lt $cert.NotBefore -or (Get-Date) -ge $cert.NotAfter){
 Refuse 'Approved code-signing private key is unavailable, inactive or expired'
}
$certSha=([Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($cert.RawData))).ToLowerInvariant()
if($certSha -cne $ApprovedSignerCertificateSha256){Refuse 'Signer cert does not match approved SHA256'}
if(@($cert.EnhancedKeyUsageList|Where-Object{$_.ObjectId -eq '1.3.6.1.5.5.7.3.3'}).Count -eq 0){
 Refuse 'Signer lacks code-signing EKU'
}
$stage=[IO.Path]::GetFullPath($ProtectedStageRoot).TrimEnd('\')
$trusted=@('S-1-5-18','S-1-5-32-544')
$writeMask=[int64]0x500D0156L
$cursor=$stage
while($true){
 $item=Get-Item -LiteralPath $cursor -Force -ErrorAction Stop
 if(($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){Refuse 'Protected staging reparse ancestor'}
 $acl=Get-Acl -LiteralPath $cursor
 try{$owner=$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value}
 catch{Refuse 'Protected staging owner unavailable'}
 if($trusted -cnotcontains $owner){Refuse 'Staging not SYSTEM/Administrators owned'}
 foreach($ace in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])){
  if($ace.AccessControlType -eq [Security.AccessControl.AccessControlType]::Allow -and
     (([int64]$ace.FileSystemRights -band $writeMask) -ne 0) -and
     $trusted -cnotcontains $ace.IdentityReference.Value){Refuse 'Staging writable by unapproved principal'}
 }
 $parent=[IO.Directory]::GetParent($cursor)
 if($null -eq $parent){break}
 $cursor=$parent.FullName
}
$runtime=[IO.Path]::GetFullPath($RuntimeSourceRoot).TrimEnd('\')
if(-not(Test-Path -LiteralPath $runtime -PathType Container)){Refuse 'Pinned frozen runtime source missing'}
$manifest=Join-Path $runtime 'r3-r1-runtime.manifest'
$provFile=Join-Path $runtime 'r3-r1-runtime-provenance.json'
foreach($p in @($manifest,$provFile)){
 if(-not(Test-Path -LiteralPath $p -PathType Leaf)){Refuse 'Frozen manifest/provenance file absent'}
}
$manifestSha=(Get-FileHash -LiteralPath $manifest -Algorithm SHA256).Hash.ToLowerInvariant()
$provSha=(Get-FileHash -LiteralPath $provFile -Algorithm SHA256).Hash.ToLowerInvariant()
if($manifestSha -cne $ApprovedRuntimeManifestSha256 -or $provSha -cne $ApprovedRuntimeProvenanceSha256){
 Refuse 'Original runtime manifest or provenance not independently pinned'
}
try{$prov=Get-Content -LiteralPath $provFile -Raw|ConvertFrom-Json}
catch{Refuse 'Frozen runtime provenance malformed'}
if($prov.schema -cne 'cognitum.ssm.r3r1.production_installer_runtime.v1' -or
   $prov.runtime_manifest_sha256 -cne $manifestSha){
 Refuse 'Test-only or mismatched runtime cannot be signed as production'
}
# Rehash every import; require a closed inventory, not merely a pinned manifest.
$raw=[IO.File]::ReadAllBytes($manifest)
if($raw.Length -eq 0 -or $raw.Length -gt 3145728){Refuse 'Bounded frozen package manifest required'}
foreach($b in $raw){
 if($b -ne 9 -and $b -ne 10 -and ($b -lt 32 -or $b -gt 126)){
  Refuse 'Noncanonical manifest byte'
 }
}
$expected=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
$last=''
$total=[long]0
foreach($line in ([Text.Encoding]::ASCII.GetString($raw)).Split([char]10)){
 if(-not $line){continue}
 $match=[regex]::Match($line,'^([0-9a-f]{64})\t([ -~]+)$')
 if(-not $match.Success){Refuse 'Frozen import record invalid'}
 $rel=$match.Groups[2].Value
 if($rel.StartsWith('/') -or $rel.Contains('\') -or
    $rel.Split('/') -contains '..' -or $rel.Split('/') -contains '.' -or
    $rel.IndexOfAny([char[]]@(':','*','?','"','<','>','|')) -ge 0 -or
    [String]::CompareOrdinal($rel,$last) -le 0 -or -not $expected.Add($rel)){
  Refuse 'Unsafe, duplicate or unsorted release import path'
 }
 $last=$rel
 $path=Join-Path $runtime ($rel.Replace('/','\'))
 if(-not(Test-Path -LiteralPath $path -PathType Leaf)){Refuse 'Frozen import missing'}
 $item=Get-Item -LiteralPath $path -Force
 if(($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or $item.Length -gt 67108864){
  Refuse 'Symlinked or oversized frozen import'
 }
 $total+=$item.Length
 if($total -gt 1468006400 -or $expected.Count -gt 12000){Refuse 'Full runtime bounds exceeded'}
 if((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $match.Groups[1].Value){
  Refuse 'Frozen import hash mismatch'
 }
}
if($expected.Count -eq 0){Refuse 'Frozen runtime empty'}
$files=@(Get-ChildItem -LiteralPath $runtime -Recurse -Force -File)
if($files.Count -ne $expected.Count+2){Refuse 'Unlisted runtime source file'}
foreach($item in Get-ChildItem -LiteralPath $runtime -Recurse -Force){
 if(($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
  Refuse 'Unlisted runtime reparse point'
 }
}
$stageName='r3r1-'+$ExactSourceSha.Substring(0,16)
$out=Join-Path $stage $stageName
if(Test-Path -LiteralPath $out){Refuse 'Existing staged release cannot be overwritten'}
New-Item -ItemType Directory -Path $out -ErrorAction Stop|Out-Null
$payload=Join-Path $out 'payload'
New-Item -ItemType Directory -Path $payload -ErrorAction Stop|Out-Null
$manifestPath=Join-Path $source 'native/windows_scm_production/Cargo.toml'
& cargo.exe build --manifest-path $manifestPath --release --locked --offline
if($LASTEXITCODE -ne 0){Refuse 'Production-only SCM source compilation failed'}
$built=Join-Path $source 'native/windows_scm_production/target/release/cognitum-scm-production.exe'
if(-not(Test-Path -LiteralPath $built -PathType Leaf)){Refuse 'Separate no-worker production executable unavailable'}
$exe=Join-Path $payload 'cognitum-scm-production.exe'
Copy-Item -LiteralPath $built -Destination $exe -ErrorAction Stop
Copy-Item -LiteralPath $runtime -Destination (Join-Path $payload 'runtime') -Recurse -ErrorAction Stop
# Reconcile the actual copied bytes before signing or packaging.
$copiedRuntime=Join-Path $payload 'runtime'
$copiedFiles=@(Get-ChildItem -LiteralPath $copiedRuntime -Recurse -Force -File)
if($copiedFiles.Count -ne $expected.Count+2){Refuse 'Copied release payload is not the reviewed full file inventory'}
if((Get-FileHash -LiteralPath (Join-Path $copiedRuntime 'r3-r1-runtime.manifest') -Algorithm SHA256).Hash.ToLowerInvariant() -cne $manifestSha -or
   (Get-FileHash -LiteralPath (Join-Path $copiedRuntime 'r3-r1-runtime-provenance.json') -Algorithm SHA256).Hash.ToLowerInvariant() -cne $provSha){
 Refuse 'Original frozen runtime manifest or provenance changed during staging'
}
foreach($rel in $expected){
 $file=Join-Path $copiedRuntime ($rel.Replace('/','\'))
 if(-not(Test-Path -LiteralPath $file -PathType Leaf)){Refuse 'Original copied runtime file absent'}
 $orig=Join-Path $runtime ($rel.Replace('/','\'))
 if((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -cne
    (Get-FileHash -LiteralPath $orig -Algorithm SHA256).Hash.ToLowerInvariant()){
  Refuse 'Copied signed-release runtime differs from original pinned import'
 }
}
$signArgs=@('sign','/fd','SHA256','/sha1',$ApprovedSignerThumbprint,'/s','My')
if($SignerStore -ceq 'LocalMachine'){$signArgs+='/sm'}
& $SignToolExecutable @signArgs $exe | Out-Null
if($LASTEXITCODE -ne 0){Refuse 'Original production executable Authenticode signing failed'}
$installer=Join-Path $out 'Cognitum-SSM-R3R1-Bootstrap.exe'
$nsi=Join-Path $source 'deployment/windows/cognitum-ssm-bootstrap.nsi'
& $MakensisExecutable '/V2' ('/DCOG_PAYLOAD_DIR='+$payload) ('/DCOG_OUTPUT_FILE='+$installer) $nsi|Out-Null
if($LASTEXITCODE -ne 0){Refuse 'Exact original NSIS carrier build failed'}
& $SignToolExecutable @signArgs $installer|Out-Null
if($LASTEXITCODE -ne 0){Refuse 'Original NSIS carrier Authenticode signing failed'}
foreach($file in @($exe,$installer)){
 $signed=Get-AuthenticodeSignature -LiteralPath $file
 if($signed.Status -ne [Management.Automation.SignatureStatus]::Valid -or
    $null -eq $signed.SignerCertificate -or
    $signed.SignatureType -ne [Management.Automation.SignatureType]::Authenticode){
  Refuse 'Signed release candidate Authenticode invalid'
 }
 $actual=([Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($signed.SignerCertificate.RawData))).ToLowerInvariant()
 if($actual -cne $certSha){Refuse 'Original signed artifact differs from approved publisher'}
}
$receipt=[ordered]@{
 schema='cognitum.ssm.r3r1.signed_release_candidate.v1'
 exact_source_sha=$ExactSourceSha
 signer_certificate_sha256=$certSha
 signed_installer_sha256=(Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
 signed_service_sha256=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()
 runtime_manifest_sha256=$manifestSha
 runtime_provenance_sha256=$provSha
 independently_approved_release=$false
 physically_installed_accepted=$false
 real_Core_grant_verified=$false
 production_CNG_receipts_verified=$false
 output_release_authorized=$false
}
[IO.File]::WriteAllText((Join-Path $out 'release-candidate.json'),($receipt|ConvertTo-Json -Compress)+[char]10,[Text.Encoding]::ASCII)
$receipt|ConvertTo-Json -Compress
