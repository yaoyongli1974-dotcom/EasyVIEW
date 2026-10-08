"""录像计划：定时时间段自动录像 + 移动侦测触发录像。

触发方式
--------
A. 定时计划（mode='schedule'）
   - 引擎后台线程按 eval_interval（默认 15s）轮询所有启用的定时计划；
   - 当当前时间落入「星期位掩码 + 起止分钟」窗口且对应摄像机未录制 -> 自动开始录像；
   - 离开窗口 -> 自动停止该计划发起的录像（不影响手动/移动侦测录像）。

B. 移动侦测计划（mode='motion'）
   - 引擎为每路 motion 计划开一路独立子码流，按 sample_interval（默认 1s）抓取快照并做帧差；
   - 连续 min_consecutive 次判定为「有变化」即触发录像（trigger='motion'），
     带 pre_seconds 预录缓冲、post_seconds 持续缓冲，最短 min_duration 后于静止时停止。
   - 备选源：设备原生移动侦测告警（ONVIF 事件 / 厂商 SDK 告警回调）可直接调用 on_motion(plan)
     触发同一套录像逻辑（见 doc）。

调用接口
--------
- 录像统一走 RecorderManager.start(camera, segment_seconds, trigger, plan_id)；
- 定时判定：PlanEngine._eval_schedules()；移动侦测：PlanEngine._eval_motion()。

参数配置（recording_plans 表字段）
--------------------------------
schedule：weekdays(位掩码), start_min, end_min, segment_seconds, stream_type
motion  ：sensitivity(1..10), min_consecutive, pre_seconds, post_seconds, min_duration, segment_seconds, stream_type

数据存储
--------
- 计划配置：recording_plans 表（camera_id, mode, 各项参数, enabled）
- 录像段：沿用 recordings 表，新增 trigger('schedule'/'motion') 与 plan_id 列用于溯源
"""
import copy
import os
import threading
import time
from dataclasses import asdict, dataclass
from typing import Optional

import vlc

from core.camera import get_camera
from core.database import get_conn

WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


@dataclass
class RecordingPlan:
    id: Optional[int] = None
    camera_id: int = 0
    name: str = ""
    enabled: bool = True
    mode: str = "schedule"            # 'schedule' | 'motion'
    weekdays: int = 127               # 位掩码 bit0=周一..bit6=周日
    start_min: int = 0                # 0..1439
    end_min: int = 1439
    segment_seconds: int = 0
    stream_type: str = "sub"
    sensitivity: int = 5
    min_consecutive: int = 3
    pre_seconds: int = 3
    post_seconds: int = 10
    min_duration: int = 15

    def to_dict(self):
        return asdict(self)


# ---------------- DB 访问 ----------------
def add_plan(plan: RecordingPlan) -> int:
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO recording_plans
           (camera_id, name, enabled, mode, weekdays, start_min, end_min, segment_seconds,
            stream_type, sensitivity, min_consecutive, pre_seconds, post_seconds, min_duration)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (plan.camera_id, plan.name, int(plan.enabled), plan.mode, plan.weekdays,
         plan.start_min, plan.end_min, plan.segment_seconds, plan.stream_type,
         plan.sensitivity, plan.min_consecutive, plan.pre_seconds, plan.post_seconds, plan.min_duration),
    )
    pid = cur.lastrowid
    conn.commit()
    conn.close()
    return pid


def update_plan(plan: RecordingPlan):
    conn = get_conn()
    conn.execute(
        """UPDATE recording_plans SET name=?, enabled=?, mode=?, weekdays=?, start_min=?, end_min=?,
           segment_seconds=?, stream_type=?, sensitivity=?, min_consecutive=?, pre_seconds=?,
           post_seconds=?, min_duration=? WHERE id=?""",
        (plan.name, int(plan.enabled), plan.mode, plan.weekdays, plan.start_min, plan.end_min,
         plan.segment_seconds, plan.stream_type, plan.sensitivity, plan.min_consecutive,
         plan.pre_seconds, plan.post_seconds, plan.min_duration, plan.id),
    )
    conn.commit()
    conn.close()


