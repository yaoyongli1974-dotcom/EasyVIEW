"""全局配置：路径与 LibVLC 启动参数。

打包注意：
- 开发态 DATA_DIR 位于项目内 data/；打包（frozen）后按平台落到用户本地数据目录：
    Windows -> %LOCALAPPDATA%/IVMS4200-Lite
    Linux   -> $XDG_DATA_HOME 或 ~/.local/share/IVMS4200-Lite
    macOS   -> ~/Library/Application Support/IVMS4200-Lite
  保证摄像机配置/录像/截图在重装、单文件解压场景下不丢失。
- 打包后若无系统 VLC，可把 VLC 运行时放到可执行文件同目录的 vlc/ 子目录：
    Windows -> vlc/libvlc.dll + vlc/plugins/
    Linux   -> vlc/libvlc.so  + vlc/plugins/
  本模块会在 import vlc 之前完成定位并注入动态库搜索路径（Windows 用 add_dll_directory，
  Linux 用 LD_LIBRARY_PATH，二者都设 VLC_PLUGIN_PATH）。未捆绑时回退系统已安装的 VLC。
"""
import os
import sys
import json
from pathlib import Path

APP_NAME = "IVMS4200-Lite"
APP_VERSION = "1.0.0"
BASE_DIR = Path(__file__).resolve().parent.parent


def _data_dir() -> Path:
    """数据目录：打包后落到用户本地应用数据，开发态留在项目内。"""
    if getattr(sys, "frozen", False):
        if sys.platform == "win32":
            base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        elif sys.platform == "darwin":
            base = os.path.expanduser("~/Library/Application Support")
        else:  # Linux / 其他 POSIX
            base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
        d = Path(base) / APP_NAME
    else:
        d = BASE_DIR / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


DATA_DIR = _data_dir()
DB_PATH = DATA_DIR / "cameras.db"

# 最多预览路数（IVMS-4200 精简版取 9 路）
MAX_CHANNELS = 9

# 硬件解码模式：用 set_hwnd 把视频画到自建窗口时，Windows 下的硬件解码（DXVA2/d3d11va）
# 常把画面输出到独立 surface 而非我们提供的 HWND，表现为「连接测试正常、预览却黑屏」。
# 因此默认软件解码（none）最稳。可用环境变量覆盖以便排查：
#   set IVMS4200_VLC_HW=none   (默认，最稳，CPU 占用略高)
#   set IVMS4200_VLC_HW=dxva2  (尝试 DXVA2 硬件加速)
#   set IVMS4200_VLC_HW=d3d11va
#   set IVMS4200_VLC_HW=any
# 视频输出模块（vout）：黑屏的真正元凶往往是 Windows 默认 direct3d11/direct3d9 把画面
# 渲染到独立 surface。none 模式默认强制 wingdi（GDI 直绘进 HWND）。若 wingdi 在某台机器
# 仍异常，可用环境变量切换，无需重新打包：
#   set IVMS4200_VLC_VOUT=wingdi     (默认，none 模式下生效)
#   set IVMS4200_VLC_VOUT=directdraw (GDI 的 DX 前身，备选)
#   set IVMS4200_VLC_VOUT=direct3d11  (DXVA 硬件解码时才有意义)
#   set IVMS4200_VLC_VOUT=auto        (完全交给 VLC 自选，不追加 --vout)
def _load_hw_mode() -> str:
    """解码模式优先级：环境变量 IVMS4200_VLC_HW > 持久化设置(settings.json) > 默认 none。"""
    env = os.environ.get("IVMS4200_VLC_HW")
    if env:
        return env
    try:
        p = Path(DATA_DIR) / "settings.json"
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                d = json.load(f)
            m = d.get("hw_mode")
            if m:
                return m
    except Exception:
        pass
    return "none"


