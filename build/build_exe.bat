@echo off
REM ============================================================
REM Build IVMS4200-Lite Windows executable with PyInstaller
REM Requirements: Python 3.11+ on PATH; (optional) VLC installed
REM Usage: double-click or run from project root
REM ============================================================
setlocal
cd /d "%~dp0\.."

IF NOT EXIST ".venv" (
    python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

python -m PyInstaller build\build.spec --noconfirm --clean

REM Bundle VLC runtime if VLC is installed on this build machine.
REM This makes the output portable (no need for end users to install VLC).
set "VLC_DIR="
if exist "%ProgramFiles%\VideoLAN\VLC\libvlc.dll" set "VLC_DIR=%ProgramFiles%\VideoLAN\VLC"
if exist "%ProgramFiles(x86)%\VideoLAN\VLC\libvlc.dll" set "VLC_DIR=%ProgramFiles(x86)%\VideoLAN\VLC"
if defined VLC_DIR (
    echo Copying VLC runtime from %VLC_DIR% ...
    xcopy "%VLC_DIR%\*" "dist\IVMS4200-Lite\vlc\" /E /I /Y >nul
) else (
    echo WARNING: VLC not found on this machine.
    echo         Copy a VLC install directory into dist\IVMS4200-Lite\vlc\
    echo         before distributing, OR require end users to install VLC.
)

echo.
echo Build complete: dist\IVMS4200-Lite\IVMS4200-Lite.exe
endlocal
