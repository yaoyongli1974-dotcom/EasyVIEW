"""SQLite 数据访问层：摄像机配置（含加密密码与自定义流地址）。"""
import sqlite3

from core.config import DB_PATH


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cameras (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            ip          TEXT NOT NULL,
            port        INTEGER NOT NULL DEFAULT 554,
            username    TEXT NOT NULL,
            password    TEXT NOT NULL,        -- 密文（Fernet）
            channel     INTEGER NOT NULL DEFAULT 1,
            stream_type TEXT NOT NULL DEFAULT 'main',
            vendor      TEXT DEFAULT 'hikvision',
            enabled     INTEGER DEFAULT 1,
            stream_uri  TEXT DEFAULT '',      -- 完整流地址（HTTP/HLS 或自定义 RTSP）
            protocol    TEXT DEFAULT 'rtsp',  -- 接入协议 rtsp / http
            channels    INTEGER DEFAULT 1,     -- 设备通道数（NVR 多通道）
            group_name  TEXT DEFAULT '',       -- 所属分组
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    # 兼容旧库：补加 stream_uri / protocol / channels / group_name 列
    cols = [r[1] for r in conn.execute("PRAGMA table_info(cameras)")]
    if "stream_uri" not in cols:
        conn.execute("ALTER TABLE cameras ADD COLUMN stream_uri TEXT DEFAULT ''")
    if "protocol" not in cols:
        conn.execute("ALTER TABLE cameras ADD COLUMN protocol TEXT DEFAULT 'rtsp'")
    if "channels" not in cols:
        conn.execute("ALTER TABLE cameras ADD COLUMN channels INTEGER DEFAULT 1")
    if "group_name" not in cols:
        conn.execute("ALTER TABLE cameras ADD COLUMN group_name TEXT DEFAULT ''")
    conn.commit()
    conn.close()
