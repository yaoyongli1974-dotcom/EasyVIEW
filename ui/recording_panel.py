"""本地录像面板：启停、分段、回放检索。"""
import time

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.camera import Camera
from core.playback import search_recordings


class RecordingPanel(QWidget):
    playFileRequested = pyqtSignal(str)  # 回放文件路径

    def __init__(self, recorder_manager, parent=None):
        super().__init__(parent)
        self.mgr = recorder_manager
        self.camera: Camera | None = None
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)

        ctl = QHBoxLayout()
        self.seg = QSpinBox(); self.seg.setRange(0, 3600); self.seg.setValue(0)
        self.seg.setSuffix(" s")
        self.btn_start = QPushButton("开始录像")
        self.btn_stop = QPushButton("停止录像")
        self.btn_start.clicked.connect(self._start)
        self.btn_stop.clicked.connect(self._stop)
        ctl.addWidget(QLabel("分段")); ctl.addWidget(self.seg)
        ctl.addWidget(self.btn_start); ctl.addWidget(self.btn_stop)
        lay.addLayout(ctl)

        self.state = QLabel("未选择摄像机")
        lay.addWidget(self.state)

        box = QGroupBox("回放片段")
        bv = QVBoxLayout()
        self.rec_list = QListWidget()
        self.rec_list.itemDoubleClicked.connect(self._play)
        rb = QHBoxLayout()
        self.btn_refresh = QPushButton("刷新")
        self.btn_refresh.clicked.connect(self._refresh)
        rb.addWidget(self.btn_refresh); rb.addStretch(1)
        bv.addWidget(self.rec_list); bv.addLayout(rb)
        box.setLayout(bv)
        lay.addWidget(box, 1)

    def set_camera(self, cam: Camera | None):
        self.camera = cam
        self._update_state()
        self._refresh()

    def _update_state(self):
        if self.camera is None:
            self.state.setText("未选择摄像机")
            return
        rec = self.mgr.is_recording(self.camera.id)
        self.state.setText(f"{self.camera.name}：{'录制中' if rec else '空闲'}")

    def _start(self):
        if not self.camera:
            return
        self.mgr.start(self.camera, segment_seconds=self.seg.value())
        self._update_state()

    def _stop(self):
        if not self.camera:
            return
        self.mgr.stop(self.camera.id)
        self._update_state()
        self._refresh()

    def _refresh(self):
        self.rec_list.clear()
        if not self.camera:
            return
        for r in search_recordings(camera_id=self.camera.id):
            start = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["start_time"]))
            dur = int(r["end_time"] - r["start_time"])
            self.rec_list.addItem(f"{start}  时长{dur}s  {r['size']//1024}KB")
            self.rec_list.item(self.rec_list.count() - 1).setData(1, r["path"])

    def _play(self, item):
        path = item.data(1)
        if path:
            self.playFileRequested.emit(path)