def set_hw_mode(mode: str) -> None:
    """把解码模式持久化到 settings.json（下次启动生效）。"""
    p = Path(DATA_DIR) / "settings.json"
    d = {}
    try:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                d = json.load(f)
    except Exception:
        d = {}
    d["hw_mode"] = mode
    with open(p, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


def set_vout_mode(mode: str) -> None:
    """把视频输出模块持久化到 settings.json（下次启动生效）。mode 可为 wingdi/directdraw/direct3d11/auto。"""
    p = Path(DATA_DIR) / "settings.json"
    d = {}
    try:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                d = json.load(f)
    except Exception:
        d = {}
    d["vout_mode"] = mode
    with open(p, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


HW_MODE = _load_hw_mode()


def _load_vout() -> str | None:
    """视频输出模块：环境变量 IVMS4200_VLC_VOUT > 持久化设置(settings.json) > 默认规则。

    - 显式设置（且非 auto）：直接采用，覆盖一切默认。
    - auto：不追加 --vout，完全交给 VLC。
    - 均未设置：none 解码模式默认 wingdi（GDI 直绘进 HWND，根治黑屏）；
      硬件解码模式（dxva2/d3d11va/any）不强制，交给 VLC 自选（DXVA 需 direct3d 呈现）。
    """
    env = (os.environ.get("IVMS4200_VLC_VOUT") or "").strip().lower()
    if env:
        return None if env == "auto" else env
    try:
        p = Path(DATA_DIR) / "settings.json"
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                d = json.load(f)
            vm = (d.get("vout_mode") or "").strip().lower()
            if vm:
                return None if vm == "auto" else vm
    except Exception:
        pass
    return "wingdi" if HW_MODE == "none" else None


VOUT = _load_vout()

# LibVLC 启动参数：面向低延迟 RTSP 预览调优
VLC_ARGS = [
    "--no-audio",
    "--no-snapshot-preview",
    "--no-video-title-show",
    "--rtsp-tcp",
    "--network-caching=300",
    "--live-caching=300",
    "--sout-mux-caching=300",
    "--drop-late-frames",
    "--skip-frames",
    f"--avcodec-hw={HW_MODE}",
    "--verbose=0",
]
# 软件解码（none）模式默认强制 GDI 视频输出（wingdi）：wingdi 直接把画面画进 set_hwnd
# 提供的子窗口 DC，绝不会像 direct3d11/direct3d9 那样把视频输出到独立 surface 而黑屏。
# 硬件解码（dxva2/d3d11va）时则不强制，交由 VLC 自选（DXVA 需要 direct3d 呈现）。
# VOUT 为 None 时不追加 --vout（交给 VLC 默认选择）。
if VOUT:
    VLC_ARGS.append(f"--vout={VOUT}")


def _vlc_lib_name() -> str:
    """不同平台 libvlc 主文件名。"""
    if sys.platform == "win32":
        return "libvlc.dll"
    if sys.platform == "darwin":
        return "libvlc.dylib"
    return "libvlc.so"


def locate_vlc() -> str | None:
    """定位 libvlc 所在目录。

    优先级：
      1. 可执行文件同目录的 vlc/ 子目录（便携/AppImage 捆绑方案，开箱即用）
      2. 系统已安装的 VLC（Windows 走注册表/常见路径；Linux/macOS 走系统动态库搜索）
    返回含 libvlc 主文件的目录路径；找不到返回 None（此时依赖系统已装 VLC）。
    """
    exe_dir = Path(sys.executable).resolve().parent
    lib = _vlc_lib_name()
    # 1) 同目录 vlc/ 子目录
    cand = exe_dir / "vlc"
    if (cand / lib).exists():
        return str(cand)
    # 2) 系统 VLC
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\VideoLAN\VLC") as k:
                val, _ = winreg.QueryValueEx(k, "")
            p = Path(val)
            if (p / lib).exists():
                return str(p)
        except Exception:
            pass
        for p in (
            r"C:\Program Files\VideoLAN\VLC",
            r"C:\Program Files (x86)\VideoLAN\VLC",
        ):
            if (Path(p) / lib).exists():
                return p
    return None


def _inject_vlc_path():
    """在 import vlc 之前调用，把 libvlc 目录注入动态库搜索路径与插件路径。

    - Windows：os.add_dll_directory + PATH
    - Linux/macOS：LD_LIBRARY_PATH（macOS 也可用 DYLD_LIBRARY_PATH，但 SIP 下受限，
      通常系统已装则可省略）
    两种平台都设置 VLC_PLUGIN_PATH 指向 plugins 目录。
    """
    vlc_dir = locate_vlc()
    if not vlc_dir:
        return
    if sys.platform == "win32":
        try:
            # 影响 ctypes.CDLL 的 LoadLibrary 搜索（Windows Python 3.8+）
            os.add_dll_directory(vlc_dir)
        except Exception:
            pass
        # 同时加入 PATH，覆盖更老的加载路径查找逻辑
        os.environ["PATH"] = vlc_dir + os.pathsep + os.environ.get("PATH", "")
    else:
        # Linux/macOS：让动态链接器找到 libvlc.so/.dylib
        os.environ["LD_LIBRARY_PATH"] = (
            vlc_dir + os.pathsep + os.environ.get("LD_LIBRARY_PATH", "")
        )
        if sys.platform == "darwin":
            os.environ["DYLD_LIBRARY_PATH"] = (
                vlc_dir + os.pathsep + os.environ.get("DYLD_LIBRARY_PATH", "")
            )
    os.environ["VLC_PLUGIN_PATH"] = str(Path(vlc_dir) / "plugins")


# 模块级执行：core.config 总是先于 vlc 被导入，确保环境已就绪
_inject_vlc_path()
