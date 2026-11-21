# R3-R1 unsigned hosted Windows NSIS carrier smoke. Not a production release.
# Installs only a CI synthetic runtime, then removes only its own test tree.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$CompiledBootstrap,
 [Parameter(Mandatory=$true)][string]$MakeNsis
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function Refuse([string]$why){throw ("COG_R3R1_CI_NSIS_REFUSED: "+$why)}
if($env:OS -cne 'Windows_NT' -or $env:GITHUB_ACTIONS -cne 'true' -or
   $env:RUNNER_OS -cne 'Windows'){Refuse 'Only disposable hosted Windows runner admitted'}
$identity=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if(-not $identity.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){
 Refuse 'Hosted NSIS installation requires elevated runner'
}
foreach($path in @($CompiledBootstrap,$MakeNsis)){
 if(-not [IO.Path]::IsPathRooted($path) -or
    -not (Test-Path -LiteralPath $path -PathType Leaf)){
  Refuse 'Original separate native image and NSIS binary must exist'
 }
}
$exe=[IO.Path]::GetFullPath($CompiledBootstrap)
if(-not $exe.EndsWith('\cognitum-scm-production.exe',[StringComparison]::OrdinalIgnoreCase)){
 Refuse 'CI fixture or foreign executable cannot be used as production bootstrap payload'
}
if((Get-AuthenticodeSignature -LiteralPath $exe).Status -ne
   [Management.Automation.SignatureStatus]::NotSigned){
 Refuse 'Unsigned CI build may never consume an approved signed release asset'
}
$installRoot=Join-Path $env:ProgramFiles 'Cognitum\SSM'
if(Test-Path -LiteralPath $installRoot){
 Refuse 'Runner has preexisting Cognitum installation; never adopt or overwrite'
}
if(Get-CimInstance Win32_Service -Filter "Name='CognitumSsmSupervisorV1'"){
 Refuse 'Runner has preexisting Cognitum SCM service; never adopt or replace'
}
$work=Join-Path $env:RUNNER_TEMP ('cog-r3r1-nsis-'+$env:GITHUB_RUN_ID)
if(Test-Path -LiteralPath $work){Refuse 'This exact CI carrier staging path already exists'}
$payload=Join-Path $work 'payload'
$runtime=Join-Path $payload 'runtime'
New-Item -ItemType Directory -Path $runtime -Force|Out-Null
Copy-Item -LiteralPath $exe -Destination (Join-Path $payload 'cognitum-scm-production.exe')
[IO.File]::WriteAllBytes((Join-Path $runtime '__init__.py'),[byte[]]@())
[IO.File]::WriteAllText((Join-Path $runtime 'a.py'),'print(1)',[Text.Encoding]::ASCII)
$h0=(Get-FileHash (Join-Path $runtime '__init__.py') -Algorithm SHA256).Hash.ToLowerInvariant()
$h1=(Get-FileHash (Join-Path $runtime 'a.py') -Algorithm SHA256).Hash.ToLowerInvariant()
$tab=[char]9
$lf=[char]10
$manifest=Join-Path $runtime 'r3-r1-runtime.manifest'
[IO.File]::WriteAllText($manifest,("$h0$tab"+'__init__.py'+"$lf"+"$h1$tab"+'a.py'+"$lf"),[Text.Encoding]::ASCII)
$manifestPin=(Get-FileHash -LiteralPath $manifest -Algorithm SHA256).Hash.ToLowerInvariant()
$provenance=Join-Path $runtime 'r3-r1-runtime-provenance.json'
$ciRecord=[ordered]@{
 schema='cognitum.ssm.r3r1.test_installer_style_frozen_runtime.v1'
 runtime_manifest_sha256=$manifestPin
 independent_publisher_approved=$false
 production_Core_grant=$false
 output_release_authorized=$false
}
[IO.File]::WriteAllText($provenance,($ciRecord|ConvertTo-Json -Compress)+$lf,[Text.Encoding]::ASCII)
$inventory=@(Get-ChildItem -LiteralPath $runtime -File |ForEach-Object{
 [pscustomobject]@{Name=$_.Name;Sha=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
})
$installer=Join-Path $work 'ci-UNSIGNED-Cognitum-SSM-Bootstrap.exe'
$nsisScript=Join-Path $PSScriptRoot '../deployment/windows/cognitum-ssm-bootstrap.nsi'
& $MakeNsis '/V2' ('/DCOG_PAYLOAD_DIR='+$payload) ('/DCOG_OUTPUT_FILE='+$installer) $nsisScript
if($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $installer -PathType Leaf)){
 Refuse 'Exact NSIS production carrier source did not compile'
}
if((Get-AuthenticodeSignature -LiteralPath $installer).Status -ne
   [Management.Automation.SignatureStatus]::NotSigned){
 Refuse 'Hosted unsigned package test must never claim a signed production release'
}
$owned=$false
$originalTestFailure=$null
try{
 $owned=$true
 # The /D attempt must not redirect the production carrier outside Program Files.
 $redirect=Join-Path $work 'attacker-redirect'
 $install=Start-Process -FilePath $installer -ArgumentList @('/S',('/D='+$redirect)) -PassThru -Wait
 if($install.ExitCode -ne 0){Refuse ('Unsigned NSIS real Windows install failed: '+$install.ExitCode)}
 if(Test-Path -LiteralPath $redirect){Refuse 'Caller /D redirected Program Files installer destination'}
 if(-not (Test-Path -LiteralPath $installRoot -PathType Container)){
  Refuse 'Original installed NSIS Program Files root absent'
 }
 $installedExe=Join-Path $installRoot 'cognitum-scm-production.exe'
 if(-not (Test-Path -LiteralPath $installedExe -PathType Leaf)){
  Refuse 'Installed no-worker SCM image absent'
 }
 if((Get-FileHash -LiteralPath $installedExe -Algorithm SHA256).Hash.ToLowerInvariant() -cne
    (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()){
  Refuse 'Installed SCM executable byte identity differs from compiled original'
 }
 $installedRuntime=Join-Path $installRoot 'runtime'
 $actual=@(Get-ChildItem -LiteralPath $installedRuntime -Recurse -File -Force)
 if($actual.Count -ne $inventory.Count){Refuse 'Installed frozen runtime file inventory differs'}
 foreach($item in $inventory){
  $installed=Join-Path $installedRuntime $item.Name
  if(-not (Test-Path -LiteralPath $installed -PathType Leaf) -or
     (Get-FileHash -LiteralPath $installed -Algorithm SHA256).Hash.ToLowerInvariant() -cne $item.Sha){
   Refuse 'Original packaged runtime file byte identity differs'
  }
 }
 $trusted=@('S-1-5-18','S-1-5-32-544')
 $writeMask=[int64]0x500D0156L
 foreach($path in @($installRoot,$installedExe,$installedRuntime)+@($actual|ForEach-Object{$_.FullName})){
  $acl=Get-Acl -LiteralPath $path
  $owner=$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value
  if($trusted -cnotcontains $owner){Refuse 'Installed NSIS tree owner is not SYSTEM or Administrators'}
  $adminEffective=$false
  $systemEffective=$false
  foreach($ace in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])){
   if($ace.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow){continue}
   $sid=$ace.IdentityReference.Value
   $rights=[int64]$ace.FileSystemRights
   if(($rights -band $writeMask) -ne 0 -and $trusted -cnotcontains $sid){
    Refuse 'Untrusted write principal remained after NSIS ACL sealing'
   }
   if(($ace.PropagationFlags -band [Security.AccessControl.PropagationFlags]::InheritOnly) -ne 0){
    continue
   }
   if($sid -eq 'S-1-5-18' -and ($rights -band $writeMask) -ne 0){$systemEffective=$true}
   if($sid -eq 'S-1-5-32-544' -and ($rights -band $writeMask) -ne 0){$adminEffective=$true}
  }
  if(-not $adminEffective -or -not $systemEffective){
   Refuse 'Installed file lacks effective SYSTEM/Administrators access'
  }
 }
 if(Get-CimInstance Win32_Service -Filter "Name='CognitumSsmSupervisorV1'"){
  Refuse 'Unsigned NSIS carrier unexpectedly enrolled a Windows service'
 }
 # Real SCM proof uses the ACTUALLY PACKAGED image, not the original build tree.
 & (Join-Path $PSScriptRoot 'cog-r5-physical02-r3-r1-ci-scm-lifecycle.ps1') -CompiledBootstrap $installedExe
 if(Get-CimInstance Win32_Service -Filter "Name='CognitumSsmSupervisorV1'"){
  Refuse 'CI original SCM lifecycle failed to delete its own test service'
 }
 $reinstall=Start-Process -FilePath $installer -ArgumentList '/S' -PassThru -Wait
 if($reinstall.ExitCode -eq 0){Refuse 'Existing installed tree was silently overwritten/adopted'}
 if((Get-FileHash -LiteralPath $installedExe -Algorithm SHA256).Hash.ToLowerInvariant() -cne
    (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()){
  Refuse 'Existing installation changed after rejected reinstall'
 }
 Write-Host 'PASS_CI_ONLY_UNSIGNED_NSIS_REAL_INSTALL_PROTECTED_ACL_AND_PACKAGED_SCM_LIFECYCLE'
 Write-Host ('CI_UNSIGNED_INSTALLER_SHA256='+
   (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant())
}catch{
 $originalTestFailure=$_
}finally{
 $cleanupFailure=$null
 if($owned){
  try{
   if(Get-CimInstance Win32_Service -Filter "Name='CognitumSsmSupervisorV1'"){
    Refuse 'CI-owned SCM service remains: cannot safely remove packaged tree'
   }
   if(Test-Path -LiteralPath $installRoot){
    Remove-Item -LiteralPath $installRoot -Force -Recurse -ErrorAction Stop
   }
  }catch{$cleanupFailure=$_}
 }
 if($originalTestFailure){
  $detail='Original NSIS package test failure: '+$originalTestFailure.Exception.Message
  if($cleanupFailure){$detail+='; cleanup also failed: '+$cleanupFailure.Exception.Message}
  Refuse $detail
 }
 if($cleanupFailure){Refuse ('Unsigned NSIS cleanup failure: '+$cleanupFailure.Exception.Message)}
}
