"""主窗口：顶部工具栏（布局/全屏/发现/云台/录像/添加）+ 左列表 + 右预览网格 + 云台/录像停靠窗。"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from core.camera import Camera, add_camera, delete_camera, test_connection, update_camera
from core.config import DATA_DIR, HW_MODE, VLC_ARGS, set_hw_mode
# 必须在 import vlc 之前完成 VLC 运行时路径注入（core.config 在导入时执行 _inject_vlc_path）
import vlc
from core.recorder import RecorderManager
from core.snapshot import SnapshotManager
from core.recording_plan import PlanEngine
from ui.camera_dialog import CameraDialog
from ui.camera_list import CameraListPanel
from ui.discovery_dialog import DiscoveryDialog
from ui.ptz_panel import PTZPanel
from ui.recording_panel import RecordingPanel
from ui.snapshot_panel import SnapshotPanel
from ui.schedule_panel import SchedulePanel
from ui.settings_dialog import SettingsDialog
from ui.video_grid import VideoGrid


class MainWindow(QMainWindow):
    # 版本戳记：让先生能一眼确认运行的是哪个版本（避免重打包后未覆盖老 exe）
    BUILD_TAG = "v5-elegant-slate-separator 2026-09-02 00:17"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("IVMS4200-Lite  视频预览客户端  ·  " + self.BUILD_TAG)
        self.resize(1360, 860)

        # 分隔线 / 选中高亮已改由 VideoGrid 在「单元格间隙」绘制（网格自身 paintEvent，
        # 不在任何原生视频窗口矩形内，绝对可见、播放中也可见），单元格不再自绘边框，
        # 因此这里不再需要 previewCell 的 QSS 边框。

        # 全局共享一个 LibVLC 实例（所有 MediaPlayer 共用）
        self.instance = vlc.Instance(VLC_ARGS)
        # 录像管理（存储根目录）
        self.recorder_manager = RecorderManager(self.instance, str(DATA_DIR / "recordings"))
        # 截图抓拍管理
        self.snapshot_manager = SnapshotManager(str(DATA_DIR / "snapshots"))
        # 录像计划引擎（定时 + 移动侦测）
        self.plan_engine = PlanEngine(self.recorder_manager, self.instance)

        # 注意顺序：工具栏依赖 self.grid 与 dock 实例，须在主体/停靠窗之后构建
        self._build_body()
        self._build_docks()
        self._build_toolbar()
        self._wire()

        # 启动诊断：把版本戳写入调试日志，便于离线验证打包产物确实包含本版代码
        try:
            from pathlib import Path as _P
            import time as _t
            _logp = _P(DATA_DIR) / "ivms_debug.log"
            with open(_logp, "a", encoding="utf-8") as _f:
                _f.write(_t.strftime("%Y-%m-%d %H:%M:%S") + f" APP_START build={self.BUILD_TAG}\n")
        except Exception:
            pass

    # ---------- 工具栏 ----------
    def _build_toolbar(self):
        tb = QToolBar("主工具栏")
        self.addToolBar(tb)
        self._add_btn(tb, "单画面", lambda: self.grid.apply_layout(1, 1))
        self._add_btn(tb, "4画面", lambda: self.grid.apply_layout(2, 2))
        self._add_btn(tb, "9画面", lambda: self.grid.apply_layout(3, 3))
        self._add_btn(tb, "自定义", self._custom_layout)
        tb.addSeparator()
        self._add_btn(tb, "全屏", self._fullscreen)
        self._add_btn(tb, "停止全部", self.grid.clear_all)
        tb.addSeparator()
        self._add_btn(tb, "发现设备", self._discover)
        self._add_btn(tb, "云台", lambda: self._toggle_dock(self.ptz_dock))
        self._add_btn(tb, "录像", lambda: self._toggle_dock(self.rec_dock))
        self._add_btn(tb, "抓拍", self._capture_active)
        self._add_btn(tb, "计划", lambda: self._toggle_dock(self.plan_dock))
        tb.addSeparator()
        self._add_btn(tb, "设置", self._open_settings)
        self._add_btn(tb, "添加摄像机", self._add_camera)

    def _add_btn(self, tb: QToolBar, text: str, slot):
        btn = QPushButton(text)
        btn.clicked.connect(slot)
        tb.addWidget(btn)

    # ---------- 主体 ----------
    def _build_body(self):
        left = QVBoxLayout()
        left.addWidget(QLabel("摄像机列表"))
        self.cam_list = CameraListPanel()
        left.addWidget(self.cam_list)
        left_widget = QWidget()
        left_widget.setLayout(left)
        left_widget.setMinimumWidth(240)
        left_widget.setMaximumWidth(320)

        self.grid = VideoGrid(self.instance)
        # 选中某路预览时同步更新云台/录像面板
        for w in self.grid.widgets:
            w.selected.connect(self._on_active_changed)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.addWidget(left_widget)
        body_layout.addWidget(self.grid, 1)
        self.setCentralWidget(body)

    def _build_docks(self):
        self.ptz = PTZPanel()
        self.ptz_dock = QDockWidget("云台控制", self)
        self.ptz_dock.setWidget(self.ptz)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.ptz_dock)
        self.ptz_dock.hide()

        self.rec = RecordingPanel(self.recorder_manager)
        self.rec.playFileRequested.connect(self._play_recording)
        self.rec_dock = QDockWidget("本地录像 / 回放", self)
        self.rec_dock.setWidget(self.rec)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.rec_dock)
        self.rec_dock.hide()

        self.snap = SnapshotPanel(self.snapshot_manager)
        self.snap.set_player_provider(lambda: self._active_player())
        self.snap.statusChanged.connect(self.statusBar().showMessage)
        self.snap_dock = QDockWidget("截图抓拍", self)
        self.snap_dock.setWidget(self.snap)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.snap_dock)
        self.snap_dock.hide()

        self.plan = SchedulePanel(self.plan_engine)
        self.plan.statusChanged.connect(self.statusBar().showMessage)
        self.plan_dock = QDockWidget("录像计划", self)
        self.plan_dock.setWidget(self.plan)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.plan_dock)
        self.plan_dock.hide()

    def _wire(self):
        self.cam_list.playRequested.connect(self._on_play_requested)
        self.cam_list.editRequested.connect(self._edit_camera)
        self.cam_list.deleteRequested.connect(self._delete_camera)
        self.cam_list.testRequested.connect(self._test_camera)

    # ---------- 激活路联动 ----------
    def _on_active_changed(self, widget):
        cam = getattr(widget, "camera", None)
        self.ptz.set_camera(cam)
        self.rec.set_camera(cam)
        self.snap.set_camera(cam)
        self.plan.set_camera(cam)
        self.cam_list.highlight_camera(cam)
        n = getattr(widget, "channel_index", -1) + 1
        if cam:
            self.statusBar().showMessage(
                f"已选中 窗口{n}：当前设备「{cam.name}」—— 点击左侧其他设备可切换上墙")
        else:
            self.statusBar().showMessage(
                f"已选中 窗口{n}：点击左侧摄像机列表中的设备即可上墙到该窗口（右键窗口可清空）")

    def _on_play_requested(self, cam):
        slot = self.grid.play_camera(cam)
        if slot is not None:
            self.statusBar().showMessage(f"设备「{cam.name}」已上墙到 窗口{slot + 1}")
        else:
            self.statusBar().showMessage("没有可用窗口，请先切换分屏布局（单/4/9画面）")

    def _active_player(self):
        """返回当前激活预览路正在播放的 MediaPlayer（供抓拍使用）。"""
        w = self.grid.active_widget
        if w is not None and w.player is not None and w.player.is_playing():
            return w.player
        return None

    def _capture_active(self):
        self.snap._capture()

    def _open_settings(self):
        dlg = SettingsDialog(self)
        dlg.exec()

    def _toggle_dock(self, dock: QDockWidget):
        dock.setVisible(not dock.isVisible())

    # ---------- 摄像机操作 ----------
    def _add_camera(self):
        dlg = CameraDialog()
        if dlg.exec():
            add_camera(dlg.get_camera())
            self.cam_list.refresh()

    def _discover(self):
        dlg = DiscoveryDialog(self)
        if dlg.exec():
            cam = dlg.result_camera
            if cam:
                add_camera(cam)
                self.cam_list.refresh()

    def _edit_camera(self, cam: Camera):
        dlg = CameraDialog(cam)
        if dlg.exec():
            update_camera(dlg.get_camera())
            self.cam_list.refresh()

    def _delete_camera(self, cam: Camera):
        if cam.id is None:
            return
        if QMessageBox.question(self, "确认", f"删除摄像机「{cam.name}」？") == QMessageBox.StandardButton.Yes:
            delete_camera(cam.id)
            self.cam_list.refresh()

    def _test_camera(self, cam: Camera):
        ok, msg = test_connection(cam)
        QMessageBox.information(self, "连接测试", f"[{'成功' if ok else '失败'}] {msg}")

    # ---------- 回放 ----------
    def _play_recording(self, path: str):
        target = self.grid.active_widget or next(
            (w for w in self.grid.widgets if w.isVisible()), self.grid.widgets[0]
        )
        target.play_file(path)

    # ---------- 布局 / 全屏 ----------
    def _custom_layout(self):
        text, ok = QInputDialog.getText(self, "自定义分屏", "输入 行x列（如 2x2 / 3x3，乘积≤9）:")
        if not ok:
            return
        try:
            rows, cols = text.lower().replace("×", "x").split("x")
            r, c = int(rows), int(cols)
            if r < 1 or c < 1 or r * c > 9:
                raise ValueError
            self.grid.apply_layout(r, c)
        except Exception:
            QMessageBox.warning(self, "提示", "格式应为 行x列，且行列乘积不超过 9（如 2x2）")

    def _fullscreen(self):
        if self.grid.fullscreen_widget:
            self.grid.exit_fullscreen()
        else:
            self.grid.enter_fullscreen()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self.grid.fullscreen_widget:
            self.grid.exit_fullscreen()
        elif event.key() == Qt.Key.Key_S:
            # 快捷键 S：抓拍当前激活路
            self._capture_active()
        super().keyPressEvent(event)

    def closeEvent(self, _event):
        self.plan_engine.stop()
        self.snapshot_manager.stop_all_timed()
        self.recorder_manager.stop_all()
        self.grid.clear_all()
        if self.instance:
            self.instance.release()
