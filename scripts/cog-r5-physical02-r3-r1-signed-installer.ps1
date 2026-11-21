# R3-R1 read-only Windows release PACKAGE authenticity gate.
# A signed installer must already be staged under administrator-owned custody.
# Never sign, generate credentials, execute installer, create service or ACK.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$SignedInstallerPackage,
 [Parameter(Mandatory=$true)][string]$ApprovedInstallerSha256,
 [Parameter(Mandatory=$true)][string]$ApprovedSignerCertificateSha256
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function Refuse([string]$reason){throw ("COG_R3R1_SIGNED_PACKAGE_REFUSED: "+$reason)}
if($env:OS -ne 'Windows_NT'){Refuse 'Native Windows Authenticode required'}
foreach($pin in @($ApprovedInstallerSha256,$ApprovedSignerCertificateSha256)){
 if($pin -cnotmatch '^[0-9a-f]{64}$' -or $pin -ceq ('0'*64)){
  Refuse 'Independently approved exact nonzero lowercase SHA256 pin missing'
 }
}
if(-not [IO.Path]::IsPathRooted($SignedInstallerPackage)){
 Refuse 'Pinned installed release artifact must use absolute path'
}
$installer=[IO.Path]::GetFullPath($SignedInstallerPackage)
$extension=[IO.Path]::GetExtension($installer)
if($extension -notin @('.exe','.msi')){Refuse 'Only independently signed EXE/MSI release containers accepted'}
if(-not (Test-Path -LiteralPath $installer -PathType Leaf)){Refuse 'Original approved package unavailable'}
$trusted=@('S-1-5-18','S-1-5-32-544')
$writeMask=[int64]0x500D0156L
$cursor=$installer
while($true){
 $item=Get-Item -LiteralPath $cursor -Force -ErrorAction Stop
 if(($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
  Refuse 'Signed installer path traverses reparse point'
 }
 $acl=Get-Acl -LiteralPath $cursor -ErrorAction Stop
 try{$owner=$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value}
 catch{Refuse 'Signed installer owner cannot be independently identified'}
 if($trusted -cnotcontains $owner){
  Refuse 'Release staging ancestry is not administrator/system owned'
 }
 foreach($ace in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])){
  if($ace.AccessControlType -eq [Security.AccessControl.AccessControlType]::Allow -and
     (([int64]$ace.FileSystemRights -band $writeMask) -ne 0) -and
     $trusted -cnotcontains $ace.IdentityReference.Value){
   Refuse 'Untrusted user can alter signed package or staging ancestry'
  }
 }
 $next=[IO.Directory]::GetParent($cursor)
 if($null -eq $next){break}
 $cursor=$next.FullName
}
$item=Get-Item -LiteralPath $installer -Force
if($item.Length -lt 1024 -or $item.Length -gt 2147483648){
 Refuse 'Signed release package size outside fixed budget'
}
$first=(Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
if($first -cne $ApprovedInstallerSha256){
 Refuse 'Release package bytes differ from independent publisher approval'
}
$signature=Get-AuthenticodeSignature -LiteralPath $installer
if($null -eq $signature -or
   $signature.Status -ne [Management.Automation.SignatureStatus]::Valid -or
   $signature.SignatureType -ne [Management.Automation.SignatureType]::Authenticode -or
   $null -eq $signature.SignerCertificate){
 Refuse 'Approved embedded Authenticode signer is absent/invalid'
}
$certsha=([Convert]::ToHexString([Security.Cryptography.SHA256]::HashData(
 $signature.SignerCertificate.RawData))).ToLowerInvariant()
if($certsha -cne $ApprovedSignerCertificateSha256){
 Refuse 'Embedded publisher certificate does not match independent approval'
}
$last=(Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
if($last -cne $first){Refuse 'Signed release package mutated during observation'}
[pscustomobject]@{
 schema='cognitum.ssm.r3r1.signed_installer_identity_readonly.v1'
 status='PASS_SIGNED_STAGED_INSTALLER_IDENTITY_OBSERVATION_ONLY'
 release_package_sha256=$first
 approved_publisher_certificate_sha256=$certsha
 verified_installed_package_contents=$false
 original_Core_grant_verified=$false
 production_worker_receipts_verified=$false
 output_release_authorized=$false
}|ConvertTo-Json -Compress
