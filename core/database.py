"""SQLite 数据访问层：摄像机配置（含加密密码与 ONVIF 流地址）与录像索引。"""
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
            password    TEXT NOT NULL,   -- 密文（Fernet）
            channel     INTEGER NOT NULL DEFAULT 1,
            stream_type TEXT NOT NULL DEFAULT 'main',
            vendor      TEXT DEFAULT 'hikvision',
            enabled     INTEGER DEFAULT 1,
            stream_uri  TEXT DEFAULT '',  -- ONVIF 取得的权威 RTSP（含鉴权）
            protocol    TEXT DEFAULT 'rtsp',  -- 接入协议 rtsp/onvif/http
            channels    INTEGER DEFAULT 1,     -- 设备通道数（NVR）
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

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS recordings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            camera_id   INTEGER NOT NULL,
            path        TEXT NOT NULL,
            start_time  REAL NOT NULL,
            end_time    REAL NOT NULL,
            size        INTEGER DEFAULT 0,
            trigger     TEXT DEFAULT 'manual',  -- manual / schedule / motion
            plan_id     INTEGER DEFAULT 0
        )
        """
    )
    # 兼容旧库：补加 trigger / plan_id 列
    rcols = [r[1] for r in conn.execute("PRAGMA table_info(recordings)")]
    if "trigger" not in rcols:
        conn.execute("ALTER TABLE recordings ADD COLUMN trigger TEXT DEFAULT 'manual'")
    if "plan_id" not in rcols:
        conn.execute("ALTER TABLE recordings ADD COLUMN plan_id INTEGER DEFAULT 0")

    # 截图抓拍索引
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS snapshots (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            camera_id   INTEGER NOT NULL,
            taken_at    REAL NOT NULL,
            path        TEXT NOT NULL,
            width       INTEGER DEFAULT 0,
            height      INTEGER DEFAULT 0,
            label       TEXT DEFAULT ''
        )
        """
    )

    # 设备原生巡航轨迹（上传到设备 + 本地配置）
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cruise_tracks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            camera_id   INTEGER NOT NULL,
            track_no    INTEGER NOT NULL,
            name        TEXT DEFAULT '',
            points_json TEXT DEFAULT '[]',  -- [{preset_no, dwell, speed}, ...]
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # 录像计划：定时段 或 移动侦测触发
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS recording_plans (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            camera_id     INTEGER NOT NULL,
            name          TEXT DEFAULT '',
            enabled       INTEGER DEFAULT 1,
            mode          TEXT NOT NULL,           -- 'schedule' | 'motion'
            weekdays      INTEGER DEFAULT 127,      -- 位掩码 bit0=周一..bit6=周日
            start_min     INTEGER DEFAULT 0,        -- 起始分钟（0..1439）
            end_min       INTEGER DEFAULT 1439,     -- 结束分钟
            segment_seconds INTEGER DEFAULT 0,
            stream_type   TEXT DEFAULT 'sub',
            -- 移动侦测参数
            sensitivity   INTEGER DEFAULT 5,        -- 1..10
            min_consecutive INTEGER DEFAULT 3,
            pre_seconds   INTEGER DEFAULT 3,
            post_seconds  INTEGER DEFAULT 10,
            min_duration  INTEGER DEFAULT 15,
            created_at    TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()
    # 启动期自愈：检测 cameras 表中解密失败的密文并清空（保留元数据）
    try:
        from core.crypto_recovery import recover_invalid_credentials
        n = recover_invalid_credentials()
        if n > 0:
            print(f"[init_db] 已自动清空 {n} 条摄像机因密钥变更无法解密的密码字段")
    except Exception as e:
        print(f"[init_db] 自愈扫描失败（不影响启动）：{e}")


def recover_invalid_credentials() -> int:
    """兼容入口：转发到 crypto_recovery 模块，便于其他脚本直接调用。"""
    from core.crypto_recovery import recover_invalid_credentials as _impl
    return _impl()
