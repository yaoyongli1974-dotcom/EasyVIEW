; ============================================================
; EasyVIEW NSIS Installer Script
; Prerequisite: run build_exe.bat first so dist\EasyVIEW\ exists
; Compile: makensis build\installer.nsi
; Output : dist\EasyVIEW-Setup.exe
; ============================================================
!define APPNAME "EasyVIEW"
!define APPVERSION "0.1.1"
!define PUBLISHER "EasyVIEW"

; 产物目录：CI 传入绝对路径 /DDISTDIR=...；本地默认相对脚本目录（build/）的 ../dist
!ifndef DISTDIR
  !define DISTDIR "..\dist"
!endif

Name "${APPNAME} ${APPVERSION}"
OutFile "${DISTDIR}\EasyVIEW-Setup.exe"
InstallDir "$PROGRAMFILES64\${APPNAME}"
RequestExecutionLevel admin

!include "MUI2.nsh"
!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_LANGUAGE "SimpChinese"

Section "Main" SEC_MAIN
  SetOutPath "$INSTDIR"
  ; dist\EasyVIEW\* already contains PyInstaller output and (optional) vlc\ runtime
  File /r "${DISTDIR}\EasyVIEW"

  CreateDirectory "$SMPROGRAMS\${APPNAME}"
  CreateShortcut "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk" "$INSTDIR\${APPNAME}.exe"
  CreateShortcut "$DESKTOP\${APPNAME}.lnk" "$INSTDIR\${APPNAME}.exe"

  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "DisplayName" "${APPNAME}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "UninstallString" "$INSTDIR\Uninstall.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "DisplayVersion" "${APPVERSION}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "Publisher" "${PUBLISHER}"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

Section "Uninstall"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir /r "$INSTDIR"
  Delete "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk"
  Delete "$DESKTOP\${APPNAME}.lnk"
  RMDir "$SMPROGRAMS\${APPNAME}"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}"
SectionEnd
