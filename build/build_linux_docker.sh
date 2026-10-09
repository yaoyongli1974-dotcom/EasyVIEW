#!/usr/bin/env bash
# ==============================================================================
# 用 Docker 在容器内一键构建全部 Linux 安装包，产物导出到 ./out 。
# 前置：本机已安装 Docker 且可访问 Docker Hub。
# 用法：bash build/build_linux_docker.sh
# ==============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

IMAGE="easyview-builder"
OUT="$ROOT/out"
mkdir -p "$OUT"

echo "==> 构建镜像 $IMAGE（会执行 PyInstaller + deb + rpm + AppImage）"
docker build -t "$IMAGE" .

echo "==> 导出安装包到 $OUT"
docker run --rm -v "$OUT:/out" "$IMAGE"

echo "==> 完成，产物："
ls -lh "$OUT"
