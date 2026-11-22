# ONLY disposable CI GPG cryptography. Never an authorized publisher signature.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$ExactSourceSha)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($env:OS -cne 'Windows_NT' -or $env:GITHUB_ACTIONS -cne 'true' -or $env:RUNNER_OS -cne 'Windows'){
 throw 'COG_R3R1_PRIVATE_CI_REFUSED: disposable Windows runner only'
}
$gpgCommand=Get-Command gpg.exe -ErrorAction SilentlyContinue
$gpg=if($null -ne $gpgCommand){$gpgCommand.Source}else{''}
if(-not $gpg){
 $gpg=Join-Path $env:ProgramFiles 'Git\usr\bin\gpg.exe'
}
if(-not (Test-Path -LiteralPath $gpg -PathType Leaf)){throw 'Original Windows GnuPG executable unavailable'}
$stage=Join-Path $env:RUNNER_TEMP ('cog-r3r1-disposable-gpg-'+$env:GITHUB_RUN_ID)
if(Test-Path -LiteralPath $stage){throw 'Reused CI-only synthetic signature fixture'}
$gpgHome=Join-Path $stage 'home'
$out=Join-Path $stage 'release'
$runtime=Join-Path $out 'payload\runtime'
New-Item -ItemType Directory -Path $gpgHome,$runtime -Force|Out-Null
$isMsysGpg=$gpg -match '(?i)\\Git\\(usr|mingw64)\\bin\\gpg\.exe$'
$cygpath=if($isMsysGpg){Join-Path (Split-Path $gpg -Parent) 'cygpath.exe'}else{''}
if($isMsysGpg -and -not(Test-Path -LiteralPath $cygpath -PathType Leaf)){
 throw 'Original Git GPG cygpath converter unavailable'
}
function Gpg-Path([string]$path){
 if(-not $isMsysGpg){return $path}
 $converted=@(& $cygpath -u $path)
 if($LASTEXITCODE -ne 0 -or $converted.Count -ne 1){throw 'CI GPG path conversion refused'}
 [string]$converted[0]
}
$former=$env:GNUPGHOME
try{
 $env:GNUPGHOME=(Gpg-Path $gpgHome)
 $who='Cognitum CI ephemeral test <cog-fixture@example.invalid>'
 $created=@(& $gpg --batch --no-tty --pinentry-mode loopback --passphrase 'ci-only-disposable' --quick-generate-key $who ed25519 sign 1d 2>&1)
 if($LASTEXITCODE -ne 0){
  $diagnostic=($created -join ' ').Substring(0,[Math]::Min(240,($created -join ' ').Length))
  $diagnostic=[regex]::Replace($diagnostic,'[^A-Za-z0-9 _.,:;/-]','_')
  throw ('Disposable one-run-only GPG key fixture creation failed: '+$diagnostic)
 }
 $listed=@(& $gpg --batch --with-colons --fingerprint --list-secret-keys 2>&1)
 if($LASTEXITCODE -ne 0){throw 'Disposable GPG primary fingerprint unavailable'}
 $fprLine=@($listed|Where-Object{([string]$_).StartsWith('fpr:')})[0]
 if(-not $fprLine){throw 'Disposable original GPG test fingerprint absent'}
 $fp=([string]$fprLine).Split(':')[9].ToUpperInvariant()
 if($fp -cnotmatch '^[A-F0-9]{40}$'){throw 'Disposable GPG primary key fingerprint invalid'}
 $public=Join-Path $stage 'ci-only-public.asc'
 & $gpg --batch --no-tty --armor --output (Gpg-Path $public) --export $fp
 if($LASTEXITCODE -ne 0){throw 'Disposable original GPG public key export failed'}
 $exe=Join-Path $out 'payload\cognitum-scm-production.exe'
 $installer=Join-Path $out 'Cognitum-SSM-R3R1-Bootstrap.exe'
 [IO.File]::WriteAllText($installer,'CI_ONLY_NO_PRODUCTION_WINDOWS_INSTALLER',[Text.Encoding]::ASCII)
 [IO.File]::WriteAllText($exe,'CI_ONLY_NO_PRODUCTION_SCM_BINARY',[Text.Encoding]::ASCII)
 $file=Join-Path $runtime 'a.py'
 [IO.File]::WriteAllText($file,'# CI-only ephemeral runtime',[Text.Encoding]::ASCII)
 $hash=(Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
 $manifest=Join-Path $runtime 'r3-r1-runtime.manifest'
 [IO.File]::WriteAllText($manifest,($hash+[char]9+'a.py'+[char]10),[Text.Encoding]::ASCII)
 $manifestSha=(Get-FileHash -LiteralPath $manifest -Algorithm SHA256).Hash.ToLowerInvariant()
 $provenance=Join-Path $runtime 'r3-r1-runtime-provenance.json'
 [IO.File]::WriteAllText($provenance,([ordered]@{
  schema='cognitum.ssm.r3r1.production_installer_runtime.v1'
  runtime_manifest_sha256=$manifestSha
  original_production_source_sha=$ExactSourceSha
  external_manifest_approved_for_production=$true
  ci_synthetic_test_only=$true
 }|ConvertTo-Json -Compress)+[char]10,[Text.Encoding]::ASCII)
 $recordFile=Join-Path $out 'private-release.json'
 $sig=Join-Path $out 'private-release.json.asc'
 $record=[ordered]@{
  schema='cognitum.ssm.r3r1.private_gpg_release.v1'
  lane='personal_local_only'
  exact_source_sha=$ExactSourceSha
  gpg_primary_fingerprint=$fp
  installer_sha256=(Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
  service_sha256=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()
  runtime_manifest_sha256=$manifestSha
  runtime_provenance_sha256=(Get-FileHash -LiteralPath $provenance -Algorithm SHA256).Hash.ToLowerInvariant()
  permits_core_grant=$false
  permits_output_release=$false
 }
 function Sign-OriginalFixture{
  [IO.File]::WriteAllText($recordFile,($record|ConvertTo-Json -Compress)+[char]10,[Text.Encoding]::ASCII)
  & $gpg --batch --yes --no-tty --pinentry-mode loopback --passphrase 'ci-only-disposable' --local-user $fp --armor --output (Gpg-Path $sig) --detach-sign (Gpg-Path $recordFile)
  if($LASTEXITCODE -ne 0){throw 'Disposable GPG fixture could not be signed'}
 }
 Sign-OriginalFixture
 $verify=Join-Path $PSScriptRoot 'cog-r5-physical02-r3-r1-private-gpg-verify.ps1'
 $inputs=@{
  ReleaseRoot=$out
  TrustedPublicKeyFile=$public
  ExpectedPrimaryFingerprint=$fp
  ExpectedSourceSha=$ExactSourceSha
  GpgExecutable=$gpg
 }
 $result=& $verify @inputs
 $claim=($result|Out-String)|ConvertFrom-Json
 if($claim.status -cne 'PASS_PRIVATE_GPG_PACKAGE_DIGESTS_OBSERVATION_ONLY' -or
    $claim.physical_windows_installed_accepted -ne $false -or
    $claim.output_release_or_ACK_authorized -ne $false){
  throw 'Original ephemeral GPG signature did not remain observation only'
 }
 function Must-Refuse([scriptblock]$assertion,[string]$expected='COG_R3R1_PRIVATE_GPG_REFUSED'){
  $denied=$false
  try{& $assertion|Out-Null}catch{
   if($_.Exception.Message.Contains($expected)){$denied=$true}else{throw}
  }
  if(-not $denied){throw 'Untrusted private GPG input was promoted to accepted'}
 }
 Must-Refuse {& $verify @inputs -ExpectedPrimaryFingerprint ('A'*40)}
 Must-Refuse {& $verify @inputs -ExpectedSourceSha ('b'*40)}
 # Signed manifest SHA alone is insufficient: verify every payload import
 # and reject an extra import even if the GPG signature remains valid.
 [IO.File]::WriteAllText($file,'TAMPERED_RUNTIME_IMPORT',[Text.Encoding]::ASCII)
 Must-Refuse {& $verify @inputs}
 [IO.File]::WriteAllText($file,'# CI-only ephemeral runtime',[Text.Encoding]::ASCII)
 $extra=Join-Path $runtime 'unlisted.py'
 [IO.File]::WriteAllText($extra,'# CI-only unlisted import',[Text.Encoding]::ASCII)
 Must-Refuse {& $verify @inputs}
 Remove-Item -LiteralPath $extra -Force -ErrorAction Stop
 [IO.File]::WriteAllText($installer,'TAMPERED_UNSIGNED_CI_ONLY',[Text.Encoding]::ASCII)
 Must-Refuse {& $verify @inputs}
 [IO.File]::WriteAllText($installer,'CI_ONLY_NO_PRODUCTION_WINDOWS_INSTALLER',[Text.Encoding]::ASCII)
 $record.permits_output_release=$true
 Sign-OriginalFixture
 Must-Refuse {& $verify @inputs}
 $physical=Join-Path $PSScriptRoot 'cog-r5-physical02-r3-r1-private-gpg-physical.ps1'
 $build=Join-Path $PSScriptRoot 'cog-r5-physical02-r3-r1-private-gpg-build.ps1'
 Must-Refuse {& $physical @inputs -Confirm:$false} 'COG_R3R1_PRIVATE_PHYSICAL_REFUSED'
 Must-Refuse {
  & $build -ExactSourceSha $ExactSourceSha -ApprovedRuntimeRoot $runtime -ApprovedRuntimeManifestSha256 $manifestSha -ApprovedRuntimeProvenanceSha256 $record.runtime_provenance_sha256 -GpgPrimaryFingerprint $fp -TrustedPublicKeyFile $public -GpgExecutable $gpg -MakeNsisExecutable $gpg -ProtectedStageRoot $stage
 } 'COG_R3R1_PRIVATE_GPG_BUILD_REFUSED'
 Write-Host 'PASS_CI_ONLY_PRIVATE_GPG_DETACHED_SIGNATURE_TAMPER_SOURCE_AND_OUTPUT_DENIAL'
}finally{
 $env:GNUPGHOME=$former
 # The CI-only private key is destroyed with its disposable runner home.
 Remove-Item -LiteralPath $stage -Force -Recurse -ErrorAction Stop
}
