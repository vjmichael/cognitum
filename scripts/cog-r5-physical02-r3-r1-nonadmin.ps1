# R3-R1 CI-only external nonadministrator original user and owned AppContainer.
# No SCM secrets, no production issuer, no arbitrary command or fallback.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][ValidateSet('provision','remove')][string]$Mode,
 [Parameter(Mandatory=$true)][string]$FixtureRoot,
 [Parameter(Mandatory=$true)][string]$RuntimeParent,
 [Parameter(Mandatory=$true)][string]$WorkerRoot,
 [string]$PeerPython,
 [string]$EnvFile
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($env:OS -ne 'Windows_NT'){throw 'Genuine Windows required'}
$root=[IO.Path]::GetFullPath($FixtureRoot)
$runtime=[IO.Path]::GetFullPath($RuntimeParent)
$worker=[IO.Path]::GetFullPath($WorkerRoot)
if(@($root,$runtime,$worker)|Select-Object -Unique|Measure-Object|Select-Object -ExpandProperty Count -ErrorAction Stop|Where-Object {$_ -ne 3}){throw 'Host-owned original, frozen runtime and worker I/O cannot be the same path'}
if(!(Test-Path -LiteralPath $root -PathType Container) -or
   !(Test-Path -LiteralPath $runtime -PathType Container) -or
   !(Test-Path -LiteralPath $worker -PathType Container)){
  throw 'Fresh original numerical and frozen-runtime parent directories required'
}
$manifest=Join-Path $root 'r3-r1-external-nonadmin.json'
$credentialFile=Join-Path $env:RUNNER_TEMP 'cognitum-r3-r1-nonadmin-credential.dpapi.xml'
$profileSrc=Join-Path $PWD 'scripts/cog-r5-physical02-r3-r1-user-profile.ps1'
$profileCopy=Join-Path $root 'r3-r1-user-profile.ps1'
$sysPwsh=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$profileName='CognitumSsmR3CiSandboxV1'
if(!(Test-Path $profileSrc -PathType Leaf) -or !(Test-Path $sysPwsh -PathType Leaf)){
 throw 'Approved profile OS helper missing'
}
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class CognitumR3R1PeerBirth {
 [DllImport("kernel32.dll",SetLastError=true)]
 static extern bool GetProcessTimes(IntPtr h,out long created,out long ended,out long kernel,out long user);
 public static ulong Creation(IntPtr h){
   long a,b,c,d;
   if(!GetProcessTimes(h,out a,out b,out c,out d)||a<=0)
     throw new InvalidOperationException("Kernel original peer creation unavailable");
   return (ulong)a;
 }
}
'@
function Run-Profile([System.Management.Automation.PSCredential]$Credential,[string]$Action,[string]$Sid){
 $argsText='-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+$profileCopy+'" -Mode '+$Action+' -Root "'+$root+'" -ExpectedUserSid '+$Sid
 $out=Join-Path $root ('r3r1-profile-'+$Action+'-stdout.txt')
 $err=Join-Path $root ('r3r1-profile-'+$Action+'-stderr.txt')
 if((Test-Path $out) -or (Test-Path $err)){throw 'Refuse reused original nonadministrator profile diagnostic'}
 $process=Start-Process -FilePath $sysPwsh -Credential $Credential -LoadUserProfile -WorkingDirectory $root -ArgumentList $argsText -PassThru -Wait -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err
 if($process.ExitCode -ne 0){
   # The original disposable test profile can emit only its bounded OS
   # refusal category, not its password, environment or credential objects.
   $message=if(Test-Path $err){Get-Content -LiteralPath $err -Raw}else{''}
   if(-not $message -and (Test-Path $out)){$message=Get-Content -LiteralPath $out -Raw}
   if(-not $message){$message='OS helper exited without diagnostic'}
   $message=[regex]::Replace([string]$message,'[^A-Za-z0-9 _.,:;/=+()#-]','_')
   $message=$message.Substring(0,[Math]::Min(350,$message.Length))
   throw ('Nonadmin Windows AppContainer profile '+$Action+' refused: '+$message)
 }
}
function Grant-Exact([string]$path,[string]$sid,[string]$rights){
 & icacls.exe $path /grant ('*'+$sid+':'+$rights) /Q
 if($LASTEXITCODE -ne 0){throw 'Exact native Windows identity ACL refused'}
}
if($Mode -eq 'provision'){
 if(-not $EnvFile -or -not [IO.Path]::IsPathRooted($EnvFile) -or
    (Test-Path $credentialFile) -or (Test-Path $manifest)){
   throw 'Fresh exact external provisioning inputs missing'
 }
 $name='CogR3Ci'+[Guid]::NewGuid().ToString('N').Substring(0,12)
 $user=$null
 $peer=$null
 $cred=$null
 $createdProfile=$false
 try{
   $clear=[Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(48))
   $secure=ConvertTo-SecureString $clear -AsPlainText -Force
   $clear=$null
   $user=New-LocalUser -Name $name -Password $secure -AccountNeverExpires -PasswordNeverExpires -Description 'Cognitum CI-only nonadmin SSM'
   $sid=$user.SID.Value
   if($sid -cnotmatch '^S-1-5-21-[0-9-]+$'){throw 'Dedicated user SID is not local standard user'}
   $members=@(Get-LocalGroupMember -SID ([Security.Principal.SecurityIdentifier]::new('S-1-5-32-544')))
   if($members | Where-Object { $_.SID -and $_.SID.Value -eq $sid }){
     throw 'Dedicated Cognitum source user joined Administrators'
   }
   $cred=[System.Management.Automation.PSCredential]::new(($env:COMPUTERNAME+'\'+$name),$secure)
   $cred|Export-Clixml -Path $credentialFile -Force
   $owner=[Security.Principal.WindowsIdentity]::GetCurrent().User
   $acl=New-Object Security.AccessControl.FileSecurity
   $acl.SetOwner($owner)
   $acl.SetAccessRuleProtection($true,$false)
   $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($owner,'FullControl','Allow'))
   $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
      ([Security.Principal.SecurityIdentifier]::new('S-1-5-18')),'FullControl','Allow'))
   Set-Acl -LiteralPath $credentialFile -AclObject $acl
   Grant-Exact $root $sid '(OI)(CI)M'
   Copy-Item -LiteralPath $profileSrc -Destination $profileCopy -ErrorAction Stop
   Run-Profile $cred 'create' $sid
   $owned=Join-Path $root 'r3-r1-user-owned-profile.json'
   if(!(Test-Path -LiteralPath $owned -PathType Leaf)){
     throw 'Nonadmin original profile did not produce OS package identity'
   }
   $profile=Get-Content -LiteralPath $owned -Raw|ConvertFrom-Json
   if($profile.schema -cne 'cognitum.ssm.r3r1.CI_user_owned_appcontainer.v1' -or
      $profile.owner_user_sid -cne $sid -or
      $profile.owner_is_nonadministrator -ne $true -or
      $profile.no_network_capabilities -ne $true -or
      $profile.appcontainer_sid -cnotmatch '^S-1-15-2-[0-9-]+$'){
     throw 'Foreign original user-owned AppContainer profile'
   }
   $createdProfile=$true
   $package=[string]$profile.appcontainer_sid
   # Only frozen package read/execute; I/O staging is disposable and not an
   # approved installed host journal or signing key.
   foreach($identity in @($sid,$package)){
     Grant-Exact $runtime $identity '(OI)(CI)RX'
   }
   Grant-Exact $root $package '(OI)(CI)M'
   Grant-Exact $worker $sid '(OI)(CI)M'
   Grant-Exact $worker $package '(OI)(CI)M'
   foreach($leaf in @($runtime,$root,$worker)){
     $cursor=Get-Item -LiteralPath $leaf -Force
     while($cursor){
       if(($cursor.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){
         throw 'Original runtime ancestry was reparse redirected'
       }
       if($cursor.Parent){
         foreach($identity in @($sid,$package)){
           Grant-Exact $cursor.Parent.FullName $identity '(RX)'
         }
       }
       $cursor=$cursor.Parent
     }
   }
   if(-not $PeerPython -or -not [IO.Path]::IsPathRooted($PeerPython)){throw 'Externally pinned user source Python required'}
   $python=[IO.Path]::GetFullPath($PeerPython)
   $peer=Start-Process -FilePath $python -Credential $cred -LoadUserProfile -WorkingDirectory $root -ArgumentList '-c "import time;time.sleep(1200)"' -PassThru -WindowStyle Hidden
   Start-Sleep -Milliseconds 150
   $peer.Refresh()
   if($peer.HasExited){throw 'Original nonadmin user peer could not stay alive'}
   $pidPeer=[uint32]$peer.Id
   $native=Get-CimInstance Win32_Process -Filter ("ProcessId="+$pidPeer)
   if(!$native){throw 'OS cannot observe original nonadmin peer process'}
   $who=Invoke-CimMethod -InputObject $native -MethodName GetOwnerSid
   if($who.ReturnValue -ne 0 -or $who.Sid -cne $sid){
     throw 'Native original peer TokenUser not independently pinned'
   }
   $birth=[CognitumR3R1PeerBirth]::Creation($peer.Handle)
   $image=(Get-FileHash -LiteralPath $python -Algorithm SHA256).Hash.ToLowerInvariant()
   [ordered]@{
     schema='cognitum.ssm.r3r1.external_nonadministrator_CI_profile.v1'
     account_name=$name
     user_sid=$sid
     profile=$profileName
     profile_sid=$package
     original_peer_pid=$pidPeer
     original_peer_birth=$birth
     original_peer_image_sha256=$image
     user_is_member_of_Administrators=$false
     AppContainer_created_as_own_nonadmin_user=$true
     no_network_capabilities=$true
     independently_approved_installed_publisher=$false
     original_Core_grant=$false
   }|ConvertTo-Json -Depth 4|Set-Content -LiteralPath $manifest -Encoding utf8
   $values=@(
     "COG_R3_CI_PEER_PID=$pidPeer",
     "COG_R3_CI_PEER_BIRTH=$birth",
     "COG_R3_CI_PEER_SID=$sid",
     "COG_R3_CI_PEER_IMAGE_SHA256=$image",
     "COG_R3_CI_PROFILE=$profileName",
     "COG_R3_CI_APP_SID=$package",
     ("COG_R3_CI_APP_WITNESS="+(Join-Path $root 'r3-original-appcontainer-witness.json'))
   )
   [IO.File]::AppendAllText($EnvFile,[string]::Join([Environment]::NewLine,$values)+[Environment]::NewLine)
   Write-Host 'PASS_CI_DEDICATED_NONADMIN_USER_OWNS_NATIVE_APP_CONTAINER_PROFILE'
 }catch{
   if($peer -and -not $peer.HasExited){try{Stop-Process -Id $peer.Id -Force}catch{}}
   if($createdProfile -and $cred){try{Run-Profile $cred 'delete' $sid}catch{}}
   if($user){try{Remove-LocalUser -Name $name}catch{}}
   if(Test-Path $credentialFile){Remove-Item -LiteralPath $credentialFile -Force}
   throw
 }
}else{
 if(!(Test-Path -LiteralPath $manifest -PathType Leaf) -or
    !(Test-Path -LiteralPath $credentialFile -PathType Leaf)){
   throw 'Original user/DPAPI key missing, cannot remove unrelated account'
 }
 $rec=Get-Content -LiteralPath $manifest -Raw|ConvertFrom-Json
 if($rec.schema -cne 'cognitum.ssm.r3r1.external_nonadministrator_CI_profile.v1' -or
    $rec.account_name -cnotmatch '^CogR3Ci[0-9a-f]{12}$' -or
    $rec.user_sid -cnotmatch '^S-1-5-21-[0-9-]+$' -or
    $rec.user_is_member_of_Administrators -ne $false){
   throw 'Foreign production or stale local account must not be deleted'
 }
 $user=Get-LocalUser -Name $rec.account_name -ErrorAction Stop
 if($user.SID.Value -cne $rec.user_sid){throw 'Original account SID was recycled'}
 $cred=Import-Clixml -Path $credentialFile
 if($cred -isnot [System.Management.Automation.PSCredential]){
   throw 'Original runner DPAPI key cannot open nonadmin account'
 }
 $original=Get-Process -Id ([uint32]$rec.original_peer_pid) -ErrorAction SilentlyContinue
 if($original){
   if([CognitumR3R1PeerBirth]::Creation($original.Handle) -ne [ulong]$rec.original_peer_birth){
     throw 'Original peer PID was recycled, refusing unrelated termination'
   }
   Stop-Process -Id $original.Id -Force -ErrorAction Stop
 }
 Run-Profile $cred 'delete' ([string]$rec.user_sid)
 Remove-LocalUser -Name $rec.account_name -ErrorAction Stop
 Remove-Item -LiteralPath $credentialFile -Force
 Remove-Item -LiteralPath $manifest -Force
 Write-Host 'PASS_CI_ORIGINAL_NONADMIN_USER_PROFILE_DPAPI_CREDENTIAL_REVOKED'
}
