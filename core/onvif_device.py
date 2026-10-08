"""ONVIF 设备客户端封装：配网信息、RTSP 流地址、PTZ 云台控制。

依赖 onvif-zeep（ONVIFCamera）。首次使用会从设备/官方拉取 WSDL，需联网。
所有调用均做异常兜底，设备不支持某项能力时返回空或抛 RuntimeError。
"""
import threading
from typing import Optional

from core.onvif_discovery import ONVIF_MANUFACTURERS


class OnvifDevice:
    def __init__(self, ip: str, port: int, username: str, password: str):
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self._cam = None
        self._profile_token: Optional[str] = None
        self._cruise_timer: Optional[threading.Timer] = None
        self._cruise_presets: list = []
        self._cruise_idx = 0

    # ---------------- 连接 ----------------
    def connect(self):
        if self._cam is None:
            from onvif import ONVIFCamera

            self._cam = ONVIFCamera(self.ip, self.port, self.username, self.password)
        return self._cam

    def _ensure_profile(self) -> str:
        if self._profile_token is None:
            profiles = self.connect().media.GetProfiles()
            self._profile_token = profiles[0].token
        return self._profile_token

    # ---------------- 配网信息 ----------------
    def device_info(self) -> dict:
        info = self.connect().devicemgmt.GetDeviceInformation()
        return {
            "manufacturer": getattr(info, "Manufacturer", ""),
            "model": getattr(info, "Model", ""),
            "firmware": getattr(info, "FirmwareVersion", ""),
        }

    def vendor_key(self) -> str:
        """根据设备厂商名匹配 rtsp 模板 key。"""
        try:
            manu = self.device_info()["manufacturer"]
        except Exception:
            return "onvif"
        return ONVIF_MANUFACTURERS.get(manu.strip().lower(), "onvif")

    def stream_uri(self) -> str:
        """获取该设备主码流的权威 RTSP 地址（优先于模板）。"""
        token = self._ensure_profile()
        res = self.connect().media.GetStreamUri(
            {
                "StreamSetup": {"Stream": "RTP-Unicast", "Transport": {"Protocol": "RTSP"}},
                "ProfileToken": token,
            }
        )
        return res.Uri

    # ---------------- PTZ 能力 ----------------
    def ptz_supported(self) -> bool:
        try:
            self._ensure_profile()
            return self.connect().ptz.GetStatus({"ProfileToken": self._profile_token}) is not None
        except Exception:
            return False

    def move_absolute(self, pan: float, tilt: float, zoom: float = 0.0):
        token = self._ensure_profile()
        self.connect().ptz.AbsoluteMove(
            {
                "ProfileToken": token,
                "Position": {"PanTilt": {"x": pan, "y": tilt}, "Zoom": {"x": zoom}},
            }
        )

    def move_relative(self, pan: float, tilt: float, zoom: float = 0.0):
        token = self._ensure_profile()
        self.connect().ptz.RelativeMove(
            {
                "ProfileToken": token,
                "Translation": {"PanTilt": {"x": pan, "y": tilt}, "Zoom": {"x": zoom}},
            }
        )

    def move_continuous(self, vx: float, vy: float, vz: float = 0.0, timeout: float = 0.5):
        """连续转动：速度分量 [-1,1]，timeout 秒后自动停止。"""
        token = self._ensure_profile()
        self.stop()
        self.connect().ptz.ContinuousMove(
            {
                "ProfileToken": token,
                "Velocity": {"PanTilt": {"x": vx, "y": vy}, "Zoom": {"x": vz}},
            }
        )
        if timeout and timeout > 0:
            threading.Timer(timeout, self.stop).start()

    def stop(self):
        if self._cam is None or self._profile_token is None:
            return
        try:
            self.connect().ptz.Stop({"ProfileToken": self._profile_token})
        except Exception:
            pass

    # ---------------- 预置位 ----------------
    def get_presets(self) -> list[dict]:
        token = self._ensure_profile()
        try:
            presets = self.connect().ptz.GetPresets({"ProfileToken": token})
        except Exception:
            return []
        return [{"token": p.token, "name": getattr(p, "Name", p.token)} for p in presets]

    def goto_preset(self, preset_token: str):
        token = self._ensure_profile()
        self.connect().ptz.GotoPreset({"ProfileToken": token, "PresetToken": preset_token})

    def set_preset(self, name: str = "") -> Optional[str]:
        token = self._ensure_profile()
        kwargs = {"ProfileToken": token}
        if name:
            kwargs["PresetName"] = name
        try:
            return self.connect().ptz.SetPreset(kwargs)
        except Exception:
            return None

    def remove_preset(self, preset_token: str):
        token = self._ensure_profile()
        try:
            self.connect().ptz.RemovePreset({"ProfileToken": token, "PresetToken": preset_token})
        except Exception:
            pass

    # ---------------- 巡航（预置位轮巡）----------------
    def start_cruise(self, preset_tokens: list, interval: float = 5.0):
        self.stop_cruise()
        self._cruise_presets = list(preset_tokens)
        self._cruise_idx = 0
        self._cruise_interval = interval

        def _tick():
            if not self._cruise_presets:
                return
            tok = self._cruise_presets[self._cruise_idx % len(self._cruise_presets)]
            self.goto_preset(tok)
            self._cruise_idx += 1
            self._cruise_timer = threading.Timer(self._cruise_interval, _tick)
            self._cruise_timer.daemon = True
            self._cruise_timer.start()

        _tick()

    def stop_cruise(self):
        if self._cruise_timer:
            self._cruise_timer.cancel()
            self._cruise_timer = None
        self.stop()

    @property
    def is_cruising(self) -> bool:
        return self._cruise_timer is not None
