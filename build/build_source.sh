#!/usr/bin/env bash
# ==============================================================================
# 生成源码包（当前 HEAD 的 git 归档）。
# 用法：bash build/build_source.sh
# 产物：dist/EasyVIEW-<version>-src.tar.gz
# ==============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VERSION="$(sed -n 's/^APP_VERSION = "\(.*\)"/\1/p' core/config.py)"
mkdir -p dist
OUT="dist/EasyVIEW-${VERSION}-src.tar.gz"

git archive --format=tar.gz --prefix="EasyVIEW-${VERSION}/" -o "$OUT" HEAD
echo "==> 完成：$OUT"
ls -lh "$OUT"
