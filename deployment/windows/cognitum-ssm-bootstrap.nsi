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
 DetailPrint "Bootstrap files staged; SCM enrollment still denied"
SectionEnd
