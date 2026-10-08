#!/usr/bin/env bash
# ==============================================================================
# 由 PyInstaller onedir 包生成 Debian/Ubuntu (.deb) 安装包。
# 前置：dpkg-deb（build-essential 或 dpkg-dev）
# 用法：bash build/build_deb.sh
# 产物：dist/ivms4200-lite_1.0.0_amd64.deb
# ==============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

APP_NAME="ivms4200-lite"
VERSION="1.0.0"
ARCH="amd64"

BUNDLE="$ROOT/dist/IVMS4200-Lite"
if [ ! -x "$BUNDLE/IVMS4200-Lite" ]; then
    echo "错误：未找到 PyInstaller 产物 $BUNDLE/IVMS4200-Lite，请先运行 build/build_linux.sh" >&2
    exit 1
fi

STAGE="$ROOT/build/deb_stage"
rm -rf "$STAGE"
mkdir -p "$STAGE/opt/$APP_NAME" \
         "$STAGE/usr/bin" \
         "$STAGE/usr/share/applications" \
         "$STAGE/usr/share/icons/hicolor/256x256/apps" \
         "$STAGE/DEBIAN"

echo "==> 复制 PyInstaller 包到 /opt/$APP_NAME"
cp -r "$BUNDLE/." "$STAGE/opt/$APP_NAME/"

echo "==> 创建 /usr/bin 软链接"
ln -s "/opt/$APP_NAME/$APP_NAME" "$STAGE/usr/bin/$APP_NAME"

echo "==> 安装桌面入口与图标"
cp "$ROOT/packaging/ivms4200-lite.desktop" "$STAGE/usr/share/applications/$APP_NAME.desktop"
cp "$ROOT/packaging/icon.png" "$STAGE/usr/share/icons/hicolor/256x256/apps/$APP_NAME.png"

echo "==> 写入 Debian 控制文件"
cp "$ROOT/packaging/deb/DEBIAN/control" "$STAGE/DEBIAN/control"
cp "$ROOT/packaging/deb/DEBIAN/postinst" "$STAGE/DEBIAN/postinst"
cp "$ROOT/packaging/deb/DEBIAN/prerm" "$STAGE/DEBIAN/prerm"
chmod 0755 "$STAGE/DEBIAN/postinst" "$STAGE/DEBIAN/prerm"
chmod 0755 "$STAGE/opt/$APP_NAME/$APP_NAME"

OUT="$ROOT/dist/${APP_NAME}_${VERSION}_${ARCH}.deb"
echo "==> 构建 $OUT"
dpkg-deb --build --root-owner-group "$STAGE" "$OUT"

echo "==> 完成：$OUT"
ls -lh "$OUT"
