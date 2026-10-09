#!/usr/bin/env bash
# ==============================================================================
# 由 PyInstaller onedir 包生成 RPM (Fedora / RHEL / openSUSE) 安装包。
# 前置：rpmbuild（Fedora: `sudo dnf install rpm-build`；Debian: `sudo apt install rpm`）
# 用法：bash build/build_rpm.sh
# 产物：dist/easyview-<version>-1.<arch>.rpm
# ==============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

APP_NAME="easyview"
VERSION="0.1.1"

BUNDLE="$ROOT/dist/EasyVIEW"
if [ ! -x "$BUNDLE/EasyVIEW" ]; then
    echo "错误：未找到 PyInstaller 产物 $BUNDLE/EasyVIEW，请先运行 build/build_linux.sh" >&2
    exit 1
fi

# 准备 rpmbuild 目录结构
RPMBUILD="${RPMBUILD:-$HOME/rpmbuild}"
mkdir -p "$RPMBUILD"/{SOURCES,SPECS,RPMS,SRPMS,BUILD}

echo "==> 打包源 tarball -> $RPMBUILD/SOURCES/${APP_NAME}-bundle.tar.gz"
tar -C "$ROOT/dist" -czf "$RPMBUILD/SOURCES/${APP_NAME}-bundle.tar.gz" EasyVIEW

cp "$ROOT/packaging/easyview.desktop" "$RPMBUILD/SOURCES/"
cp "$ROOT/packaging/icon.png" "$RPMBUILD/SOURCES/"
cp "$ROOT/packaging/rpm/${APP_NAME}.spec" "$RPMBUILD/SPECS/"

echo "==> 运行 rpmbuild"
rpmbuild -bb --define "_topdir $RPMBUILD" "$RPMBUILD/SPECS/${APP_NAME}.spec"

echo "==> 复制产物到 dist/"
find "$RPMBUILD/RPMS" -name "${APP_NAME}-${VERSION}-*.rpm" -exec cp -v {} "$ROOT/dist/" \;

echo "==> 完成："
ls -lh "$ROOT"/dist/*.rpm
