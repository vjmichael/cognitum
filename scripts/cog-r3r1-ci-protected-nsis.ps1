# CI-only distinct protected NSIS install carrier smoke on disposable runner.
# Never install the owner's production build, register a service, provision a
# CNG signer, consume Core grants or deliver SSM output. The frozen runtime
# below is intentionally synthetic; its package MUST NOT be signed.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$CompiledProtectedService,
 [Parameter(Mandatory=$true)][string]$MakeNsisExecutable
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function Refuse([string]$why){throw ('CI_PROTECTED_NSIS_REFUSED: '+$why)}
if($env:OS -cne 'Windows_NT' -or $env:GITHUB_ACTIONS -cne 'true' -or
   $env:RUNNER_OS -cne 'Windows'){Refuse 'Disposable hosted Windows CI ONLY'}
$identity=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if(-not $identity.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){
 Refuse 'Disposable Windows runner requires administrative installer custody'
}
foreach($p in @($CompiledProtectedService,$MakeNsisExecutable)){
 if(-not [IO.Path]::IsPathRooted($p) -or -not(Test-Path -LiteralPath $p -PathType Leaf)){
  Refuse 'Original native compiled service / NSIS compiler unavailable'
 }
}
$root=Join-Path $env:ProgramFiles 'Cognitum\SSMProtected'
$original=Join-Path $env:ProgramFiles 'Cognitum\SSM'
if((Test-Path -LiteralPath $root) -or (Test-Path -LiteralPath $original) -or
   (Get-CimInstance Win32_Service -Filter "Name='CognitumSsmProtectedV1'") -or
   (Get-CimInstance Win32_Service -Filter "Name='CognitumSsmSupervisorV1'") -or
   (Get-CimInstance Win32_Service -Filter "Name='CognitumSsmProductionQualifierV1'")){
 Refuse 'Runner contains a preexisting Cognitum installation/service; cannot adopt'
}
$work=Join-Path $env:RUNNER_TEMP ('cog-protected-nsis-'+$env:GITHUB_RUN_ID)
if(Test-Path -LiteralPath $work){Refuse 'Original CI test staging already exists'}
$payload=Join-Path $work 'payload'
$runtime=Join-Path $payload 'runtime'
New-Item -ItemType Directory -Path $runtime -Force -ErrorAction Stop|Out-Null
Copy-Item -LiteralPath $CompiledProtectedService -Destination (Join-Path $payload 'cognitum-scm-production.exe')
[IO.File]::WriteAllText((Join-Path $runtime 'SYNTHETIC_CI_NOT_PRODUCTION.txt'),'NO_WORKER_OR_RELEASE_AUTHORITY',[Text.Encoding]::ASCII)
$originalImage=(Get-FileHash -LiteralPath $CompiledProtectedService -Algorithm SHA256).Hash.ToLowerInvariant()
$installer=Join-Path $work 'UNSIGNED-CI-ONLY-Cognitum-SSM-Protected.exe'
$nsis=Join-Path $PSScriptRoot '../deployment/windows/cognitum-ssm-protected-successor.nsi'
& $MakeNsisExecutable '/V2' ('/DCOG_PAYLOAD_DIR='+$payload) ('/DCOG_OUTPUT_FILE='+$installer) $nsis|Out-Null
if($LASTEXITCODE -ne 0 -or -not(Test-Path -LiteralPath $installer -PathType Leaf)){
 Refuse 'Distinct fixed Program Files successor NSIS failed build'
}
if((Get-AuthenticodeSignature -LiteralPath $installer).Status -ne
   [Management.Automation.SignatureStatus]::NotSigned){
 Refuse 'CI-only carrier may never become a signed production release'
}
$owned=$false
try{
 $install=Start-Process -FilePath $installer -ArgumentList @('/S','/D=C:\untrusted\attacker-redirect') -PassThru -Wait
 if($install.ExitCode -ne 0){Refuse 'Genuine CI-only Windows NSIS install rejected'}
 if(Test-Path -LiteralPath 'C:\untrusted\attacker-redirect'){
  Refuse 'User-controlled NSIS /D redirected protected source'
 }
 if(-not(Test-Path -LiteralPath $root -PathType Container)){
  Refuse 'Distinct protected successor Program Files root not installed'
 }
 $owned=$true
 $installed=Join-Path $root 'cognitum-scm-production.exe'
 $sentinel=Join-Path $root 'runtime\SYNTHETIC_CI_NOT_PRODUCTION.txt'
 if(-not(Test-Path -LiteralPath $installed -PathType Leaf) -or
    -not(Test-Path -LiteralPath $sentinel -PathType Leaf)){
  Refuse 'Original CI-only NSIS native code/runtime files missing'
 }
 if((Get-FileHash -LiteralPath $installed -Algorithm SHA256).Hash.ToLowerInvariant() -cne
     $originalImage){
  Refuse 'Installed protected native binary hash differs from built source'
 }
 if((Get-Content -LiteralPath $sentinel -Raw).Trim() -cne 'NO_WORKER_OR_RELEASE_AUTHORITY'){
  Refuse 'Synthetic CI runtime identity altered during install'
 }
 if((Test-Path -LiteralPath $original) -or
    (Get-CimInstance Win32_Service -Filter "Name='CognitumSsmProtectedV1'") -or
    (Get-CimInstance Win32_Service -Filter "Name='CognitumSsmSupervisorV1'")){
  Refuse 'Protected package overwrote original no-worker tree or enrolled SCM'
 }
 Write-Host 'PASS_CI_DISTINCT_PROTECTED_NSIS_INSTALLED_SEPARATELY_NO_WORKER_NO_GPG'
}finally{
 if($owned -and (Test-Path -LiteralPath $root -PathType Container)){
  $protectedImage=Join-Path $root 'cognitum-scm-production.exe'
  if((Test-Path -LiteralPath $protectedImage -PathType Leaf) -and
     (Get-FileHash -LiteralPath $protectedImage -Algorithm SHA256).Hash.ToLowerInvariant() -cne $originalImage){
   Refuse 'Refusing cleanup of unexpected or modified installed protected source'
  }
  Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction Stop
 }
}
