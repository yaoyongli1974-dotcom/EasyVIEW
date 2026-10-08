#!/usr/bin/env bash
# ==============================================================================
# 由 PyInstaller onedir 包生成 AppImage（单文件、跨发行版可直接运行）。
# 前置：appimagetool（AppImageKit）。脚本会自动下载到 build/ 目录（若未找到）。
# 用法：bash build/build_appimage.sh
# 产物：dist/IVMS4200-Lite-1.0.0-x86_64.AppImage
# ==============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

APP_NAME="ivms4200-lite"
VERSION="1.0.0"
ARCH="x86_64"

BUNDLE="$ROOT/dist/IVMS4200-Lite"
if [ ! -x "$BUNDLE/IVMS4200-Lite" ]; then
    echo "错误：未找到 PyInstaller 产物 $BUNDLE/IVMS4200-Lite，请先运行 build/build_linux.sh" >&2
    exit 1
fi

# ---- appimagetool ----
APPIMAGETOOL="$ROOT/build/appimagetool"
if [ ! -x "$APPIMAGETOOL" ]; then
    echo "==> 下载 appimagetool"
    curl -fsSL -o "$APPIMAGETOOL" \
        "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x "$APPIMAGETOOL"
fi

# ---- 构造 AppDir ----
APPDIR="$ROOT/build/AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/lib/$APP_NAME" \
         "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/256x256/apps"

echo "==> 复制 PyInstaller 包到 AppDir/usr/lib/$APP_NAME"
cp -r "$BUNDLE/." "$APPDIR/usr/lib/$APP_NAME/"

# AppRun：定位自身目录并启动真实二进制
cat > "$APPDIR/AppRun" <<EOF
#!/bin/sh
HERE="\$(dirname "\$(readlink -f "\$0")")"
export LD_LIBRARY_PATH="\$HERE/usr/lib/$APP_NAME:\$LD_LIBRARY_PATH"
exec "\$HERE/usr/lib/$APP_NAME/$APP_NAME" "\$@"
EOF
chmod +x "$APPDIR/AppRun"

# 桌面入口（AppImage 内 Exec 用应用名，由 AppRun 接管）
cat > "$APPDIR/$APP_NAME.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=IVMS4200-Lite
GenericName=Video Surveillance Client
Comment=Lightweight IVMS-4200-like RTSP video preview client
Exec=$APP_NAME
Icon=$APP_NAME
Terminal=false
Categories=AudioVideo;Video;Network;Monitor;
Keywords=surveillance;camera;RTSP;ONVIF;preview;
StartupNotify=true
EOF
cp "$APPDIR/$APP_NAME.desktop" "$APPDIR/usr/share/applications/$APP_NAME.desktop"
cp "$ROOT/packaging/icon.png" "$APPDIR/$APP_NAME.png"
cp "$ROOT/packaging/icon.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/$APP_NAME.png"

echo "==> 生成 AppImage"
OUT="$ROOT/dist/$APP_NAME-$VERSION-$ARCH.AppImage"
"$APPIMAGETOOL" "$APPDIR" "$OUT"

echo "==> 完成：$OUT"
ls -lh "$OUT"
