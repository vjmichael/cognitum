# R3-R1 personally controlled Windows private GPG release stages.
# No signing material, external approvals, Core grant, or physical installation is minted here.
[CmdletBinding()]
param(
 [ValidateSet('Check','Candidate','Production','Sign','Verify')][string]$Phase='Check',
 [string]$ExactSourceSha='',
 [string]$PythonExecutable='',
 [string]$ApprovedPythonSha256='',
 [string]$ApprovedManifestSha256='',
 [string]$ApprovedProvenanceSha256='',
 [string]$RuntimeRoot='',
 [string]$StageRoot='',
 [string]$ReleaseRoot='',
 [string]$PublicKeyFile='',
 [string]$GpgExecutable='',
 [string]$MakeNsisExecutable='',
 [string]$GpgPrimaryFingerprint='DB9C7C9FCC675D8EE33D3F885007C136EE8BDB86'
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function Refuse([string]$reason){throw ('COG_R3R1_PERSONAL_RELEASE_REFUSED: '+$reason)}
if($env:OS -cne 'Windows_NT' -or $env:CI -eq 'true' -or $env:GITHUB_ACTIONS -eq 'true'){
 Refuse 'An original non-CI Windows PC is required for every personal release phase'
}
if(-not [Environment]::Is64BitProcess -or $PSVersionTable.PSVersion.Major -lt 7){
 Refuse 'Native x64 PowerShell 7 is required'
}
if($GpgPrimaryFingerprint -cnotmatch '^([A-Fa-f0-9]{40}|[A-Fa-f0-9]{64})$'){
 Refuse 'An independently selected full primary GPG fingerprint is required'
}
$fp=$GpgPrimaryFingerprint.ToUpperInvariant()
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
function Tool([string]$name,[string]$supplied=''){
 if($supplied){
  if(-not [IO.Path]::IsPathRooted($supplied) -or
     -not (Test-Path -LiteralPath $supplied -PathType Leaf)){
   Refuse ('Original executable path missing: '+$name)
  }
  return [IO.Path]::GetFullPath($supplied)
 }
 $cmd=Get-Command $name -CommandType Application -ErrorAction SilentlyContinue |
      Select-Object -First 1
 if($null -eq $cmd){return ''}
 return [string]$cmd.Source
}
function Need-File([string]$path,[string]$description){
 if(-not $path -or -not [IO.Path]::IsPathRooted($path) -or
    -not (Test-Path -LiteralPath $path -PathType Leaf)){
  Refuse ('Missing original absolute '+$description)
 }
}
function Need-Hash([string]$value,[string]$description){
 if($value -cnotmatch '^[a-f0-9]{64}$' -or $value -ceq ('0'*64)){
  Refuse ('Original externally approved lowercase SHA256 required: '+$description)
 }
}
function Need-DirDestination([string]$path){
 if(-not $path -or -not [IO.Path]::IsPathRooted($path) -or
    (Test-Path -LiteralPath $path) -or
    -not (Test-Path -LiteralPath (Split-Path $path -Parent) -PathType Container)){
  Refuse 'Fresh absent absolute runtime directory under an existing original parent required'
 }
}
function Digest([string]$path){
 (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
}
$git=Tool 'git.exe'
$python=Tool 'python.exe' $PythonExecutable
$gpg=Tool 'gpg.exe' $GpgExecutable
$cargo=Tool 'cargo.exe'
$nsis=Tool 'makensis.exe' $MakeNsisExecutable
if(-not $nsis){
 foreach($rootName in @('ProgramFiles(x86)','ProgramFiles')){
  $programFiles=[Environment]::GetEnvironmentVariable($rootName)
  if(-not $programFiles){continue}
  $candidate=Join-Path $programFiles 'NSIS\makensis.exe'
  if(Test-Path -LiteralPath $candidate -PathType Leaf){$nsis=$candidate;break}
 }
}
if(-not $PublicKeyFile){
 $PublicKeyFile=Join-Path (Join-Path $HOME 'Documents') 'cognitum-ecc-public.asc'
}
if(-not $git){Refuse 'Git must be installed and on PATH'}
$head=@(& $git -C $repo rev-parse HEAD)
if($LASTEXITCODE -ne 0 -or $head.Count -ne 1){Refuse 'Original Git source checkout absent'}
$tracked=@(& $git -C $repo status --porcelain --untracked-files=no)
if($LASTEXITCODE -ne 0){Refuse 'Original Git tracked-source state unavailable'}
$localPythonHash=if($python){Digest $python}else{''}
$keyAvailable=$false
$publicKeyMatched=$false
if($gpg){
 $secretLines=@(& $gpg --batch --with-colons --fingerprint --list-secret-keys $fp 2>&1)
 $keyAvailable=($LASTEXITCODE -eq 0 -and
     ($secretLines -join [char]10).ToUpperInvariant().Contains($fp))
 if(Test-Path -LiteralPath $PublicKeyFile -PathType Leaf){
  $publicLines=@(& $gpg --batch --no-tty --with-colons --fingerprint --show-keys $PublicKeyFile 2>&1)
  if($LASTEXITCODE -eq 0){
   $primaryFollowing=$false
   $identities=@()
   foreach($line in $publicLines){
    $columns=([string]$line).Split(':')
    if($columns[0] -eq 'pub'){$primaryFollowing=$true;continue}
    if($columns[0] -eq 'sub'){$primaryFollowing=$false;continue}
    if($columns[0] -eq 'fpr' -and $primaryFollowing){
     $identities+=([string]$columns[9]).ToUpperInvariant()
     $primaryFollowing=$false
    }
   }
   $publicKeyMatched=($identities.Count -eq 1 -and $identities[0] -ceq $fp)
  }
 }
}
# Read-only interpreter inventory; no dependency installation or download.
$pythonInventory=[pscustomobject]@{
 status='PYTHON_NOT_FOUND'
 runtime_layout_valid=$false
 packages_imported=$false
 packages=@{}
}
if($python){
 $probe=@'
import sys, json, struct, importlib, importlib.metadata as metadata
from pathlib import Path
mods=(("numpy","numpy"),("scipy","scipy"),
      ("google.protobuf","protobuf"),("cryptography","cryptography"))
packages={}
for module,distribution in mods:
    try:
        importlib.import_module(module)
        packages[distribution]={"imported":True,"version":metadata.version(distribution)}
    except Exception as exc:
        packages[distribution]={"imported":False,"error_type":type(exc).__name__}
prefix=Path(sys.prefix).resolve()
executable=Path(sys.executable).resolve()
layout=(executable.parent==prefix and (prefix/"DLLs").is_dir()
        and (prefix/"Lib").is_dir() and (prefix/"Lib"/"site-packages").is_dir())
print(json.dumps({"status":"READ_ONLY_INTERPRETER_INVENTORY",
 "python_version":sys.version.split()[0],"python_bits":struct.calcsize("P")*8,
 "runtime_layout_valid":layout,
 "packages_imported":all(item["imported"] for item in packages.values()),
 "packages":packages},separators=(",",":")))
'@
 try{
  $probeLines=@(& $python -c $probe 2>$null)
  if($LASTEXITCODE -eq 0 -and $probeLines.Count -eq 1){
   $pythonInventory=$probeLines[0]|ConvertFrom-Json
  }else{
   $pythonInventory.status='PYTHON_IMPORT_PROBE_FAILED'
  }
 }catch{$pythonInventory.status='PYTHON_IMPORT_PROBE_FAILED'}
}

if($Phase -eq 'Check'){
 [pscustomobject]@{
  schema='cognitum.ssm.r3r1.personal_tool_preflight.v1'
  status='INFORMATION_ONLY_EXTERNAL_APPROVAL_NOT_GRANTED'
  checked_out_source_sha=$head[0]
  tracked_source_clean=($tracked.Count -eq 0)
  python_path=$python
  observed_python_sha256=$localPythonHash
  git_path=$git
  cargo_path=$cargo
  makensis_path=$nsis
  gpg_path=$gpg
  gpg_primary_fingerprint=$fp
  gpg_secret_key_listed=$keyAvailable
  public_key_file_present=(Test-Path -LiteralPath $PublicKeyFile -PathType Leaf)
  public_key_matches_selected_primary_fingerprint=$publicKeyMatched
  python_runtime_inventory=$pythonInventory
  approved_runtime=$false
  signed_release=$false
  physical_installed_accepted=$false
  output_release_authorized=$false
 }|ConvertTo-Json -Compress
 return
}
if($ExactSourceSha -cnotmatch '^[a-f0-9]{40}$' -or $head[0] -cne $ExactSourceSha){
 Refuse 'Exact reviewed original Git source SHA does not match checkout'
}
if($tracked.Count -ne 0){Refuse 'Tracked original source has local edits'}
if($Phase -eq 'Candidate' -or $Phase -eq 'Production'){
 if(-not $python){Refuse 'Original x64 Python executable unavailable'}
 if($pythonInventory.python_bits -ne 64 -or
    $pythonInventory.runtime_layout_valid -ne $true -or
    $pythonInventory.packages_imported -ne $true){
  Refuse 'Original 64-bit CPython layout or NumPy/SciPy/Protobuf/cryptography imports missing'
 }
 Need-Hash $ApprovedPythonSha256 'Python source image'
 if($localPythonHash -cne $ApprovedPythonSha256){
  Refuse 'Original Python image does not match independently selected source pin'
 }
 Need-DirDestination $RuntimeRoot
 $bundle=Join-Path $PSScriptRoot 'cog_r5_r3_r1_bundle.py'
 Need-File $bundle 'frozen-runtime builder'
 $arguments=@($bundle,'prepare-candidate','--root',$RuntimeRoot,'--repo',$repo,
              '--source-sha',$ExactSourceSha,'--approved-python-sha256',$ApprovedPythonSha256)
 if($Phase -eq 'Production'){
  Need-Hash $ApprovedManifestSha256 'reviewed candidate runtime manifest'
  $arguments[1]='prepare-production'
  $arguments+=@('--approved-manifest-sha256',$ApprovedManifestSha256)
 }
 & $python @arguments
 if($LASTEXITCODE -ne 0){Refuse 'Original full runtime preparation failed; preserve state for review'}
 $manifest=Join-Path $RuntimeRoot 'r3-r1-runtime.manifest'
 $provenance=Join-Path $RuntimeRoot 'r3-r1-runtime-provenance.json'
 Need-File $manifest 'runtime manifest'
 Need-File $provenance 'runtime provenance'
 $m=Digest $manifest
 $p=Digest $provenance
 if($Phase -eq 'Production' -and $m -cne $ApprovedManifestSha256){
  Refuse 'Fresh rebuilt production runtime differs from separately reviewed manifest pin'
 }
 [pscustomobject]@{
  schema='cognitum.ssm.r3r1.personal_runtime_preparation.v1'
  status=if($Phase -eq 'Production'){'FRESH_PRODUCTION_RUNTIME_PREPARED_SIGNING_APPROVAL_PENDING'}else{'CANDIDATE_UNAPPROVED_INDEPENDENT_REVIEW_REQUIRED'}
  exact_source_sha=$ExactSourceSha
  runtime_root=$RuntimeRoot
  manifest_sha256=$m
  provenance_sha256=$p
  may_sign_without_separately_reviewed_hashes=$false
  output_release_authorized=$false
 }|ConvertTo-Json -Compress
 return
}
if(-not $gpg){Refuse 'GnuPG executable unavailable'}
if(-not $keyAvailable){Refuse 'Original selected ECC secret signing key unavailable'}
Need-File $PublicKeyFile 'trusted exported public key'
if(-not $publicKeyMatched){Refuse 'Exported public key does not match selected primary fingerprint'}
if($Phase -eq 'Sign'){
 if(-not $cargo -or -not $nsis){Refuse 'Cargo and NSIS compiler are required for original native build'}
 Need-Hash $ApprovedManifestSha256 'production runtime manifest'
 Need-Hash $ApprovedProvenanceSha256 'production runtime provenance'
 if(-not $RuntimeRoot -or -not [IO.Path]::IsPathRooted($RuntimeRoot) -or
    -not(Test-Path -LiteralPath $RuntimeRoot -PathType Container)){
  Refuse 'Fresh independently approved production runtime root missing'
 }
 if(-not $StageRoot -or -not [IO.Path]::IsPathRooted($StageRoot) -or
    -not(Test-Path -LiteralPath $StageRoot -PathType Container)){
  Refuse 'Precreated protected original staging root missing'
 }
 $builder=Join-Path $PSScriptRoot 'cog-r5-physical02-r3-r1-private-gpg-build.ps1'
 $buildArgs=@{
  ExactSourceSha=$ExactSourceSha
  ApprovedRuntimeRoot=$RuntimeRoot
  ApprovedRuntimeManifestSha256=$ApprovedManifestSha256
  ApprovedRuntimeProvenanceSha256=$ApprovedProvenanceSha256
  GpgPrimaryFingerprint=$fp
  TrustedPublicKeyFile=$PublicKeyFile
  GpgExecutable=$gpg
  MakeNsisExecutable=$nsis
  ProtectedStageRoot=$StageRoot
 }
 & $builder @buildArgs
 return
}
if($Phase -eq 'Verify'){
 if(-not $ReleaseRoot -or -not [IO.Path]::IsPathRooted($ReleaseRoot) -or
    -not(Test-Path -LiteralPath $ReleaseRoot -PathType Container)){
  Refuse 'Existing original private release root missing'
 }
 $verifier=Join-Path $PSScriptRoot 'cog-r5-physical02-r3-r1-private-gpg-verify.ps1'
 $verifyArgs=@{
  ReleaseRoot=$ReleaseRoot
  TrustedPublicKeyFile=$PublicKeyFile
  ExpectedPrimaryFingerprint=$fp
  ExpectedSourceSha=$ExactSourceSha
  GpgExecutable=$gpg
 }
 & $verifier @verifyArgs
 return
}
Refuse 'Unrecognized release phase'
