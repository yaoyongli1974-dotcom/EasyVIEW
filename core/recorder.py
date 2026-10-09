"""本地录像：基于 LibVLC 的启停、分段存储与索引回调。

设计：
- 每路录像使用独立的 MediaPlayer（独立 RTSP 连接），仅写文件、不显示，避免与预览互扰。
- 分段：segment_seconds>0 时，定时停止当前段并开启新段，每段生成一个 mp4 文件，
  并通过 on_segment 回调写入回放索引（recordings 表）。
- 单段（segment_seconds=0）：一次 start 对应一个文件，stop 时归档。
"""
import threading
import time
from pathlib import Path

# 先经 core.playback 触发 core.config 的 VLC 路径注入，再 import vlc
from core.playback import add_recording

import vlc


class Recorder:
    def __init__(self, vlc_instance: vlc.Instance, camera, storage_dir: str):
        self.instance = vlc_instance
        self.camera = camera
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.player = None
        self.segment_timer: threading.Timer | None = None
        self.segment_seconds = 0
        self._meta: dict | None = None
        self._on_segment = None

    def _segment_path(self) -> Path:
        ts = time.strftime("%Y%m%d_%H%M%S")
        return self.storage_dir / f"cam{self.camera.id}_{ts}.mp4"

    def start(self, segment_seconds: int = 0, on_segment=None):
        self.segment_seconds = segment_seconds
        self._on_segment = on_segment
        self._start_segment()
        if segment_seconds and segment_seconds > 0:
            self._schedule_next()

    def _start_segment(self):
        path = self._segment_path()
        media = self.instance.media_new(self.camera.rtsp_url())
        media.add_option("rtsp-tcp")
        # 仅写文件，不显示
        media.add_option(f"sout=#std{{access=file,mux=mp4,dst='{path}'}}")
        media.add_option("no-sout-rtp-sap")
        media.add_option("no-sout-standard-sap")
        self.player = self.instance.media_player_new()
        self.player.set_media(media)
        self.player.play()
        self._meta = {"path": str(path), "start": time.time()}

    def _schedule_next(self):
        self.segment_timer = threading.Timer(self.segment_seconds, self._rotate)
        self.segment_timer.daemon = True
        self.segment_timer.start()

    def _rotate(self):
        self._stop_player()
        if self._on_segment and self._meta:
            self._on_segment(self.camera.id, self._meta)
        self._start_segment()
        self._schedule_next()

    def stop(self):
        if self.segment_timer:
            self.segment_timer.cancel()
            self.segment_timer = None
        self._stop_player()
        if self._on_segment and self._meta:
            self._on_segment(self.camera.id, self._meta)
        self._meta = None

    def _stop_player(self):
        if self.player:
            self.player.stop()
            try:
                self.player.release()
            except Exception:
                pass
            self.player = None


class RecorderManager:
    """管理多路并发录像。"""

    def __init__(self, vlc_instance: vlc.Instance, storage_root: str):
        self.instance = vlc_instance
        self.storage_root = Path(storage_root)
        self.recorders: dict[int, Recorder] = {}

    def _finalize(self, camera_id: int, meta: dict):
        add_recording(
            camera_id, meta["path"], meta["start"], time.time(),
            trigger=meta.get("trigger", "manual"), plan_id=meta.get("plan_id", 0),
        )

    def start(self, camera, segment_seconds: int = 0, trigger: str = "manual", plan_id: int = 0):
        if camera.id in self.recorders:
            return
        d = self.storage_root / f"cam{camera.id}"
        rec = Recorder(self.instance, camera, str(d))
        # 元数据中携带触发来源，供索引落库
        orig = self._finalize

        def _on_seg(cid, m):
            m = dict(m)
            m["trigger"] = trigger
            m["plan_id"] = plan_id
            orig(cid, m)

        rec.start(segment_seconds=segment_seconds, on_segment=_on_seg)
        self.recorders[camera.id] = rec

    def stop(self, camera_id: int):
        rec = self.recorders.pop(camera_id, None)
        if rec:
            rec.stop()

    def is_recording(self, camera_id: int) -> bool:
        return camera_id in self.recorders

    def stop_all(self):
        for cid in list(self.recorders.keys()):
            self.stop(cid)
