"""设备原生巡航轨迹：本地配置持久化 + 控制器工厂（厂商 SDK / ONVIF 兜底）。

触发方式
--------
- 上传到设备：用户在 PTZ 面板「原生巡航」组配置轨迹点（预置位号/停留/速度）后点「上传到设备」，
  fill_cruise_track 逐点下发到设备，设备端存储该巡航路线。
- 运行/停止/清除：按钮直接调用设备原生巡航指令，由设备自身执行轨迹控制（不经客户端轮询）。

调用接口
--------
- 海康：HikvisionSDK.ptz_cruise(uid, channel, cmd, route, point, winput)
- 大华：DahuaSDK.ptz_cruise(lid, channel, cmd, route, point, cruise_time, ...)
- 兜底：OnvifDevice 预置位轮巡（start_cruise/stop_cruise）

参数配置（CruiseTrack.points）
----------------------------
- preset_no：设备原生预置位编号（1..N，取决于设备）
- dwell：该点停留时间（秒），海康映射 wInput，大华映射 cruise_time
- speed：转动速度（1..N），大华可映射 stop_time；海康按全局速度另走 PTZ 速度

数据存储
--------
- 文件：轨迹配置仅保存在设备端（设备原生能力），同时本地表 cruise_tracks 存一份镜像，
  用于下次加载与前端展示。cruise_tracks 表（camera_id, track_no, name, points_json）。
"""
import json
from dataclasses import asdict, dataclass
from typing import Optional

from core.database import get_conn
from core.vendor_sdk import (
    CRUISE_DH_CLEAR,
    CRUISE_DH_DEL,
    CRUISE_DH_FILL,
    CRUISE_DH_RUN,
    CRUISE_DH_STOP,
    CRUISE_HK_CLEAR,
    CRUISE_HK_DEL,
    CRUISE_HK_FILL,
    CRUISE_HK_RUN,
    CRUISE_HK_STOP,
    DahuaSDK,
    HikvisionSDK,
    get_dahua_sdk,
    get_hikvision_sdk,
)


@dataclass
class CruisePoint:
    preset_no: int = 1
    dwell: int = 5
    speed: int = 4


@dataclass
class CruiseTrack:
    id: Optional[int] = None
    camera_id: int = 0
    track_no: int = 1
    name: str = ""
    points: list = None  # list[CruisePoint]

    def __post_init__(self):
        if self.points is None:
            self.points = []

    def points_to_json(self) -> str:
        return json.dumps([asdict(p) for p in self.points], ensure_ascii=False)

    @staticmethod
    def points_from_json(text: str) -> list:
        try:
            return [CruisePoint(**d) for d in json.loads(text or "[]")]
        except Exception:
            return []


# ---------------- DB 访问 ----------------
def add_cruise_track(track: CruiseTrack) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO cruise_tracks (camera_id, track_no, name, points_json) VALUES (?,?,?,?)",
        (track.camera_id, track.track_no, track.name, track.points_to_json()),
    )
    tid = cur.lastrowid
    conn.commit()
    conn.close()
    return tid


def update_cruise_track(track: CruiseTrack):
    conn = get_conn()
    conn.execute(
        "UPDATE cruise_tracks SET track_no=?, name=?, points_json=? WHERE id=?",
        (track.track_no, track.name, track.points_to_json(), track.id),
    )
    conn.commit()
    conn.close()


def list_cruise_tracks(camera_id: int) -> list[CruiseTrack]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM cruise_tracks WHERE camera_id=? ORDER BY track_no", (camera_id,)).fetchall()
    conn.close()
    out = []
    for r in rows:
        t = CruiseTrack(
            id=r["id"], camera_id=r["camera_id"], track_no=r["track_no"],
            name=r["name"] or "", points=CruiseTrack.points_from_json(r["points_json"]),
        )
        out.append(t)
    return out


def delete_cruise_track(track_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM cruise_tracks WHERE id=?", (track_id,))
    conn.commit()
    conn.close()


def get_cruise_track_by_id(track_id: int) -> CruiseTrack | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM cruise_tracks WHERE id=?", (track_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return CruiseTrack(
        id=row["id"], camera_id=row["camera_id"], track_no=row["track_no"],
        name=row["name"] or "", points=CruiseTrack.points_from_json(row["points_json"]),
    )


# ---------------- 控制器接口 ----------------
class BaseCruiseController:
    def __init__(self, camera):
        self.camera = camera
        self._uid = None

    @property
    def backend(self) -> str:
        raise NotImplementedError

    def available(self) -> bool:
        raise NotImplementedError

    def login(self):
        raise NotImplementedError

    def fill_cruise_track(self, route: int, points: list):
        raise NotImplementedError

    def run_cruise(self, route: int):
        raise NotImplementedError

    def stop_cruise(self, route: int):
        raise NotImplementedError

    def clear_cruise(self, route: int):
        raise NotImplementedError

    def logout(self):
        pass


