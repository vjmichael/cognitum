# Cognitum R2 signed installed-host independent READ-ONLY admission preflight.
# This does not install, sign, provision, enroll, approve a publisher,
# mint a Core grant or turn an unsigned CI fixture into production.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$InstalledExecutable,
 [Parameter(Mandatory=$true)][string]$ApprovedInstallRoot,
 [Parameter(Mandatory=$true)][string]$ApprovedImageSha256,
 [Parameter(Mandatory=$true)][string]$ApprovedSignerCertificateSha256
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function Refuse([string]$reason){throw "COG_R2_INSTALLED_REFUSED: $reason"}
if($env:OS -ne 'Windows_NT'){Refuse 'Real Windows required'}
$service='CognitumSsmSupervisorV1'
foreach($item in @($ApprovedImageSha256,$ApprovedSignerCertificateSha256)){
 if($item -cnotmatch '^[0-9a-f]{64}$' -or $item -ceq ('0'*64)){Refuse 'Separately approved nonzero SHA256 pin missing'}
}
if(-not [IO.Path]::IsPathRooted($InstalledExecutable) -or
   -not [IO.Path]::IsPathRooted($ApprovedInstallRoot)){
  Refuse 'Absolute approved binary/root required'
}
$exe=[IO.Path]::GetFullPath($InstalledExecutable)
$root=[IO.Path]::GetFullPath($ApprovedInstallRoot).TrimEnd('\')
if(-not $exe.StartsWith(($root+'\'),[StringComparison]::OrdinalIgnoreCase)){
  Refuse 'SCM executable outside independently approved root'
}
if(!(Test-Path -LiteralPath $exe -PathType Leaf)){Refuse 'Installed signed SCM executable absent'}
# Require no reparse point and no untrusted writable ACEs in every ancestor.
$trusted=@('S-1-5-18','S-1-5-32-544')
$cursor=$exe
while($true){
  $file=Get-Item -LiteralPath $cursor -Force
  if(($file.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
    Refuse 'SCM approved executable ancestry contains a reparse point'
  }
  $acl=Get-Acl -LiteralPath $cursor
  try{
    $owner=([Security.Principal.NTAccount]::new($acl.Owner)).Translate(
      [Security.Principal.SecurityIdentifier]).Value
  }catch{Refuse 'Unknown SCM image/root owner'}
  if($trusted -cnotcontains $owner){Refuse 'Installed executable ancestry not SYSTEM/Administrators owned'}
  foreach($ace in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])){
    $sid=$ace.IdentityReference.Value
    $mask=[uint32]([int64]$ace.FileSystemRights -band 0xffffffffL)
    $writeMask=[uint32]0x500D0156
    if($ace.AccessControlType -eq [Security.AccessControl.AccessControlType]::Allow -and
       ($mask -band $writeMask) -ne 0 -and $trusted -cnotcontains $sid){
      Refuse 'Untrusted principal can alter signed SCM code/data ancestry'
    }
  }
  if($cursor.Equals($root,[StringComparison]::OrdinalIgnoreCase)){break}
  $parent=[IO.Directory]::GetParent($cursor)
  if($null -eq $parent){Refuse 'Escaped approved root'}
  $cursor=$parent.FullName.TrimEnd('\')
  if(-not $cursor.Equals($root,[StringComparison]::OrdinalIgnoreCase) -and
     -not $cursor.StartsWith(($root+'\'),[StringComparison]::OrdinalIgnoreCase)){
    Refuse 'Escaped approved installation root'
  }
}
$hash=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()
if($hash -cne $ApprovedImageSha256){Refuse 'Executable hash differs from independently approved package'}
$signature=Get-AuthenticodeSignature -LiteralPath $exe
if($null -eq $signature -or $signature.Status -ne [Management.Automation.SignatureStatus]::Valid -or
   $null -eq $signature.SignerCertificate -or
   $signature.SignatureType -ne [Management.Automation.SignatureType]::Authenticode){
  Refuse 'Approved embedded Authenticode publisher invalid or missing'
}
$certsha=[Convert]::ToHexString([Security.Cryptography.SHA256]::HashData(
  $signature.SignerCertificate.RawData)).ToLowerInvariant()
if($certsha -cne $ApprovedSignerCertificateSha256){
  Refuse 'Authenticode certificate differs from independently approved publisher'
}
$svc=Get-CimInstance Win32_Service -Filter "Name='$service'"
if($null -eq $svc -or $svc.State -cne 'Running' -or $svc.StartMode -cne 'Auto' -or
   [uint32]$svc.ProcessId -eq 0 -or
   $svc.ServiceType -notlike '*Own Process*' -or
   $svc.ServiceType -like '*Share Process*'){
  Refuse 'Exact Cognitum production SCM service absent/not dedicated-running automatic'
}
if($svc.StartName -notin @('LocalSystem','NT AUTHORITY\LocalSystem')){
  Refuse 'SCM production supervisor account differs from approved SYSTEM custody'
}
if($svc.PathName -cne $exe -and $svc.PathName -cne ('"'+$exe+'"')){
  Refuse 'Installed SCM ImagePath command differs from trusted pinned binary'
}
$registry=Get-ItemProperty -LiteralPath ("HKLM:\SYSTEM\CurrentControlSet\Services\"+$service)
if($registry.Type -ne 16 -or $registry.Start -ne 2 -or
   $registry.ServiceSidType -ne 3){
  Refuse 'Protected SCM service type/start/restricted SID configuration invalid'
}
$proc=Get-CimInstance Win32_Process -Filter ("ProcessId="+[uint32]$svc.ProcessId)
if(!$proc -or !$proc.ExecutablePath.Equals($exe,[StringComparison]::OrdinalIgnoreCase) -or
   $null -eq $proc.CreationDate -or [uint32]$proc.SessionId -ne 0){
  Refuse 'Live SCM process image/generation/session differs'
}
$token=Invoke-CimMethod -InputObject $proc -MethodName GetOwnerSid
if($token.ReturnValue -ne 0 -or $token.Sid -cne 'S-1-5-18'){
  Refuse 'Native live SCM process lacks independent SYSTEM token witness'
}
# This success verifies ONLY signed host prerequisites, not signer key,
# AppContainer SSM child, original Core grant, signed stop or output ACK.
[pscustomobject]@{
 schema='cognitum.ssm.r2.production_installed_readonly_preflight.v1'
 status='PASS_SIGNED_SCM_IDENTITY_OBSERVATION_ONLY'
 service_pid=[uint32]$svc.ProcessId
 executable_sha256=$hash
 approved_signer_sha256=$certsha
 independently_provisioned_stop_key_verified=$false
 real_Core_Health_authenticated=$false
 production_restricted_SSM_original_worker_verified=$false
 external_output_release_authorized=$false
} | ConvertTo-Json
