; ============================================================
; EasyVIEW NSIS Installer Script
; Prerequisite: run build_exe.bat first so dist\EasyVIEW\ exists
; Compile: makensis build\installer.nsi
; Output : dist\EasyVIEW-Setup.exe
; ============================================================
!define APPNAME "EasyVIEW"
!define APPVERSION "0.1.2"
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
  ; 清理旧版安装器可能生成的嵌套目录（旧版误把 EasyVIEW 文件夹本身装进 $INSTDIR）
  RMDir /r "$INSTDIR\EasyVIEW"
  ; 只复制 EasyVIEW 目录的内容到 $INSTDIR，确保 exe 位于 $INSTDIR\EasyVIEW.exe
  File /r "${DISTDIR}\EasyVIEW\*"

  ; 目标不存在时直接报错，避免生成指向错误路径的快捷方式
  IfFileExists "$INSTDIR\${APPNAME}.exe" have_exe
    MessageBox MB_ICONSTOP "安装失败：未找到 $INSTDIR\${APPNAME}.exe"
    Abort
  have_exe:

  CreateDirectory "$SMPROGRAMS\${APPNAME}"
  CreateShortcut "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk" "$INSTDIR\${APPNAME}.exe" "" "$INSTDIR\${APPNAME}.exe" 0
  CreateShortcut "$DESKTOP\${APPNAME}.lnk" "$INSTDIR\${APPNAME}.exe" "" "$INSTDIR\${APPNAME}.exe" 0

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
