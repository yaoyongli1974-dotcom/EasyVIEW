"""pytest 全局配置：保证项目根目录可导入，GUI 测试走 offscreen 后端。"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# 隔离 QSettings（窗口几何/网格布局），避免测试读写真实用户配置
os.environ.setdefault("XDG_CONFIG_HOME", tempfile.mkdtemp(prefix="easyview-test-cfg-"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
