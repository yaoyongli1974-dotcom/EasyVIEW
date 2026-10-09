# -*- mode: python ; coding: utf-8 -*-
# ==============================================================================
# PyInstaller 规格（Windows / Linux 通用，onedir 模式）。
# 用法：python -m PyInstaller build/build.spec --noconfirm --clean
# 产物：dist/EasyVIEW/EasyVIEW(.exe) + _internal/
# VLC 运行时（libvlc）不打进包：Windows 由 CI 复制到 dist/EasyVIEW/vlc/，
# Linux 走系统 libvlc（deb/rpm 声明依赖；AppImage 需宿主已装）。
# ==============================================================================
import os
import sys

# SPECPATH 为 build/ 目录；项目根在上一级
ROOT = os.path.abspath(os.path.join(SPECPATH, os.pardir))

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=["vlc"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="EasyVIEW",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=not sys.platform.startswith("win"),
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="EasyVIEW",
)
