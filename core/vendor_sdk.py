"""厂商 SDK 桥接：通过 ctypes 加载海康 / 大华原生 SDK，调用设备自带的预置巡航轨迹控制。

设计要点
--------
- 真实厂商 SDK（HCNetSDK.dll/.so、dhnetsdk.dll/.so）为 C 接口动态库，需用户自行部署到
  运行环境（放在 PATH / LD_LIBRARY_PATH 或指定目录），本模块只做按需 ctypes 加载。
- 若运行环境无对应 SDK（缺库 / 未授权），加载失败 -> SDK 不可用，调用方自动回退 ONVIF 预置位轮巡。
- 巡航命令枚举值以官方 SDK 头文件为准；此处给出常用取值并标注「需按头文件核对」，
  不同固件/SDK 版本可能微调，上线前请对真实设备验证。

海康 HCNetSDK 巡航（NET_DVR_PTZCruise）
--------------------------------------
  byCruiseCmd 枚举（PTZ_CRUSECmd，常见取值）：
    30 CRS_SET_PRESET   把 byCruisePoint 预置点加入路线 byCruiseRoute
    31 CRS_DEL_PRESET   从路线删除指定预置点
    32 CRS_GOTO_PRESET  开始巡航该路线
    33 CRS_STOP_SEQ     停止巡航
    34 CRS_DEL_SEQ      删除整条巡航路线
  wInput：填充预置点时作为「停留时间(秒)」可选。

大华 SDK 巡航（CLIENT_PTZCruise）
---------------------------------
  dwPTZCruiseCmd 枚举（PTZ_CRUISE_CMD，常见取值，需按 dhnetsdk.h 核对）：
    9  设置预置点（fill）
    10 删除预置点
    11 运行巡航
    12 停止巡航
    13 删除巡航
"""
import ctypes
import platform
from typing import Optional

# ---------------- 海康 SDK 结构（仅提供足够大的写缓冲，不解析字段）----------------
class NET_DVR_DEVICEINFO_V30(ctypes.Structure):
    _fields_ = [("data", ctypes.c_char * 256)]


class NET_DEVICEINFO(ctypes.Structure):
    _fields_ = [("data", ctypes.c_char * 64)]


# 海康巡航命令（需按 HCNetSDK.h 核对）
CRUISE_HK_FILL = 30
CRUISE_HK_DEL = 31
CRUISE_HK_RUN = 32
CRUISE_HK_STOP = 33
CRUISE_HK_CLEAR = 34

# 大华巡航命令（需按 dhnetsdk.h 核对）
CRUISE_DH_FILL = 9
CRUISE_DH_DEL = 10
CRUISE_DH_RUN = 11
CRUISE_DH_STOP = 12
CRUISE_DH_CLEAR = 13


class VendorSDKError(Exception):
    pass


class HikvisionSDK:
    """海康 HCNetSDK 加载器（单例登录会话管理）。"""

    def __init__(self, lib_path: str | None = None):
        self.lib = self._load(lib_path)
        self._init_ok = False
        if self.lib and self._try_init():
            self._init_ok = True
        self._sessions: dict[tuple, int] = {}  # (ip, port) -> lUserID

    def _load(self, lib_path: str | None) -> Optional[ctypes.CDLL]:
        candidates = []
        if lib_path:
            candidates.append(lib_path)
        if platform.system() == "Windows":
            candidates += ["HCNetSDK.dll", "hcnetsdk.dll"]
        else:
            candidates += ["libhcnetsdk.so", "HCNetSDK.so"]
        for c in candidates:
            try:
                return ctypes.CDLL(c)
            except OSError:
                continue
        return None

    def _try_init(self) -> bool:
        try:
            self.lib.NET_DVR_Init.restype = ctypes.c_bool
            self.lib.NET_DVR_Init.argtypes = []
            self.lib.NET_DVR_Cleanup.restype = ctypes.c_bool
            self.lib.NET_DVR_Cleanup.argtypes = []
            self.lib.NET_DVR_Login_V30.restype = ctypes.c_long
            self.lib.NET_DVR_Login_V30.argtypes = [
                ctypes.c_char_p, ctypes.c_ushort, ctypes.c_char_p, ctypes.c_char_p,
                ctypes.POINTER(NET_DVR_DEVICEINFO_V30),
            ]
            self.lib.NET_DVR_Logout.restype = ctypes.c_bool
            self.lib.NET_DVR_Logout.argtypes = [ctypes.c_long]
            self.lib.NET_DVR_PTZCruise.restype = ctypes.c_bool
            self.lib.NET_DVR_PTZCruise.argtypes = [
                ctypes.c_long, ctypes.c_long, ctypes.c_uint, ctypes.c_byte, ctypes.c_byte, ctypes.c_ushort,
            ]
            return bool(self.lib.NET_DVR_Init())
        except Exception as e:
            raise VendorSDKError(f"HCNetSDK 初始化失败：{e}")

    @property
    def available(self) -> bool:
        return self.lib is not None and self._init_ok

    def login(self, ip: str, port: int, username: str, password: str) -> int:
        if not self.available:
            raise VendorSDKError("HCNetSDK 不可用（未部署或初始化失败）")
        key = (ip, port, username)
        if key in self._sessions:
            return self._sessions[key]
        dev = NET_DVR_DEVICEINFO_V30()
        uid = self.lib.NET_DVR_Login_V30(
            ip.encode(), ctypes.c_ushort(port), username.encode(), password.encode(), ctypes.byref(dev)
        )
        if uid < 0:
            raise VendorSDKError(f"海康设备登录失败 ip={ip}:{port}（错误码 {uid}）")
        self._sessions[key] = uid
        return uid

    def logout(self, uid: int):
        if self.lib and uid >= 0:
            self.lib.NET_DVR_Logout(uid)

    def ptz_cruise(self, uid: int, channel: int, cmd: int, route: int, point: int, winput: int = 0):
        if not self.lib:
            raise VendorSDKError("HCNetSDK 不可用")
        ok = self.lib.NET_DVR_PTZCruise(
            ctypes.c_long(uid), ctypes.c_long(channel), ctypes.c_uint(cmd),
            ctypes.c_byte(route), ctypes.c_byte(point), ctypes.c_ushort(winput),
        )
        if not ok:
            raise VendorSDKError("海康 PTZ 巡航指令执行失败")
        return True


