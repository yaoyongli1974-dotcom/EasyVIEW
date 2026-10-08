"""截图抓拍：手动 / 定时触发，捕获当前实时画面。

触发方式
--------
- 手动触发：工具栏「抓拍」按钮或预览控件快捷键（在 MainWindow 绑定 S 键），
  捕获当前激活预览路（grid.active_widget）的画面。
- 定时触发：SnapshotPanel 设置间隔后调用 start_timed()，内部以独立线程周期性抓拍。

调用接口
--------
通过 LibVLC 的 `MediaPlayer.video_take_snapshot(num, file_path, width, height)`：
- num=0（视频输出序号）
- file_path：目标文件路径，扩展名决定格式（.jpg / .png）
- width/height=0：按视频原始分辨率保存

参数配置（SnapshotManager.configure）
--------------------------------
- fmt:        'jpg' | 'png'
- quality:    jpg 质量 1..100（png 忽略）
- interval:   定时抓拍间隔（秒）
- prefix:     文件名前缀 / 水印标签（写入 DB label 列 & 叠加到文件名）

数据存储
--------
- 文件落盘：<DATA_DIR>/snapshots/cam{id}/YYYYMMDD/HHMMSS_{seq}.{ext}
- 索引：snapshots 表（camera_id, taken_at, path, width, height, label）
"""
import os
import threading
import time
from pathlib import Path

import vlc

from core.config import DATA_DIR
from core.database import get_conn

FMT_EXT = {"jpg": "jpg", "jpeg": "jpg", "png": "png"}


class SnapshotManager:
    def __init__(self, storage_root: str = None):
        self.storage_root = Path(storage_root or (DATA_DIR / "snapshots"))
        self.fmt = "jpg"
        self.quality = 90
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    # ---------------- 参数配置 ----------------
    def configure(self, fmt: str = "jpg", quality: int = 90):
        self.fmt = FMT_EXT.get(fmt.lower(), "jpg")
        self.quality = max(1, min(100, int(quality)))

    # ---------------- 单次抓拍 ----------------
    def capture(self, player: vlc.MediaPlayer, camera_id: int, label: str = "") -> dict | None:
        """捕获 player 当前帧。成功返回元数据 dict，失败返回 None。"""
        if player is None or not player.is_playing():
            return None
        cam_dir = self.storage_root / f"cam{camera_id}" / time.strftime("%Y%m%d")
        cam_dir.mkdir(parents=True, exist_ok=True)
        seq = time.strftime("%H%M%S") + f"_{int(time.time() * 1000) % 1000:03d}"
        fname = f"{seq}.{self.fmt}"
        path = cam_dir / fname
        try:
            ok = player.video_take_snapshot(0, str(path), 0, 0)
        except Exception:
            ok = False
        if not ok or not path.exists():
            return None
        # 读取实际分辨率
        w = h = 0
        try:
            vsize = player.video_get_size(0)
            if vsize:
                w, h = vsize
        except Exception:
            pass
        meta = {
            "camera_id": camera_id,
            "taken_at": time.time(),
            "path": str(path),
            "width": w,
            "height": h,
            "label": label,
        }
        add_snapshot(meta)
        return meta

    # ---------------- 定时抓拍 ----------------
    def start_timed(self, key: str, player_provider, camera_id: int, interval: int, label: str = ""):
        """以 interval 秒为周期调用 player_provider() 取得 player 并抓拍。

        player_provider: 无参 callable，返回当前要抓拍的 vlc.MediaPlayer（可能为 None）。
        """
        self.stop_timed(key)
        interval = max(1, int(interval))

        def _tick():
            with self._lock:
                if key not in self._timers:
                    return
            player = player_provider() if callable(player_provider) else None
            if player is not None:
                self.capture(player, camera_id, label=label)
            with self._lock:
                if key in self._timers:
                    t = threading.Timer(interval, _tick)
                    t.daemon = True
                    self._timers[key] = t
                    t.start()

        with self._lock:
            t = threading.Timer(interval, _tick)
            t.daemon = True
            self._timers[key] = t
            t.start()

    def stop_timed(self, key: str):
        with self._lock:
            t = self._timers.pop(key, None)
            if t:
                t.cancel()

    def stop_all_timed(self):
        with self._lock:
            for t in self._timers.values():
                t.cancel()
            self._timers.clear()

    def is_timed(self, key: str) -> bool:
        with self._lock:
            return key in self._timers


# ---------------- DB 访问 ----------------
def add_snapshot(meta: dict) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO snapshots (camera_id, taken_at, path, width, height, label) "
        "VALUES (?,?,?,?,?,?)",
        (meta["camera_id"], meta["taken_at"], meta["path"], meta["width"], meta["height"], meta["label"]),
    )
    sid = cur.lastrowid
    conn.commit()
    conn.close()
    return sid


def search_snapshots(camera_id: int = None, date: str = None) -> list[dict]:
    conn = get_conn()
    if camera_id is not None:
        rows = conn.execute(
            "SELECT * FROM snapshots WHERE camera_id=? ORDER BY taken_at DESC", (camera_id,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM snapshots ORDER BY taken_at DESC").fetchall()
    conn.close()
    result = [dict(r) for r in rows]
    if date:
        result = [r for r in result if time.strftime("%Y-%m-%d", time.localtime(r["taken_at"])) == date]
    return result


def delete_snapshot(sid: int) -> None:
    conn = get_conn()
    row = conn.execute("SELECT path FROM snapshots WHERE id=?", (sid,)).fetchone()
    if row and os.path.exists(row["path"]):
        try:
            os.remove(row["path"])
        except OSError:
            pass
    conn.execute("DELETE FROM snapshots WHERE id=?", (sid,))
    conn.commit()
    conn.close()
