"""截图抓拍面板：手动抓拍当前激活路 + 定时抓拍 + 历史快照检索。"""""
from PyQt6.QtCore import pyqtSignal, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

import time

from core.camera import Camera
from core.snapshot import SnapshotManager, search_snapshots


class SnapshotPanel(QWidget):
    statusChanged = pyqtSignal(str)

    def __init__(self, snapshot_manager: SnapshotManager, parent=None):
        super().__init__(parent)
        self.mgr = snapshot_manager
        self.camera: Camera | None = None
        self._player_provider = None  # callable -> vlc.MediaPlayer | None
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        self.state = QLabel("未选择摄像机")
        lay.addWidget(self.state)

        # 抓拍控制
        ctl = QHBoxLayout()
        self.btn_capture = QPushButton("抓拍当前")
        self.btn_capture.clicked.connect(self._capture)
        ctl.addWidget(self.btn_capture)
        lay.addLayout(ctl)

        # 参数：格式 / 质量
        cfg = QHBoxLayout()
        self.fmt = QComboBox()
        self.fmt.addItems(["jpg", "png"])
        self.quality = QSpinBox()
        self.quality.setRange(10, 100)
        self.quality.setValue(90)
        self.quality.setSuffix("%")
        self.btn_apply_cfg = QPushButton("应用参数")
        self.btn_apply_cfg.clicked.connect(self._apply_cfg)
        cfg.addWidget(QLabel("格式")); cfg.addWidget(self.fmt)
        cfg.addWidget(QLabel("质量")); cfg.addWidget(self.quality)
        cfg.addWidget(self.btn_apply_cfg)
        lay.addLayout(cfg)

        # 定时抓拍
        tm = QGroupBox("定时抓拍")
        tv = QVBoxLayout()
        tr = QHBoxLayout()
        self.interval = QSpinBox()
        self.interval.setRange(1, 3600)
        self.interval.setValue(10)
        self.interval.setSuffix(" s")
        self.btn_timed = QPushButton("开始定时")
        self.btn_timed.clicked.connect(self._toggle_timed)
        tr.addWidget(QLabel("间隔")); tr.addWidget(self.interval)
        tr.addWidget(self.btn_timed)
        tv.addLayout(tr)
        tm.setLayout(tv)
        lay.addWidget(tm)

        # 历史快照
        box = QGroupBox("历史快照")
        bv = QVBoxLayout()
        self.snap_list = QListWidget()
        self.snap_list.itemDoubleClicked.connect(self._open)
        rb = QHBoxLayout()
        self.btn_refresh = QPushButton("刷新")
        self.btn_refresh.clicked.connect(self._refresh)
        rb.addWidget(self.btn_refresh); rb.addStretch(1)
        bv.addWidget(self.snap_list); bv.addLayout(rb)
        box.setLayout(bv)
        lay.addWidget(box, 1)

    def set_camera(self, cam: Camera | None):
        self.camera = cam
        self._update_state()
        self._refresh()

    def set_player_provider(self, provider):
        """提供当前激活预览路 player 的无参 callable（用于手动/定时抓拍）。"""
        self._player_provider = provider

    def _update_state(self):
        if self.camera is None:
            self.state.setText("未选择摄像机")
        else:
            self.state.setText(f"{self.camera.name}：{'定时抓拍中' if self.mgr.is_timed(f'snap_{self.camera.id}') else '空闲'}")

    def _apply_cfg(self):
        self.mgr.configure(self.fmt.currentText(), self.quality.value())

    def _capture(self):
        if not self.camera:
            self.statusChanged.emit("请先选中一路预览")
            return
        player = self._player_provider() if callable(self._player_provider) else None
        if player is None:
            self.statusChanged.emit("该预览路未播放")
            return
        meta = self.mgr.capture(player, self.camera.id, label=self.camera.name)
        if meta:
            self.statusChanged.emit(f"已抓拍：{meta['path']}")
            self._refresh()
        else:
            self.statusChanged.emit("抓拍失败（画面未就绪）")

    def _toggle_timed(self):
        if not self.camera:
            self.statusChanged.emit("请先选中一路预览")
            return
        key = f"snap_{self.camera.id}"
        if self.mgr.is_timed(key):
            self.mgr.stop_timed(key)
            self.btn_timed.setText("开始定时")
            self.statusChanged.emit("已停止定时抓拍")
        else:
            provider = self._player_provider
            self.mgr.start_timed(key, provider, self.camera.id, self.interval.value(),
                                 label=self.camera.name)
            self.btn_timed.setText("停止定时")
            self.statusChanged.emit(f"已启动定时抓拍（每 {self.interval.value()}s）")
        self._update_state()

    def _refresh(self):
        self.snap_list.clear()
        if not self.camera:
            return
        for s in search_snapshots(camera_id=self.camera.id):
            t = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(s["taken_at"]))
            self.snap_list.addItem(f"{t}  {s['width']}x{s['height']}")
            self.snap_list.item(self.snap_list.count() - 1).setData(1, s["path"])

    def _open(self, item):
        path = item.data(1)
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def stop_all(self):
        self.mgr.stop_all_timed()
        self.btn_timed.setText("开始定时")
