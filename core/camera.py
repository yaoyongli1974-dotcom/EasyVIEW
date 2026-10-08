"""摄像机模型、RTSP 地址构造、CRUD（密码加密存储）与连接测试。"""
import socket
import threading
from dataclasses import asdict, dataclass
from typing import Optional

import vlc

from core.config import VLC_ARGS
from core.crypto import get_vault
from core.database import get_conn


@dataclass
class Camera:
    id: Optional[int] = None
    name: str = ""
    ip: str = ""
    port: int = 554
    username: str = ""
    password: str = ""          # 内存中始终为明文；入库时加密
    channel: int = 1
    stream_type: str = "main"   # main=主码流, sub=子码流
    vendor: str = "hikvision"
    enabled: bool = True
    stream_uri: str = ""         # ONVIF 取得的权威 RTSP（含鉴权），优先于模板

    def rtsp_url(self) -> str:
        """统一入口：优先 ONVIF 权威地址，否则按厂商模板构造。"""
        from core import rtsp_templates

        return rtsp_templates.camera_rtsp_url(self)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------- CRUD（密码入库即加密）----------------
def _row_to_camera(row) -> Camera:
    vault = get_vault()
    return Camera(
        id=row["id"],
        name=row["name"],
        ip=row["ip"],
        port=row["port"],
        username=row["username"],
        password=vault.decrypt(row["password"]),  # 出库即解密到内存
        channel=row["channel"],
        stream_type=row["stream_type"],
        vendor=row["vendor"],
        enabled=bool(row["enabled"]),
        stream_uri=row["stream_uri"] or "",
    )


def add_camera(cam: Camera) -> int:
    vault = get_vault()
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO cameras (name, ip, port, username, password,
                                channel, stream_type, vendor, enabled, stream_uri)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (cam.name, cam.ip, cam.port, cam.username, vault.encrypt(cam.password),
         cam.channel, cam.stream_type, cam.vendor, int(cam.enabled), cam.stream_uri or ""),
    )
    cid = cur.lastrowid
    conn.commit()
    conn.close()
    return cid


def update_camera(cam: Camera) -> None:
    vault = get_vault()
    conn = get_conn()
    conn.execute(
        """UPDATE cameras SET name=?, ip=?, port=?, username=?, password=?,
           channel=?, stream_type=?, vendor=?, enabled=?, stream_uri=? WHERE id=?""",
        (cam.name, cam.ip, cam.port, cam.username, vault.encrypt(cam.password),
         cam.channel, cam.stream_type, cam.vendor, int(cam.enabled), cam.stream_uri or "", cam.id),
    )
    conn.commit()
    conn.close()


def delete_camera(cid: int) -> None:
    conn = get_conn()
    conn.execute("DELETE FROM cameras WHERE id=?", (cid,))
    conn.commit()
    conn.close()


def list_cameras() -> list[Camera]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM cameras ORDER BY id").fetchall()
    conn.close()
    return [_row_to_camera(r) for r in rows]


def get_camera(cid: int) -> Optional[Camera]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM cameras WHERE id=?", (cid,)).fetchone()
    conn.close()
    return _row_to_camera(row) if row else None


# ---------------- 连接测试（两阶段探测）----------------
def test_connection(cam: Camera, timeout: float = 4.0) -> tuple[bool, str]:
    """先测 TCP 端口可达，再测 RTSP 流能否被 VLC 拉起播放。"""
    try:
        with socket.create_connection((cam.ip, cam.port), timeout=timeout):
            pass
    except OSError as e:
        return False, f"TCP 连接失败（{cam.ip}:{cam.port}）：{e}"

    result = {"playing": False}
    done = threading.Event()
    instance = vlc.Instance("--no-audio", "--rtsp-tcp", "--network-caching=300")
    media = instance.media_new(cam.rtsp_url())
    media.add_option(f"timeout={int(timeout * 1000)}")
    player = instance.media_player_new()
    player.set_media(media)

    def on_playing(_event):
        result["playing"] = True
        done.set()

    def on_error(_event):
        done.set()

    em = player.event_manager()
    em.event_attach(vlc.EventType.MediaPlayerPlaying, on_playing)
    em.event_attach(vlc.EventType.MediaPlayerEncounteredError, on_error)

    player.play()
    done.wait(timeout)
    player.stop()
    instance.release()

    if result["playing"]:
        return True, "连接成功，视频流可播放"
    return False, "TCP 可达但 RTSP 拉流失败（请检查用户名/密码/码流类型是否匹配）"
