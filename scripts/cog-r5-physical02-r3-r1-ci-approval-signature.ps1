# Disposable hosted-Windows ONLY detached-approval verifier test.
# The ephemeral CI certificate is NOT an independently approved release key,
# and this test NEVER signs a Windows executable or production installer.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$ExactSourceSha)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($env:OS -cne 'Windows_NT' -or $env:GITHUB_ACTIONS -cne 'true' -or
   $env:RUNNER_OS -cne 'Windows'){
 throw 'COG_R3R1_CI_APPROVAL_REFUSED: disposable Windows runner required'
}
if($ExactSourceSha -cnotmatch '^[0-9a-f]{40}$'){throw 'CI exact Git source missing'}
$dir=Join-Path $env:RUNNER_TEMP ('cog-r3r1-approval-'+$env:GITHUB_RUN_ID)
if(Test-Path -LiteralPath $dir){throw 'Reused CI approval test path'}
New-Item -ItemType Directory -Path $dir|Out-Null
$cert=$null
try{
 $cert=New-SelfSignedCertificate -Subject 'CN=Cognitum R3R1 CI-only CMS verifier test' -CertStoreLocation 'Cert:\CurrentUser\My' -Type CodeSigningCert -KeyExportPolicy NonExportable -KeyAlgorithm RSA -KeyLength 2048 -NotAfter (Get-Date).AddDays(1) -ErrorAction Stop
 if($null -eq $cert -or -not $cert.HasPrivateKey){throw 'CI-only ephemeral CMS key creation failed'}
 $certSha=([Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($cert.RawData))).ToLowerInvariant()
 $publisher=('2'*64)
 if($certSha -ceq $publisher){throw 'Disposable test signer identity collided with synthetic publisher'}
 $a=[ordered]@{
  schema='cognitum.ssm.r3r1.independent_release_approval.v1'
  exact_source_sha=$ExactSourceSha
  signed_installer_sha256=('3'*64)
  signed_service_sha256=('4'*64)
  runtime_manifest_sha256=('5'*64)
  runtime_provenance_sha256=('6'*64)
  publisher_certificate_sha256=$publisher
  permits_Core_grant=$false
  permits_output_release=$false
 }
 $json=Join-Path $dir 'disposable-approval.json'
 $sig=Join-Path $dir 'disposable-approval.p7s'
 $data=[Text.Encoding]::UTF8.GetBytes(($a|ConvertTo-Json -Compress))
 [IO.File]::WriteAllBytes($json,$data)
 $cms=[Security.Cryptography.Pkcs.SignedCms]::new(
   [Security.Cryptography.Pkcs.ContentInfo]::new([byte[]]$data),$true)
 $signer=[Security.Cryptography.Pkcs.CmsSigner]::new($cert)
 $signer.DigestAlgorithm=[Security.Cryptography.Oid]::new('2.16.840.1.101.3.4.2.1')
 $cms.ComputeSignature($signer)
 [IO.File]::WriteAllBytes($sig,$cms.Encode())
 $gate=Join-Path $PSScriptRoot 'cog-r5-physical02-r3-r1-verify-detached-approval.ps1'
 $args=@{
  ApprovalJson=$json
  DetachedSignatureP7s=$sig
  ApprovedReleaseAuthorityCertificateSha256=$certSha
  ApprovedPublisherCertificateSha256=$publisher
  ExpectedSourceSha=$ExactSourceSha
 }
 $raw=& $gate @args
 if(-not $raw){throw 'Original disposable CMS cryptographic witness missing'}
 $witness=($raw|Out-String)|ConvertFrom-Json
 if($witness.status -cne 'PASS_DETACHED_APPROVAL_CRYPTOGRAPHIC_IDENTITY_OBSERVATION_ONLY' -or
    $witness.release_authority_certificate_sha256 -cne $certSha -or
    $witness.output_release_authorized -ne $false -or
    $witness.physically_installed_accepted -ne $false){
  throw 'Disposable signed approval escaped observation-only scope'
 }
 function Must-Refuse([scriptblock]$check){
  $refused=$false
  try{& $check | Out-Null}catch{
   if($_.Exception.Message -match 'COG_R3R1_APPROVAL_REFUSED'){$refused=$true}
   else{throw}
  }
  if(-not $refused){throw 'Untrusted detached approval was promoted'}
 }
 Must-Refuse { & $gate @args -ApprovedReleaseAuthorityCertificateSha256 ('7'*64) }
 Must-Refuse { & $gate @args -ApprovedPublisherCertificateSha256 $certSha }
 Must-Refuse { & $gate @args -ExpectedSourceSha ('8'*40) }
 # Tamper one signed payload byte without resigning.
 [IO.File]::WriteAllBytes($json,[Text.Encoding]::UTF8.GetBytes(
   ([Text.Encoding]::UTF8.GetString($data)).Replace(('3'*64),('9'*64))))
 Must-Refuse { & $gate @args }
 # A signer approving output release must be rejected even if signed.
 $a.permits_output_release=$true
 $wrong=[Text.Encoding]::UTF8.GetBytes(($a|ConvertTo-Json -Compress))
 [IO.File]::WriteAllBytes($json,$wrong)
 $wrongCms=[Security.Cryptography.Pkcs.SignedCms]::new(
   [Security.Cryptography.Pkcs.ContentInfo]::new([byte[]]$wrong),$true)
 $wrongCms.ComputeSignature($signer)
 [IO.File]::WriteAllBytes($sig,$wrongCms.Encode())
 Must-Refuse { & $gate @args }
 Write-Host 'PASS_CI_ONLY_DETACHED_CMS_APPROVAL_IDENTITY_TAMPER_AND_OUTPUT_DENIAL'
}finally{
 if($null -ne $cert){
  Remove-Item -LiteralPath ('Cert:\CurrentUser\My\'+$cert.Thumbprint) -Force -ErrorAction Stop
 }
}
