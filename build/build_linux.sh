#!/usr/bin/env bash
# ==============================================================================
# 在 Linux 主机上一键构建 IVMS4200-Lite 的 PyInstaller onedir 包。
# 产物：dist/IVMS4200-Lite/（含主程序与 _internal 依赖集合）
#
# 前置（以 Debian/Ubuntu 为例）：
#   sudo apt update
#   sudo apt install -y python3 python3-venv python3-pip libvlc5 libgl1 \
#       libxkbcommon0 libdbus-1-3 libxcb-xinerama0 libfontconfig1 libglib2.0-0
#
# 用法：
#   bash build/build_linux.sh
# ==============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"

echo "==> [1/3] 创建虚拟环境并安装依赖"
"$PYTHON" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt pyinstaller

echo "==> [2/3] PyInstaller 构建 onedir 包"
python -m PyInstaller build/build_linux.spec --noconfirm --clean --workpath build_pyi

echo "==> [3/3] 完成"
if [ -x "dist/IVMS4200-Lite/IVMS4200-Lite" ]; then
    echo "产物已生成：dist/IVMS4200-Lite/IVMS4200-Lite"
    echo "可继续运行 build/build_deb.sh / build/build_rpm.sh / build/build_appimage.sh 生成安装包"
else
    echo "错误：未找到构建产物 dist/IVMS4200-Lite/IVMS4200-Lite" >&2
    exit 1
fi
