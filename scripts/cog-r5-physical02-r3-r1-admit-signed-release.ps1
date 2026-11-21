# Cognitum R3-R1 read-only staged signed-release admission.
# Requires separate cryptographic release-approver identity from publisher.
# NEVER installs files, starts SCM, provisions CNG or grants Lu operations.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$ReleaseRoot,
 [Parameter(Mandatory=$true)][string]$ApprovalJson,
 [Parameter(Mandatory=$true)][string]$DetachedSignatureP7s,
 [Parameter(Mandatory=$true)][string]$ApprovedReleaseAuthorityCertificateSha256,
 [Parameter(Mandatory=$true)][string]$ApprovedPublisherCertificateSha256,
 [Parameter(Mandatory=$true)][string]$ExpectedSourceSha
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function Refuse([string]$why){throw ('COG_R3R1_SIGNED_ADMISSION_REFUSED: '+$why)}
if($env:OS -cne 'Windows_NT'){Refuse 'Native Windows required'}
if($env:GITHUB_ACTIONS -eq 'true'){Refuse 'Hosted CI cannot admit independently signed production'}
if($ExpectedSourceSha -cnotmatch '^[0-9a-f]{40}$'){Refuse 'External full source SHA required'}
if(-not [IO.Path]::IsPathRooted($ReleaseRoot)){Refuse 'Protected original release root must be absolute'}
$root=[IO.Path]::GetFullPath($ReleaseRoot).TrimEnd('\')
if(-not(Test-Path -LiteralPath $root -PathType Container)){Refuse 'Original release staging absent'}
$installer=Join-Path $root 'Cognitum-SSM-R3R1-Bootstrap.exe'
$payload=Join-Path $root 'payload'
$exe=Join-Path $payload 'cognitum-scm-production.exe'
$runtime=Join-Path $payload 'runtime'
$receiptFile=Join-Path $root 'release-candidate.json'
foreach($path in @($installer,$exe,$receiptFile)){
 if(-not(Test-Path -LiteralPath $path -PathType Leaf)){Refuse 'Original signed build artifact or receipt missing'}
}
$trusted=@('S-1-5-18','S-1-5-32-544')
$writeMask=[int64]0x500D0156L
function Check-ProtectedAncestry([string]$path){
 $cursor=[IO.Path]::GetFullPath($path)
 while($true){
  $item=Get-Item -LiteralPath $cursor -Force
  if(($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){Refuse 'Signed staged release reparse path'}
  $acl=Get-Acl -LiteralPath $cursor
  try{$owner=$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value}
  catch{Refuse 'Unresolvable original staged release owner'}
  if($trusted -cnotcontains $owner){Refuse 'Original staged release not SYSTEM/Administrators owned'}
  foreach($ace in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])){
   if($ace.AccessControlType -eq [Security.AccessControl.AccessControlType]::Allow -and
      (([int64]$ace.FileSystemRights -band $writeMask) -ne 0) -and
      $trusted -cnotcontains $ace.IdentityReference.Value){
    Refuse 'Untrusted staged release ancestor write access'
   }
  }
  $parent=[IO.Directory]::GetParent($cursor)
  if($null -eq $parent){break}
  $cursor=$parent.FullName
 }
}
foreach($path in @($root,$installer,$payload,$exe,$receiptFile)){
 Check-ProtectedAncestry $path
}
$approve=Join-Path $PSScriptRoot 'cog-r5-physical02-r3-r1-verify-detached-approval.ps1'
$pkgGate=Join-Path $PSScriptRoot 'cog-r5-physical02-r3-r1-signed-installer.ps1'
$runtimeGate=Join-Path $PSScriptRoot 'cog-r5-physical02-r3-r1-runtime-audit.ps1'
foreach($script in @($approve,$pkgGate,$runtimeGate)){
 if(-not(Test-Path -LiteralPath $script -PathType Leaf)){Refuse 'Original reviewed admission implementation missing'}
}
$approvalRaw=& $approve -ApprovalJson $ApprovalJson -DetachedSignatureP7s $DetachedSignatureP7s -ApprovedReleaseAuthorityCertificateSha256 $ApprovedReleaseAuthorityCertificateSha256 -ApprovedPublisherCertificateSha256 $ApprovedPublisherCertificateSha256 -ExpectedSourceSha $ExpectedSourceSha
if(-not $approvalRaw){Refuse 'Original signed independent release approval absent'}
$a=($approvalRaw|Out-String)|ConvertFrom-Json
if($a.schema -cne 'cognitum.ssm.r3r1.detached_release_approval_readonly.v1' -or
   $a.status -cne 'PASS_DETACHED_APPROVAL_CRYPTOGRAPHIC_IDENTITY_OBSERVATION_ONLY' -or
   $a.output_release_authorized -ne $false){
 Refuse 'Detached approval not independently verified'
}
try{$receipt=Get-Content -LiteralPath $receiptFile -Raw|ConvertFrom-Json}
catch{Refuse 'Original signed candidate receipt invalid'}
if($receipt.schema -cne 'cognitum.ssm.r3r1.signed_release_candidate.v1' -or
   $receipt.exact_source_sha -cne $ExpectedSourceSha -or
   $receipt.signer_certificate_sha256 -cne $ApprovedPublisherCertificateSha256 -or
   $receipt.independently_approved_release -ne $false -or
   $receipt.physically_installed_accepted -ne $false -or
   $receipt.real_Core_grant_verified -ne $false -or
   $receipt.production_CNG_receipts_verified -ne $false -or
   $receipt.output_release_authorized -ne $false){
 Refuse 'Release candidate receipt falsely claims production authority or wrong source'
}
$pins=@{
 signed_installer_sha256=(Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
 signed_service_sha256=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()
 runtime_manifest_sha256=(Get-FileHash -LiteralPath (Join-Path $runtime 'r3-r1-runtime.manifest') -Algorithm SHA256).Hash.ToLowerInvariant()
 runtime_provenance_sha256=(Get-FileHash -LiteralPath (Join-Path $runtime 'r3-r1-runtime-provenance.json') -Algorithm SHA256).Hash.ToLowerInvariant()
}
foreach($key in $pins.Keys){
 if($pins[$key] -cne $a.$key -or $pins[$key] -cne $receipt.$key){
  Refuse ('Original release candidate, independent approval and bytes disagree: '+$key)
 }
}
$originalPkg=& $pkgGate -SignedInstallerPackage $installer -ApprovedInstallerSha256 $pins.signed_installer_sha256 -ApprovedSignerCertificateSha256 $ApprovedPublisherCertificateSha256
if(-not $originalPkg){Refuse 'Original Authenticode package gate absent'}
$pkg=($originalPkg|Out-String)|ConvertFrom-Json
if($pkg.status -cne 'PASS_SIGNED_STAGED_INSTALLER_IDENTITY_OBSERVATION_ONLY'){
 Refuse 'Approved Authenticode installer identity not verified'
}
$exeSig=Get-AuthenticodeSignature -LiteralPath $exe
if($null -eq $exeSig -or
   $exeSig.Status -ne [Management.Automation.SignatureStatus]::Valid -or
   $exeSig.SignatureType -ne [Management.Automation.SignatureType]::Authenticode -or
   $null -eq $exeSig.SignerCertificate){
 Refuse 'Original staged production SCM image lacks valid embedded Authenticode'
}
$exePublisher=([Convert]::ToHexString([Security.Cryptography.SHA256]::HashData(
 $exeSig.SignerCertificate.RawData))).ToLowerInvariant()
if($exePublisher -cne $ApprovedPublisherCertificateSha256){
 Refuse 'Staged production SCM image signer differs from independent approved publisher'
}
$r=& $runtimeGate -ApprovedInstallRoot $payload -RuntimeRoot $runtime -ApprovedManifestSha256 $pins.runtime_manifest_sha256 -ApprovedProvenanceSha256 $pins.runtime_provenance_sha256
if(-not $r){Refuse 'Full frozen runtime independent hash/ACL verification absent'}
$runtimeClaim=($r|Out-String)|ConvertFrom-Json
if($runtimeClaim.status -cne 'PASS_INSTALLED_RUNTIME_DIGEST_ACL_OBSERVATION_ONLY' -or
   $runtimeClaim.output_release_authorized -ne $false){
 Refuse 'Original frozen production imports not independently verified'
}
$afterInstaller=(Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
$afterExe=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()
if($afterInstaller -cne $pins.signed_installer_sha256 -or
   $afterExe -cne $pins.signed_service_sha256){
 Refuse 'Signed release bytes changed during independent observation'
}
[pscustomobject]@{
 schema='cognitum.ssm.r3r1.staged_signed_release_approval_audit.v1'
 status='PASS_SIGNED_RELEASE_AND_DETACHED_APPROVAL_OBSERVATION_ONLY'
 exact_source_sha=$ExpectedSourceSha
 signed_installer_sha256=$pins.signed_installer_sha256
 signed_service_sha256=$pins.signed_service_sha256
 runtime_manifest_sha256=$pins.runtime_manifest_sha256
 runtime_provenance_sha256=$pins.runtime_provenance_sha256
 publisher_certificate_sha256=$ApprovedPublisherCertificateSha256
 release_authority_certificate_sha256=$ApprovedReleaseAuthorityCertificateSha256
 legal_publisher_approval_independently_attested=$false
 installed_SCM_verified=$false
 production_CNG_signer_verified=$false
 original_Lu_Core_grant_verified=$false
 physical_full_installed_acceptance=$false
 output_release_or_ACK_authorized=$false
}|ConvertTo-Json -Compress
