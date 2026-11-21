# Cognitum R3-R1: verify an independent *detached* release approval signature.
# Authentication of an approval RECORD alone is never installed acceptance,
# a legal attestation, an original Core operation grant or an output authority.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$ApprovalJson,
 [Parameter(Mandatory=$true)][string]$DetachedSignatureP7s,
 [Parameter(Mandatory=$true)][string]$ApprovedReleaseAuthorityCertificateSha256,
 [Parameter(Mandatory=$true)][string]$ApprovedPublisherCertificateSha256,
 [Parameter(Mandatory=$true)][string]$ExpectedSourceSha
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function Refuse([string]$why){throw ('COG_R3R1_APPROVAL_REFUSED: '+$why)}
if($env:OS -cne 'Windows_NT'){Refuse 'Native Windows cryptographic approval required'}
foreach($pin in @($ApprovedReleaseAuthorityCertificateSha256,$ApprovedPublisherCertificateSha256)){
 if($pin -cnotmatch '^[0-9a-f]{64}$' -or $pin -ceq ('0'*64)){Refuse 'Independent nonzero lowercase certificate pins required'}
}
if($ApprovedReleaseAuthorityCertificateSha256 -ceq $ApprovedPublisherCertificateSha256){
 Refuse 'Release approver must differ cryptographically from publisher'
}
if($ExpectedSourceSha -cnotmatch '^[0-9a-f]{40}$'){Refuse 'External exact source commit SHA required'}
foreach($p in @($ApprovalJson,$DetachedSignatureP7s)){
 if(-not [IO.Path]::IsPathRooted($p) -or -not (Test-Path -LiteralPath $p -PathType Leaf)){
  Refuse 'Original absolute detached signed approval files required'
 }
 if(((Get-Item -LiteralPath $p -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
  Refuse 'Detached approval file may not be a reparse point'
 }
}
$approvalBytes=[IO.File]::ReadAllBytes([IO.Path]::GetFullPath($ApprovalJson))
$signatureBytes=[IO.File]::ReadAllBytes([IO.Path]::GetFullPath($DetachedSignatureP7s))
if($approvalBytes.Length -lt 100 -or $approvalBytes.Length -gt 16384 -or
   $signatureBytes.Length -lt 128 -or $signatureBytes.Length -gt 32768){
 Refuse 'Bounded original approval and detached signature bytes required'
}
if(([Text.Encoding]::UTF8.GetString($approvalBytes).Contains([char]0))){
 Refuse 'Approval includes invalid control bytes'
}
try{
 $content=[Security.Cryptography.Pkcs.ContentInfo]::new([byte[]]$approvalBytes)
 $cms=[Security.Cryptography.Pkcs.SignedCms]::new($content,$true)
 $cms.Decode([byte[]]$signatureBytes)
 if(-not $cms.Detached -or $cms.SignerInfos.Count -ne 1){
  Refuse 'Exactly one detached original release approver required'
 }
 $cms.CheckSignature($true) # Crypto + external exact pin; chain is separate.
}catch{Refuse 'Original detached CMS cryptographic signature invalid'}
$signer=$cms.SignerInfos[0].Certificate
if($null -eq $signer){Refuse 'Original release approver certificate unavailable'}
$actualCert=([Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($signer.RawData))).ToLowerInvariant()
if($actualCert -cne $ApprovedReleaseAuthorityCertificateSha256){
 Refuse 'Detached signer does not match independent release authority pin'
}
if($cms.SignerInfos[0].DigestAlgorithm.Value -cne '2.16.840.1.101.3.4.2.1'){
 Refuse 'Detached release authority must use SHA256 digest'
}
try{$a=([Text.Encoding]::UTF8.GetString($approvalBytes)|ConvertFrom-Json -AsHashtable)}
catch{Refuse 'Signed independent approval is not valid JSON'}
$keys=@('schema','exact_source_sha','signed_installer_sha256',
        'signed_service_sha256','runtime_manifest_sha256',
        'runtime_provenance_sha256','publisher_certificate_sha256',
        'permits_Core_grant','permits_output_release')
if(@($a.Keys).Count -ne $keys.Count){Refuse 'Independent approval contains unexpected/missing fields'}
foreach($key in $keys){if(-not $a.Contains($key)){Refuse 'Original signed approval field absent'}}
if($a.schema -cne 'cognitum.ssm.r3r1.independent_release_approval.v1' -or
   $a.exact_source_sha -cne $ExpectedSourceSha -or
   $a.publisher_certificate_sha256 -cne $ApprovedPublisherCertificateSha256 -or
   $a.permits_Core_grant -cne $false -or
   $a.permits_output_release -cne $false){
 Refuse 'Independent approval schema/source/publisher or authorization scope invalid'
}
foreach($key in @('signed_installer_sha256','signed_service_sha256',
                  'runtime_manifest_sha256','runtime_provenance_sha256')){
 $pin=$a[$key]
 if($pin -isnot [string] -or $pin -cnotmatch '^[0-9a-f]{64}$' -or $pin -ceq ('0'*64)){
  Refuse ('External signed '+$key+' release pin invalid')
 }
}
[pscustomobject]@{
 schema='cognitum.ssm.r3r1.detached_release_approval_readonly.v1'
 status='PASS_DETACHED_APPROVAL_CRYPTOGRAPHIC_IDENTITY_OBSERVATION_ONLY'
 exact_source_sha=$a.exact_source_sha
 signed_installer_sha256=$a.signed_installer_sha256
 signed_service_sha256=$a.signed_service_sha256
 runtime_manifest_sha256=$a.runtime_manifest_sha256
 runtime_provenance_sha256=$a.runtime_provenance_sha256
 publisher_certificate_sha256=$a.publisher_certificate_sha256
 release_authority_certificate_sha256=$actualCert
 independently_approved_organization_policy_verified=$false
 original_Core_grant_verified=$false
 physically_installed_accepted=$false
 output_release_authorized=$false
}|ConvertTo-Json -Compress
