"""多厂商 RTSP 拉流地址模板与自动匹配。"""
from urllib.parse import quote

from core.camera import Camera
from core.onvif_discovery import ONVIF_MANUFACTURERS  # 厂商名 -> 模板 key 映射

# 模板以 lambda 接收 {'channel':int,'stream_type':'main'|'sub'} 返回路径部分
TEMPLATES = {
    "hikvision": {
        "port": 554,
        "url": lambda c: f"/Streaming/Channels/{c['channel']}{'01' if c['stream_type'] == 'main' else '02'}",
        "note": "主码流 101 / 子码流 102",
    },
    "dahua": {
        "port": 554,
        "url": lambda c: f"/cam/realmonitor?channel={c['channel']}&subtype={'0' if c['stream_type'] == 'main' else '1'}",
        "note": "subtype=0 主码流 / 1 子码流",
    },
    "uniview": {  # 宇视（不同固件略有差异，以 ONVIF GetStreamUri 为准）
        "port": 554,
        "url": lambda c: f"/media/video{c['channel']}?stream={c['stream_type']}",
        "note": "宇视格式随固件变化，建议用 ONVIF 拉取权威地址",
    },
    "imou": {  # 乐橙（大华消费级）
        "port": 554,
        "url": lambda c: f"/cam/realmonitor?channel={c['channel']}&subtype={'0' if c['stream_type'] == 'main' else '1'}",
        "note": "同大华",
    },
    "onvif": {  # 通用 ONVIF（实际地址优先来自 GetStreamUri）
        "port": 554,
        "url": lambda c: f"/onvif/stream/{c['channel']}",
        "note": "兜底模板；ONVIF 设备建议用 GetStreamUri 获取真实地址",
    },
}


def build_rtsp(
    vendor: str,
    ip: str,
    port: int,
    username: str,
    password: str,
    channel: int = 1,
    stream_type: str = "main",
) -> str:
    """按厂商模板构造 RTSP 地址。"""
    tpl = TEMPLATES.get(vendor, TEMPLATES["onvif"])
    path = tpl["url"]({"channel": channel, "stream_type": stream_type})
    user = quote(username, safe="")
    pwd = quote(password, safe="")
    return f"rtsp://{user}:{pwd}@{ip}:{port}{path}"


def camera_rtsp_url(cam: Camera) -> str:
    """Camera 统一入口：若已通过 ONVIF 取得权威地址则优先使用。"""
    if getattr(cam, "stream_uri", None):
        return cam.stream_uri
    return build_rtsp(
        cam.vendor, cam.ip, cam.port, cam.username, cam.password,
        cam.channel, cam.stream_type,
    )


def match_vendor(manufacturer: str) -> str:
    """根据 ONVIF 返回的厂商名自动匹配模板 key。"""
    if not manufacturer:
        return "onvif"
    m = manufacturer.lower()
    for name, key in ONVIF_MANUFACTURERS.items():
        if name.lower() in m:
            return key
    return "onvif"
