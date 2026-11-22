!include "x64.nsh"
!include "LogicLib.nsh"
!ifndef COG_PAYLOAD_DIR
 !error "Approved protected successor payload required"
!endif
!ifndef COG_OUTPUT_FILE
 !error "Approved protected successor output required"
!endif

Unicode True
Name "Cognitum SSM - Protected Successor (Grant Denied)"
OutFile "${COG_OUTPUT_FILE}"
InstallDir "$PROGRAMFILES64\Cognitum\SSMProtected"
RequestExecutionLevel admin
SetCompressor /SOLID lzma
ShowInstDetails show

; Never accept an NSIS /D redirect into an existing service or writable path.
; Original owner-accepted no-worker install remains at \Cognitum\SSM.
Function .onInit
 StrCpy $INSTDIR "$PROGRAMFILES64\Cognitum\SSMProtected"
FunctionEnd

Section "Stage protected successor, no service enrollment" SecRequired
 SectionIn RO
 ${IfNot} ${RunningX64}
  Abort "Physical x64 Windows required"
 ${EndIf}
 IfFileExists "$INSTDIR\." 0 +2
  Abort "Existing protected successor must be independently recovered"
 ; Explicitly reject a second protected SCM registration: no overwrite,
 ; no service creation in this package, no test-only qualifier promotion.
 nsExec::ExecToStack '"$SYSDIR\sc.exe" query CognitumSsmProtectedV1'
 Pop $0
 Pop $1
 ${If} $0 == 0
  Abort "Existing protected SCM needs separate authorized reconciliation"
 ${EndIf}
 CreateDirectory "$INSTDIR"
 SetOutPath "$INSTDIR"
 File /oname=cognitum-scm-production.exe "${COG_PAYLOAD_DIR}\cognitum-scm-production.exe"
 SetOutPath "$INSTDIR\runtime"
 File /r "${COG_PAYLOAD_DIR}\runtime\*.*"
 ; AppContainer standard users read original pinned runtime. SYSTEM and
 ; Administrators alone may change installed code. This package does NOT
 ; provision the AppContainer identity, CNG signing key or Lu Core grant.
 ExecWait '"$SYSDIR\icacls.exe" "$INSTDIR" /grant:r *S-1-5-18:(OI)(CI)F *S-1-5-32-544:(OI)(CI)F *S-1-5-32-545:(OI)(CI)RX *S-1-15-2-1:(OI)(CI)RX /T /Q' $0
 StrCmp $0 0 +2
  Abort "Protected successor access policy failed"
 ExecWait '"$SYSDIR\icacls.exe" "$INSTDIR" /grant *S-1-5-18:F *S-1-5-32-544:F *S-1-5-32-545:RX *S-1-15-2-1:RX /T /Q' $0
 StrCmp $0 0 +2
  Abort "Protected successor explicit read grants failed"
 ExecWait '"$SYSDIR\icacls.exe" "$INSTDIR" /setowner *S-1-5-32-544 /T /Q' $0
 StrCmp $0 0 +2
  Abort "Protected successor owner pin failed"
 ExecWait '"$SYSDIR\icacls.exe" "$INSTDIR" /inheritance:r /T /Q' $0
 StrCmp $0 0 +2
  Abort "Untrusted inherited write grants could not be removed"
 DetailPrint "Protected successor source staged, service/worker/Core/output admission DENIED"
SectionEnd
