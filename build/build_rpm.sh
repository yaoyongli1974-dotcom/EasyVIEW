#!/usr/bin/env bash
# ==============================================================================
# 由 PyInstaller onedir 包生成 RPM (Fedora / RHEL / openSUSE) 安装包。
# 前置：rpmbuild（Fedora: `sudo dnf install rpm-build`；RHEL: `sudo yum install rpm-build`）
# 用法：bash build/build_rpm.sh
# 产物：~/rpmbuild/RPMS/x86_64/ivms4200-lite-1.0.0-1.*.x86_64.rpm
# ==============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

APP_NAME="ivms4200-lite"
VERSION="1.0.0"

BUNDLE="$ROOT/dist/IVMS4200-Lite"
if [ ! -x "$BUNDLE/IVMS4200-Lite" ]; then
    echo "错误：未找到 PyInstaller 产物 $BUNDLE/IVMS4200-Lite，请先运行 build/build_linux.sh" >&2
    exit 1
fi

# 准备 rpmbuild 目录结构
RPMBUILD="${RPMBUILD:-$HOME/rpmbuild}"
mkdir -p "$RPMBUILD"/{SOURCES,SPECS,RPMS,SRPMS,BUILD}

# 源 tarball：把 onedir 包打成 %{name}-bundle.tar.gz，解包后为 IVMS4200-Lite/
echo "==> 打包源 tarball -> $RPMBUILD/SOURCES/${APP_NAME}-bundle.tar.gz"
tar -C "$ROOT/dist" -czf "$RPMBUILD/SOURCES/${APP_NAME}-bundle.tar.gz" IVMS4200-Lite

# 其余源文件（desktop / icon）也放入 SOURCES
cp "$ROOT/packaging/ivms4200-lite.desktop" "$RPMBUILD/SOURCES/"
cp "$ROOT/packaging/icon.png" "$RPMBUILD/SOURCES/"

# spec 复制到 SPECS
cp "$ROOT/packaging/rpm/${APP_NAME}.spec" "$RPMBUILD/SPECS/"

echo "==> 运行 rpmbuild"
rpmbuild -bb --define "_topdir $RPMBUILD" "$RPMBUILD/SPECS/${APP_NAME}.spec"

echo "==> 完成："
find "$RPMBUILD/RPMS" -name "${APP_NAME}-${VERSION}-*.rpm" -exec ls -lh {} \;
