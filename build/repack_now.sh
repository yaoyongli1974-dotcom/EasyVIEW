#!/usr/bin/env bash
# 重打包 EasyVIEW（onedir，不含 NSIS）：
# 用唯一 distpath 避免 PyInstaller 清空已有目录被沙箱 safe-delete 拦截；
# 路径一律用 Windows 盘符形式（D:/...）以兼容 Windows 版 Python 与 git-bash。
set -e
cd /d/workbuddy/4200/easyview
PY="C:/Users/h/.workbuddy/binaries/python/versions/3.13.12/python.exe"
BACKUP="D:/workbuddy/4200/easyview/_vlc_backup"
DIST_TAG="$(date +%m%d_%H%M%S)"
OUT="D:/workbuddy/4200/easyview/dist_$DIST_TAG"

echo "[1] ensure VLC runtime backup"
if [ ! -f "$BACKUP/libvlc.dll" ]; then
  mkdir -p "$BACKUP"
  cp -r dist/EasyVIEW/vlc "$BACKUP"
fi
echo "    vlc backup: $([ -f "$BACKUP/libvlc.dll" ] && echo ok || echo MISSING)"

echo "[2] venv + deps (reuse if already built)"
if [ ! -f .venv/Scripts/pyinstaller.exe ]; then
  "$PY" -m venv .venv
  source .venv/Scripts/activate
  pip install --upgrade pip >/dev/null 2>&1 || true
  pip install -r requirements.txt pyinstaller 2>/dev/null || pip install -r requirements.txt pyinstaller --proxy http://127.0.0.1:7897
else
  source .venv/Scripts/activate
fi

echo "[3] PyInstaller build -> $OUT (fresh dir, --clean to force re-analysis so source edits actually ship)"
python -m PyInstaller build/build.spec --noconfirm --clean --distpath "$OUT"

echo "[4] restore VLC runtime"
mkdir -p "$OUT/EasyVIEW/vlc"
cp -r "$BACKUP/." "$OUT/EasyVIEW/vlc/"

echo "[5] verify"
ls -lh "$OUT/EasyVIEW/EasyVIEW.exe"
echo "REPACK_DONE OUT=$OUT"