class DahuaSDK:
    """大华 SDK 加载器（单例登录会话管理）。"""

    def __init__(self, lib_path: str | None = None):
        self.lib = self._load(lib_path)
        self._init_ok = False
        if self.lib and self._try_init():
            self._init_ok = True
        self._sessions: dict[tuple, int] = {}

    def _load(self, lib_path: str | None) -> Optional[ctypes.CDLL]:
        candidates = []
        if lib_path:
            candidates.append(lib_path)
        if platform.system() == "Windows":
            candidates += ["dhnetsdk.dll", "DHNetSDK.dll"]
        else:
            candidates += ["libdhnetsdk.so", "dhnetsdk.so"]
        for c in candidates:
            try:
                return ctypes.CDLL(c)
            except OSError:
                continue
        return None

    def _try_init(self) -> bool:
        try:
            self.lib.CLIENT_Login.restype = ctypes.c_long
            self.lib.CLIENT_Login.argtypes = [
                ctypes.c_char_p, ctypes.c_ushort, ctypes.c_char_p, ctypes.c_char_p,
                ctypes.POINTER(NET_DEVICEINFO), ctypes.POINTER(ctypes.c_int),
            ]
            self.lib.CLIENT_Logout.restype = ctypes.c_bool
            self.lib.CLIENT_Logout.argtypes = [ctypes.c_long]
            self.lib.CLIENT_PTZCruise.restype = ctypes.c_bool
            self.lib.CLIENT_PTZCruise.argtypes = [
                ctypes.c_long, ctypes.c_int, ctypes.c_uint, ctypes.c_byte, ctypes.c_byte,
                ctypes.c_byte, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint,
            ]
            return True
        except Exception as e:
            raise VendorSDKError(f"dhnetsdk 初始化失败：{e}")

    @property
    def available(self) -> bool:
        return self.lib is not None and self._init_ok

    def login(self, ip: str, port: int, username: str, password: str) -> int:
        if not self.available:
            raise VendorSDKError("dhnetsdk 不可用（未部署或初始化失败）")
        key = (ip, port, username)
        if key in self._sessions:
            return self._sessions[key]
        dev = NET_DEVICEINFO()
        err = ctypes.c_int(0)
        lid = self.lib.CLIENT_Login(
            ip.encode(), ctypes.c_ushort(port), username.encode(), password.encode(),
            ctypes.byref(dev), ctypes.byref(err),
        )
        if lid == 0:
            raise VendorSDKError(f"大华设备登录失败 ip={ip}:{port}（错误码 {err.value}）")
        self._sessions[key] = lid
        return lid

    def logout(self, lid: int):
        if self.lib and lid:
            self.lib.CLIENT_Logout(lid)

    def ptz_cruise(self, lid: int, channel: int, cmd: int, route: int, point: int,
                   cruise_time: int = 0, stop_time: int = 0, waite: int = 0):
        if not self.lib:
            raise VendorSDKError("dhnetsdk 不可用")
        ok = self.lib.CLIENT_PTZCruise(
            ctypes.c_long(lid), ctypes.c_int(channel), ctypes.c_uint(cmd),
            ctypes.c_byte(route), ctypes.c_byte(point), ctypes.c_byte(cruise_time),
            ctypes.c_int(stop_time), ctypes.c_int(waite), None, ctypes.c_uint(0),
        )
        if not ok:
            raise VendorSDKError("大华 PTZ 巡航指令执行失败")
        return True


# ---------------- 单例 ----------------
_hk: HikvisionSDK | None = None
_dh: DahuaSDK | None = None


def get_hikvision_sdk(lib_path: str | None = None) -> HikvisionSDK:
    global _hk
    if _hk is None:
        _hk = HikvisionSDK(lib_path)
    return _hk


def get_dahua_sdk(lib_path: str | None = None) -> DahuaSDK:
    global _dh
    if _dh is None:
        _dh = DahuaSDK(lib_path)
    return _dh
