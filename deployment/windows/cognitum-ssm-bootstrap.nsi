!include "x64.nsh"
!include "LogicLib.nsh"
!ifndef COG_PAYLOAD_DIR
 !error "Approved protected payload location required"
!endif
!ifndef COG_OUTPUT_FILE
 !error "Approved release destination required"
!endif
Unicode True
Name "Cognitum SSM - Production Bootstrap (No Worker)"
OutFile "${COG_OUTPUT_FILE}"
InstallDir "$PROGRAMFILES64\Cognitum\SSM"
RequestExecutionLevel admin
SetCompressor /SOLID lzma
ShowInstDetails show
; Override NSIS /D and any caller-controlled install destination. The x64
; signed release is admitted only at the pinned Program Files location.
Function .onInit
 StrCpy $INSTDIR "$PROGRAMFILES64\Cognitum\SSM"
FunctionEnd

Section "Stage signed Cognitum SSM bootstrap files" SecRequired
 SectionIn RO
 ${IfNot} ${RunningX64}
  Abort "Windows x64 required"
 ${EndIf}
 ; Refuse previous installations and interrupted install trees.
 IfFileExists "$INSTDIR\." 0 +2
  Abort "Existing Cognitum installation requires independent recovery"
 CreateDirectory "$INSTDIR"
 SetOutPath "$INSTDIR"
 File /oname=cognitum-scm-production.exe "${COG_PAYLOAD_DIR}\cognitum-scm-production.exe"
 SetOutPath "$INSTDIR\runtime"
 File /r "${COG_PAYLOAD_DIR}\runtime\*.*"
 ; Separate, signed-only physical enrollment requires external hash pins.
 ; Never create service, Core grant, worker profile or production signer.
 ; Protect the installed source BEFORE reporting success. On failure the
 ; package must remain unadmitted, and independent recovery is required.
 ; Grant the runtime read-only access to Users and AppContainer packages,
 ; but only SYSTEM/Administrators may write. No worker is started here.
 ExecWait '"$SYSDIR\icacls.exe" "$INSTDIR" /grant:r *S-1-5-18:(OI)(CI)F *S-1-5-32-544:(OI)(CI)F *S-1-5-32-545:(OI)(CI)RX *S-1-15-2-1:(OI)(CI)RX /T /Q' $0
 StrCmp $0 0 +2
  Abort "Protected installed file ACL enrollment failed"
 ExecWait '"$SYSDIR\icacls.exe" "$INSTDIR" /setowner *S-1-5-32-544 /T /Q' $0
 StrCmp $0 0 +2
  Abort "Installed code owners could not be pinned to Administrators"
 ExecWait '"$SYSDIR\icacls.exe" "$INSTDIR" /inheritance:r /T /Q' $0
 StrCmp $0 0 +2
  Abort "Inherited write ACLs could not be eliminated"
 ; No service/key creation. Release authority separately verifies all bytes.
 DetailPrint "Protected bootstrap files staged; SCM enrollment still denied"
SectionEnd
