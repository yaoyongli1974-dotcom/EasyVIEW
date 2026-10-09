"""摄像机模型、流地址构造、CRUD（密码加密存储）与连接测试。"""
from dataclasses import dataclass
from typing import Optional

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
    stream_uri: str = ""         # 完整流地址（HTTP/HLS 或自定义 RTSP），优先于模板
    protocol: str = "rtsp"       # 接入协议：rtsp / http(HLS/MJPEG)

    def rtsp_url(self) -> str:
        """统一入口：优先完整流地址，否则按厂商模板构造。"""
        from core import rtsp_templates

        return rtsp_templates.camera_rtsp_url(self)


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
        protocol=(row["protocol"] if "protocol" in row.keys() else "rtsp") or "rtsp",
    )


def add_camera(cam: Camera) -> int:
    vault = get_vault()
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO cameras (name, ip, port, username, password,
                                channel, stream_type, vendor, enabled, stream_uri, protocol)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (cam.name, cam.ip, cam.port, cam.username, vault.encrypt(cam.password),
         cam.channel, cam.stream_type, cam.vendor, int(cam.enabled),
         cam.stream_uri or "", cam.protocol or "rtsp"),
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
           channel=?, stream_type=?, vendor=?, enabled=?, stream_uri=?, protocol=?
           WHERE id=?""",
        (cam.name, cam.ip, cam.port, cam.username, vault.encrypt(cam.password),
         cam.channel, cam.stream_type, cam.vendor, int(cam.enabled),
         cam.stream_uri or "", cam.protocol or "rtsp", cam.id),
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


# ---------------- 连接测试（分类诊断）----------------
def test_connection(cam: Camera, timeout: float = 5.0) -> tuple[bool, str]:
    """连接测试：区分网络超时/连接被拒绝/密码错误/地址错误/无视频流等。"""
    from core.net_probe import diagnose_connection

    code, msg = diagnose_connection(cam, timeout)
    return code == "ok", msg