class HikvisionCruiseController(BaseCruiseController):
    def __init__(self, camera, sdk: HikvisionSDK | None = None):
        super().__init__(camera)
        self.sdk = sdk or get_hikvision_sdk()

    @property
    def backend(self) -> str:
        return "hikvision"

    def available(self) -> bool:
        return self.sdk.available

    def login(self):
        if self._uid is None:
            self._uid = self.sdk.login(
                self.camera.ip, self.camera.port, self.camera.username, self.camera.password
            )
        return self._uid

    def fill_cruise_track(self, route: int, points: list):
        uid = self.login()
        ch = self.camera.channel
        for p in points:
            # wInput = 停留时间（秒）
            self.sdk.ptz_cruise(uid, ch, CRUISE_HK_FILL, route, p.preset_no, p.dwell)

    def run_cruise(self, route: int):
        self.sdk.ptz_cruise(self.login(), self.camera.channel, CRUISE_HK_RUN, route, 0, 0)

    def stop_cruise(self, route: int):
        self.sdk.ptz_cruise(self.login(), self.camera.channel, CRUISE_HK_STOP, route, 0, 0)

    def clear_cruise(self, route: int):
        self.sdk.ptz_cruise(self.login(), self.camera.channel, CRUISE_HK_CLEAR, route, 0, 0)

    def logout(self):
        if self._uid is not None:
            self.sdk.logout(self._uid)
            self._uid = None


class DahuaCruiseController(BaseCruiseController):
    def __init__(self, camera, sdk: DahuaSDK | None = None):
        super().__init__(camera)
        self.sdk = sdk or get_dahua_sdk()

    @property
    def backend(self) -> str:
        return "dahua"

    def available(self) -> bool:
        return self.sdk.available

    def login(self):
        if self._uid is None:
            self._uid = self.sdk.login(
                self.camera.ip, self.camera.port, self.camera.username, self.camera.password
            )
        return self._uid

    def fill_cruise_track(self, route: int, points: list):
        lid = self.login()
        ch = self.camera.channel
        for p in points:
            # cruise_time=停留秒, stop_time=速度档
            self.sdk.ptz_cruise(lid, ch, CRUISE_DH_FILL, route, p.preset_no,
                                cruise_time=p.dwell, stop_time=p.speed)

    def run_cruise(self, route: int):
        self.sdk.ptz_cruise(self.login(), self.camera.channel, CRUISE_DH_RUN, route, 0)

    def stop_cruise(self, route: int):
        self.sdk.ptz_cruise(self.login(), self.camera.channel, CRUISE_DH_STOP, route, 0)

    def clear_cruise(self, route: int):
        self.sdk.ptz_cruise(self.login(), self.camera.channel, CRUISE_DH_CLEAR, route, 0)

    def logout(self):
        if self._uid is not None:
            self.sdk.logout(self._uid)
            self._uid = None


class GenericCruiseController(BaseCruiseController):
    """ONVIF 预置位轮巡兜底：当运行环境无厂商 SDK 时仍可用。"""

    def __init__(self, camera):
        super().__init__(camera)
        self._dev = None

    @property
    def backend(self) -> str:
        return "onvif"

    def available(self) -> bool:
        return True

    def _device(self):
        if self._dev is None:
            from core.onvif_device import OnvifDevice

            self._dev = OnvifDevice(self.camera.ip, self.camera.port, self.camera.username, self.camera.password)
        return self._dev

    def login(self):
        return self._device()

    def fill_cruise_track(self, route: int, points: list):
        # ONVIF 无原生「巡航路线」概念：按预置位号逐个在设备上创建预置位作为镜像
        dev = self._device()
        for p in points:
            dev.set_preset(f"P{p.preset_no}")

    def run_cruise(self, route: int):
        dev = self._device()
        tokens = [p["token"] for p in dev.get_presets()]
        dev.start_cruise(tokens, interval=5)

    def stop_cruise(self, route: int):
        self._device().stop_cruise()

    def clear_cruise(self, route: int):
        dev = self._device()
        for p in dev.get_presets():
            dev.remove_preset(p["token"])

    def logout(self):
        pass


def get_cruise_controller(camera):
    """根据厂商选择原生 SDK 控制器；无 SDK 时回退 ONVIF。"""
    v = (camera.vendor or "onvif").lower()
    if v == "hikvision":
        c = HikvisionCruiseController(camera)
        if c.available():
            return c
    elif v == "dahua":
        c = DahuaCruiseController(camera)
        if c.available():
            return c
    return GenericCruiseController(camera)
