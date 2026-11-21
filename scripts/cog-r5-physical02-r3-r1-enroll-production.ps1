# R3-R1 production SCM bootstrap enrollment. Physical administrator only.
# Signed and externally pinned assets must preexist. Never mint Core grants,
# create signer keys, launch SSM, or release worker output.
[CmdletBinding(SupportsShouldProcess=$true,ConfirmImpact='High')]
param(
 [Parameter(Mandatory=$true)][string]$SignedInstallerPackage,
 [Parameter(Mandatory=$true)][string]$ApprovedInstallerSha256,
 [Parameter(Mandatory=$true)][string]$ApprovedSignerCertificateSha256,
 [Parameter(Mandatory=$true)][string]$ApprovedInstallRoot,
 [Parameter(Mandatory=$true)][string]$InstalledExecutable,
 [Parameter(Mandatory=$true)][string]$ApprovedExecutableSha256,
 [Parameter(Mandatory=$true)][string]$RuntimeRoot,
 [Parameter(Mandatory=$true)][string]$ApprovedRuntimeManifestSha256,
 [Parameter(Mandatory=$true)][string]$ApprovedRuntimeProvenanceSha256
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function Refuse([string]$why){throw ("COG_R3R1_PRODUCTION_BOOTSTRAP_REFUSED: "+$why)}
if($env:OS -ne 'Windows_NT'){Refuse 'Real Windows required'}
$who=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if(-not $who.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){
 Refuse 'Elevated physical administrator required'
}
if(-not [IO.Path]::IsPathRooted($ApprovedInstallRoot) -or
   -not [IO.Path]::IsPathRooted($InstalledExecutable)){Refuse 'Absolute pinned installation paths required'}
$root=[IO.Path]::GetFullPath($ApprovedInstallRoot).TrimEnd('\')
$exe=[IO.Path]::GetFullPath($InstalledExecutable)
if(-not $exe.StartsWith(($root+'\'),[StringComparison]::OrdinalIgnoreCase) -or
   -not $exe.EndsWith('\cognitum-scm-production.exe',[StringComparison]::OrdinalIgnoreCase)){
 Refuse 'Separate genuine production SCM binary required, not CI fixture'
}
if($ApprovedExecutableSha256 -cnotmatch '^[0-9a-f]{64}$' -or $ApprovedExecutableSha256 -ceq ('0'*64)){
 Refuse 'Externally pinned nonzero native executable hash required'
}
$pkgGate=Join-Path $PSScriptRoot 'cog-r5-physical02-r3-r1-signed-installer.ps1'
$runtimeGate=Join-Path $PSScriptRoot 'cog-r5-physical02-r3-r1-runtime-audit.ps1'
$hostGate=Join-Path $PSScriptRoot 'cog-r5-physical02-r2-signed-host-preflight.ps1'
foreach($gate in @($pkgGate,$runtimeGate,$hostGate)){
 if(-not (Test-Path -LiteralPath $gate -PathType Leaf)){
  Refuse 'Reviewed signed package, runtime or host gate missing'
 }
}
$p=& $pkgGate -SignedInstallerPackage $SignedInstallerPackage -ApprovedInstallerSha256 $ApprovedInstallerSha256 -ApprovedSignerCertificateSha256 $ApprovedSignerCertificateSha256
if(-not $p){Refuse 'Signed installer identity absent'}
$pkg=($p|Out-String)|ConvertFrom-Json
if($pkg.status -cne 'PASS_SIGNED_STAGED_INSTALLER_IDENTITY_OBSERVATION_ONLY' -or
   $pkg.output_release_authorized -ne $false){Refuse 'Original installer publisher not accepted'}
$r=& $runtimeGate -ApprovedInstallRoot $root -RuntimeRoot $RuntimeRoot -ApprovedManifestSha256 $ApprovedRuntimeManifestSha256 -ApprovedProvenanceSha256 $ApprovedRuntimeProvenanceSha256
if(-not $r){Refuse 'Protected frozen import manifest absent'}
$runtime=($r|Out-String)|ConvertFrom-Json
if($runtime.status -cne 'PASS_INSTALLED_RUNTIME_DIGEST_ACL_OBSERVATION_ONLY' -or
   $runtime.output_release_authorized -ne $false){Refuse 'Unapproved installed runtime'}
$trusted=@('S-1-5-18','S-1-5-32-544')
$writeMask=[int64]0x500D0156L
$cursor=$exe
while($true){
 $item=Get-Item -LiteralPath $cursor -Force -ErrorAction Stop
 if(($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
  Refuse 'Production SCM executable reparse ancestry'
 }
 $acl=Get-Acl -LiteralPath $cursor -ErrorAction Stop
 try{$owner=$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value}
 catch{Refuse 'Unknown production SCM image owner'}
 if($trusted -cnotcontains $owner){Refuse 'Unprotected production image ownership'}
 foreach($ace in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])){
  if($ace.AccessControlType -eq [Security.AccessControl.AccessControlType]::Allow -and
     (([int64]$ace.FileSystemRights -band $writeMask) -ne 0) -and
     $trusted -cnotcontains $ace.IdentityReference.Value){
   Refuse 'Untrusted production service code ancestry write'
  }
 }
 if($cursor.Equals($root,[StringComparison]::OrdinalIgnoreCase)){break}
 $parent=[IO.Directory]::GetParent($cursor)
 if($null -eq $parent){Refuse 'Production binary escaped approved installation'}
 $cursor=$parent.FullName.TrimEnd('\')
}
if(-not (Test-Path -LiteralPath $exe -PathType Leaf)){Refuse 'Production executable absent'}
if((Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant() -cne
    $ApprovedExecutableSha256){Refuse 'Original executable differs from independently approved build'}
$sig=Get-AuthenticodeSignature -LiteralPath $exe
if($null -eq $sig -or $sig.Status -ne [Management.Automation.SignatureStatus]::Valid -or
   $sig.SignatureType -ne [Management.Automation.SignatureType]::Authenticode -or
   $null -eq $sig.SignerCertificate){Refuse 'Original production executable not Authenticode valid'}
$publisher=([Convert]::ToHexString([Security.Cryptography.SHA256]::HashData(
 $sig.SignerCertificate.RawData))).ToLowerInvariant()
if($publisher -cne $ApprovedSignerCertificateSha256){
 Refuse 'SCM production signer differs from independently approved installer'
}
$service='CognitumSsmSupervisorV1'
if($null -ne (Get-CimInstance Win32_Service -Filter "Name='$service'")){
 Refuse 'Existing service may not be overwritten or silently adopted'
}
if(-not $PSCmdlet.ShouldProcess($service,'Register protected zero-worker production SCM bootstrap')){
 return
}
& sc.exe create $service binPath= ('"'+$exe+'"') type= own start= auto obj= LocalSystem
if($LASTEXITCODE -ne 0){Refuse 'SCM protected dedicated registration failed'}
& sc.exe sidtype $service restricted
if($LASTEXITCODE -ne 0){Refuse 'Restricted service SID failed; installed state requires independent review'}
& sc.exe start $service
if($LASTEXITCODE -ne 0){Refuse 'Protected SCM startup failed; installed state requires independent review'}
# sc.exe reports a pending transition before Win32_Service becomes RUNNING.
# Bound this observer to 10 seconds; it creates no second operation.
$started=$false
for($i=0;$i -lt 50;$i++){
 $observed=Get-CimInstance Win32_Service -Filter "Name='$service'"
 if($null -ne $observed -and $observed.State -ceq 'Running'){
  $started=$true
  break
 }
 Start-Sleep -Milliseconds 200
}
if(-not $started){Refuse 'Native SCM service failed bounded RUNNING observation'}
$h=& $hostGate -InstalledExecutable $exe -ApprovedInstallRoot $root -ApprovedImageSha256 $ApprovedExecutableSha256 -ApprovedSignerCertificateSha256 $ApprovedSignerCertificateSha256
if(-not $h){Refuse 'Real signed installed host witness absent'}
$hostWitness=($h|Out-String)|ConvertFrom-Json
if($hostWitness.status -cne 'PASS_SIGNED_SCM_IDENTITY_OBSERVATION_ONLY' -or
   $hostWitness.external_output_release_authorized -ne $false){
 Refuse 'Original installed SCM service identity not verified'
}
[pscustomobject]@{
 schema='cognitum.ssm.r3r1.production_bootstrap_registration.v1'
 status='PASS_SIGNED_INSTALLED_SERVICE_BOOTSTRAP_ONLY'
 signed_installer_sha256=$pkg.release_package_sha256
 signed_service_sha256=$ApprovedExecutableSha256
 protected_runtime_manifest_sha256=$runtime.manifest_sha256
 service_pid=$hostWitness.service_pid
 nonadmin_AppContainer_worker_verified=$false
 separate_production_CNG_signer_verified=$false
 original_Lu_Core_grant_verified=$false
 physical_complete_acceptance=$false
 output_release_or_ACK_authorized=$false
}|ConvertTo-Json -Compress