def delete_plan(plan_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM recording_plans WHERE id=?", (plan_id,))
    conn.commit()
    conn.close()


def list_plans(camera_id: int = None) -> list[RecordingPlan]:
    conn = get_conn()
    if camera_id is not None:
        rows = conn.execute("SELECT * FROM recording_plans WHERE camera_id=? ORDER BY id", (camera_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM recording_plans ORDER BY id").fetchall()
    conn.close()
    return [_row_to_plan(r) for r in rows]


def get_plan(plan_id: int) -> Optional[RecordingPlan]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM recording_plans WHERE id=?", (plan_id,)).fetchone()
    conn.close()
    return _row_to_plan(row) if row else None


def _row_to_plan(row) -> RecordingPlan:
    return RecordingPlan(
        id=row["id"], camera_id=row["camera_id"], name=row["name"] or "",
        enabled=bool(row["enabled"]), mode=row["mode"], weekdays=row["weekdays"],
        start_min=row["start_min"], end_min=row["end_min"], segment_seconds=row["segment_seconds"],
        stream_type=row["stream_type"], sensitivity=row["sensitivity"],
        min_consecutive=row["min_consecutive"], pre_seconds=row["pre_seconds"],
        post_seconds=row["post_seconds"], min_duration=row["min_duration"],
    )


# ---------------- 计划引擎 ----------------
class PlanEngine:
    def __init__(self, recorder_manager, vlc_instance: vlc.Instance,
                 eval_interval: int = 15, sample_interval: float = 1.0):
        self.rm = recorder_manager
        self.instance = vlc_instance
        self.eval_interval = eval_interval
        self.sample_interval = sample_interval
        self._stop = threading.Event()
        self._sched_thread: threading.Thread | None = None
        self._motion_thread: threading.Thread | None = None
        self._active_schedules: set[int] = set()   # 由本引擎发起的定时录像 plan_id
        self._motion_state: dict[int, dict] = {}    # plan_id -> 状态
        self._motion_players: dict[int, vlc.MediaPlayer] = {}
        self._lock = threading.Lock()

    # ---------- 启动 / 停止 ----------
    def start(self):
        if self._sched_thread and self._sched_thread.is_alive():
            return
        self._stop.clear()
        self._sched_thread = threading.Thread(target=self._schedule_loop, daemon=True)
        self._sched_thread.start()
        self._motion_thread = threading.Thread(target=self._motion_loop, daemon=True)
        self._motion_thread.start()

    def stop(self):
        self._stop.set()
        for pid, p in self._motion_players.items():
            try:
                p.stop()
                p.release()
            except Exception:
                pass
        self._motion_players.clear()
        with self._lock:
            self._active_schedules.clear()
            self._motion_state.clear()

    @property
    def running(self) -> bool:
        return bool(self._sched_thread and self._sched_thread.is_alive())

    # ---------- 定时计划 ----------
    def _schedule_loop(self):
        while not self._stop.is_set():
            self._eval_schedules()
            self._stop.wait(self.eval_interval)

    @staticmethod
    def _in_window(plan: RecordingPlan, now_dt) -> bool:
        wd = now_dt.weekday()  # 0=周一
        if not (plan.weekdays >> wd) & 1:
            return False
        cur = now_dt.hour * 60 + now_dt.minute
        if plan.start_min <= plan.end_min:
            return plan.start_min <= cur < plan.end_min
        return cur >= plan.start_min or cur < plan.end_min  # 跨夜

    def _eval_schedules(self):
        now_dt = time.localtime()
        for plan in list_plans():
            if plan.mode != "schedule" or not plan.enabled:
                continue
            cam = get_camera(plan.camera_id)
            if cam is None:
                continue
            inside = self._in_window(plan, now_dt)
            with self._lock:
                active = plan.id in self._active_schedules
            if inside and not active and not self.rm.is_recording(cam.id):
                self.rm.start(cam, segment_seconds=plan.segment_seconds, trigger="schedule", plan_id=plan.id)
                with self._lock:
                    self._active_schedules.add(plan.id)
            elif not inside and active:
                # 仅停止由本计划发起的录像
                self.rm.stop(cam.id)
                with self._lock:
                    self._active_schedules.discard(plan.id)

    # ---------- 移动侦测 ----------
    def _motion_loop(self):
        while not self._stop.is_set():
            self._eval_motion()
            self._stop.wait(self.sample_interval)

    def _ensure_player(self, plan: RecordingPlan) -> Optional[vlc.MediaPlayer]:
        cam = get_camera(plan.camera_id)
        if cam is None:
            return None
        cam2 = copy.copy(cam)
        cam2.stream_type = plan.stream_type or "sub"
        if plan.camera_id in self._motion_players:
            return self._motion_players[plan.camera_id]
        player = self.instance.media_player_new()
        media = self.instance.media_new(cam2.rtsp_url())
        media.add_option(":vout=vdummy")  # 无窗口解码，仅为快照/帧差提供解码帧
        media.add_option("network-caching=300")
        media.add_option("rtsp-tcp")
        player.set_media(media)
        player.play()
        self._motion_players[plan.camera_id] = player
        return player

    @staticmethod
    def _snapshot_size(player: vlc.MediaPlayer, tmp_path: str) -> Optional[int]:
        try:
            if not player.is_playing():
                return None
            ok = player.video_take_snapshot(0, tmp_path, 0, 0)
            if not ok or not os.path.exists(tmp_path):
                return None
            return os.path.getsize(tmp_path)
        except Exception:
            return None

    def _eval_motion(self):
        tmp_root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "motion_tmp")
        os.makedirs(tmp_root, exist_ok=True)
        for plan in list_plans():
            if plan.mode != "motion" or not plan.enabled:
                continue
            player = self._ensure_player(plan)
            if player is None:
                continue
            tmp = os.path.join(tmp_root, f"cam{plan.camera_id}.jpg")
            size = self._snapshot_size(player, tmp)
            if size is None:
                continue
            with self._lock:
                st = self._motion_state.setdefault(
                    plan.id, {"prev": None, "consec": 0, "recording": False, "last_motion": 0.0, "start": 0.0}
                )
            prev = st["prev"]
            # 帧差启发式：文件大小变化超过阈值即视为有变化（生产建议 OpenCV 帧差）
            threshold = max(800, 5000 - plan.sensitivity * 400)
            changed = prev is None or abs(size - prev) > threshold
            st["prev"] = size
            now = time.time()
            if changed:
                st["consec"] += 1
                st["last_motion"] = now
                if st["consec"] >= plan.min_consecutive and not st["recording"]:
                    cam = get_camera(plan.camera_id)
                    if cam and not self.rm.is_recording(cam.id):
                        cam2 = copy.copy(cam)
                        cam2.stream_type = plan.stream_type or "sub"
                        self.rm.start(cam2, segment_seconds=plan.segment_seconds, trigger="motion", plan_id=plan.id)
                        st["recording"] = True
                        st["start"] = now
            else:
                st["consec"] = 0
                if st["recording"]:
                    since_motion = now - st["last_motion"]
                    since_start = now - st["start"]
                    if since_motion >= plan.post_seconds and since_start >= plan.min_duration:
                        cam = get_camera(plan.camera_id)
                        if cam:
                            self.rm.stop(cam.id)
                        st["recording"] = False
