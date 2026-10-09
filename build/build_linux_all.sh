#!/usr/bin/env bash
# ==============================================================================
# 一键构建 Linux 全部安装包（PyInstaller onedir + deb + rpm + AppImage）。
#
# 用法：
#   bash build/build_linux_all.sh            # 全部
#   bash build/build_linux_all.sh deb        # 仅 deb
#   bash build/build_linux_all.sh deb rpm    # deb + rpm
#   bash build/build_linux_all.sh appimage   # 仅 AppImage
#
# 前置依赖（Debian/Ubuntu 示例）：
#   sudo apt update
#   sudo apt install -y python3 python3-venv python3-pip libvlc5 libgl1 \
#       libxkbcommon0 libdbus-1-3 libxcb-xinerama0 libfontconfig1 libglib2.0-0 \
#       dpkg-dev rpm patch lintian curl
#   # rpm 构建还需：sudo apt install -y rpm  （提供 rpmbuild）
# ==============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TARGETS=("${@:-deb rpm appimage}")

# 始终先确保 onedir 包存在
if [ ! -x "$ROOT/dist/EasyVIEW/EasyVIEW" ]; then
    echo "==> onedir 包缺失，先构建"
    bash "$ROOT/build/build_linux.sh"
fi

for t in "${TARGETS[@]}"; do
    case "$t" in
        deb)
            echo "########## 构建 .deb ##########"
            bash "$ROOT/build/build_deb.sh"
            ;;
        rpm)
            echo "########## 构建 .rpm ##########"
            bash "$ROOT/build/build_rpm.sh"
            ;;
        appimage)
            echo "########## 构建 AppImage ##########"
            bash "$ROOT/build/build_appimage.sh"
            ;;
        *)
            echo "未知目标: $t (可用: deb rpm appimage)" >&2
            exit 1
            ;;
    esac
done

echo "=========================================="
echo "构建完成，产物位于 dist/ ："
ls -lh "$ROOT/dist/"
echo "=========================================="
