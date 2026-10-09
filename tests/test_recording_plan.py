"""录像计划：时间窗口判定（含跨夜与星期掩码）。"""
import time

from core.recording_plan import PlanEngine, RecordingPlan


def _t(hour, minute, weekday):
    # struct_time 的 tm_wday：0=周一 .. 6=周日，与 PlanEngine._in_window 约定一致
    return time.struct_time((2026, 1, 5, hour, minute, 0, weekday, 1, -1))


def test_in_window_normal():
    p = RecordingPlan(weekdays=0b1111111, start_min=9 * 60, end_min=18 * 60)
    assert PlanEngine._in_window(p, _t(10, 0, 0)) is True
    assert PlanEngine._in_window(p, _t(8, 59, 0)) is False
    assert PlanEngine._in_window(p, _t(18, 0, 0)) is False


def test_in_window_overnight():
    p = RecordingPlan(weekdays=0b1111111, start_min=22 * 60, end_min=6 * 60)
    assert PlanEngine._in_window(p, _t(23, 0, 0)) is True
    assert PlanEngine._in_window(p, _t(5, 0, 0)) is True
    assert PlanEngine._in_window(p, _t(12, 0, 0)) is False


def test_in_window_weekday_mask():
    p = RecordingPlan(weekdays=0b0000001, start_min=0, end_min=1439)  # 仅周一
    assert PlanEngine._in_window(p, _t(12, 0, 0)) is True
    assert PlanEngine._in_window(p, _t(12, 0, 1)) is False
