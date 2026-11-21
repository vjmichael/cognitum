# R3-R1 READ-ONLY externally pinned installed frozen-runtime integrity gate.
# Never creates/enrolls/starts workers, authorizes Core, signs or releases data.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$ApprovedInstallRoot,
 [Parameter(Mandatory=$true)][string]$RuntimeRoot,
 [Parameter(Mandatory=$true)][string]$ApprovedManifestSha256,
 [Parameter(Mandatory=$true)][string]$ApprovedProvenanceSha256
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function Refuse([string]$why){throw ("COG_R3R1_INSTALLED_RUNTIME_REFUSED: "+$why)}
if($env:OS -ne 'Windows_NT'){Refuse 'Actual Windows required'}
foreach($pin in @($ApprovedManifestSha256,$ApprovedProvenanceSha256)){
 if($pin -cnotmatch '^[0-9a-f]{64}$' -or $pin -ceq ('0'*64)){
  Refuse 'Independent nonzero lowercase SHA256 pin required'
 }
}
if(-not [IO.Path]::IsPathRooted($ApprovedInstallRoot) -or
   -not [IO.Path]::IsPathRooted($RuntimeRoot)){Refuse 'Absolute installed roots required'}
$root=[IO.Path]::GetFullPath($ApprovedInstallRoot).TrimEnd('\')
$runtime=[IO.Path]::GetFullPath($RuntimeRoot).TrimEnd('\')
if(-not $runtime.StartsWith(($root+'\'),[StringComparison]::OrdinalIgnoreCase)){
 Refuse 'Frozen runtime outside independently approved installation'
}
if(-not (Test-Path -LiteralPath $root -PathType Container) -or
   -not (Test-Path -LiteralPath $runtime -PathType Container)){
 Refuse 'Original signed installation/runtime directories missing'
}
$trusted=@('S-1-5-18','S-1-5-32-544')
$writeMask=[int64]0x500D0156L
function Assert-Custody([string]$path){
 $item=Get-Item -LiteralPath $path -Force -ErrorAction Stop
 if(($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
  Refuse 'Installed runtime reparse-point traversal'
 }
 $acl=Get-Acl -LiteralPath $path -ErrorAction Stop
 try{$owner=$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value}
 catch{Refuse 'Installed runtime file ownership unresolvable'}
 if($trusted -cnotcontains $owner){Refuse 'Installed runtime owner is not SYSTEM/Administrators'}
 foreach($ace in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])){
  $mask=[int64]$ace.FileSystemRights
  if($ace.AccessControlType -eq [Security.AccessControl.AccessControlType]::Allow -and
     (($mask -band $writeMask) -ne 0) -and
     $trusted -cnotcontains $ace.IdentityReference.Value){
   Refuse 'Untrusted principal can alter installed runtime'
  }
 }
}
$cursor=$runtime
while($true){
 Assert-Custody $cursor
 if($cursor.Equals($root,[StringComparison]::OrdinalIgnoreCase)){break}
 $parent=[IO.Directory]::GetParent($cursor)
 if($null -eq $parent){Refuse 'Runtime escaped installed root'}
 $cursor=$parent.FullName.TrimEnd('\')
}
$manifest=Join-Path $runtime 'r3-r1-runtime.manifest'
$provenance=Join-Path $runtime 'r3-r1-runtime-provenance.json'
foreach($path in @($manifest,$provenance)){
 if(-not (Test-Path -LiteralPath $path -PathType Leaf)){
  Refuse 'Externally pinned manifest/provenance absent'
 }
 Assert-Custody $path
}
$manifestInfo=Get-Item -LiteralPath $manifest
if($manifestInfo.Length -lt 1 -or $manifestInfo.Length -gt 3145728){
 Refuse 'Bounded original manifest required'
}
$raw=[IO.File]::ReadAllBytes($manifest)
if(([Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($raw))).ToLowerInvariant() -cne
   $ApprovedManifestSha256){Refuse 'Runtime manifest differs from independent pin'}
if((Get-FileHash -LiteralPath $provenance -Algorithm SHA256).Hash.ToLowerInvariant() -cne
   $ApprovedProvenanceSha256){Refuse 'Runtime provenance differs from independent pin'}
try{$report=Get-Content -LiteralPath $provenance -Raw|ConvertFrom-Json}
catch{Refuse 'Runtime provenance invalid'}
if($report.schema -cne 'cognitum.ssm.r3r1.production_installer_runtime.v1' -or
   $report.runtime_manifest_sha256 -cne $ApprovedManifestSha256){
 Refuse 'CI-only or mismatched provenance cannot identify installed runtime'
}
foreach($b in $raw){
 if($b -ne 9 -and $b -ne 10 -and ($b -lt 32 -or $b -gt 126)){
  Refuse 'Non-ASCII/control/CR in installed runtime manifest'
 }
}
$text=[Text.Encoding]::ASCII.GetString($raw)
if(-not $text.EndsWith([string][char]10,[StringComparison]::Ordinal)){
 Refuse 'Installed runtime manifest missing canonical LF'
}
$lines=$text.Split([char]10)
$expected=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
$last=''
$count=0
[long]$total=0
foreach($line in $lines){
 if($line.Length -eq 0){continue}
 $m=[regex]::Match($line,'^([0-9a-f]{64})\t([ -~]+)$')
 if(-not $m.Success){Refuse 'Noncanonical runtime manifest line'}
 $digest=$m.Groups[1].Value
 $rel=$m.Groups[2].Value
 if($rel.StartsWith('/') -or $rel.Contains('\') -or
    $rel.IndexOfAny([char[]]@(':','*','?','"','<','>','|')) -ge 0 -or
    [String]::CompareOrdinal($rel,$last) -le 0){
  Refuse 'Unsorted, absolute or invalid frozen dependency path'
 }
 $parts=$rel.Split('/')
 if(@($parts|Where-Object{$_ -in @('','.', '..') -or $_.EndsWith(' ') -or $_.EndsWith('.')}).Count -gt 0){
  Refuse 'Noncanonical runtime path'
 }
 if($rel -in @('r3-r1-runtime.manifest','r3-r1-runtime-provenance.json') -or
    -not $expected.Add($rel)){Refuse 'Duplicate or self-hashed runtime path'}
 $last=$rel
 $count++
 if($count -gt 12000){Refuse 'Frozen import count exceeded'}
 $file=Join-Path $runtime ($rel.Replace('/','\'))
 if(-not (Test-Path -LiteralPath $file -PathType Leaf)){
  Refuse 'Original installed import missing'
 }
 Assert-Custody $file
 $info=Get-Item -LiteralPath $file -Force
 if($info.Length -gt 67108864){Refuse 'Dependency file size exceeded'}
 $total+=$info.Length
 if($total -gt 1468006400){Refuse 'Full-runtime byte budget exceeded'}
 if((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -cne $digest){
  Refuse 'Installed DLL/Python import digest mismatch'
 }
}
if($count -eq 0){Refuse 'Empty installed code manifest'}
$actual=0
foreach($item in Get-ChildItem -LiteralPath $runtime -Force -Recurse){
 if(($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
  Refuse 'Unmanifested runtime reparse point'
 }
 if($item.PSIsContainer){
  Assert-Custody $item.FullName
  continue
 }
 $actual++
 if($actual -gt 12002){Refuse 'Additional runtime files exceed budget'}
 $relative=$item.FullName.Substring($runtime.Length+1).Replace('\','/')
 if($relative -in @('r3-r1-runtime.manifest','r3-r1-runtime-provenance.json')){continue}
 if(-not $expected.Contains($relative)){Refuse 'Unmanifested executable or import'}
}
if($actual -ne $count+2){Refuse 'Installed inventory differs from frozen manifest'}
[pscustomobject]@{
 schema='cognitum.ssm.r3r1.installed_runtime_readonly_audit.v1'
 status='PASS_INSTALLED_RUNTIME_DIGEST_ACL_OBSERVATION_ONLY'
 original_file_count=$count
 original_total_bytes=$total
 manifest_sha256=$ApprovedManifestSha256
 provenance_sha256=$ApprovedProvenanceSha256
 production_installer_verified=$false
 nonadmin_AppContainer_execution_verified=$false
 original_Core_grant_verified=$false
 independent_CNG_receipts_verified=$false
 output_release_authorized=$false
}|ConvertTo-Json -Compress
