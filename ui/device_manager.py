"""独立「设备管理」窗口：表格化增删改、连接测试（错误分类）与多通道批量上墙。"""
import threading

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.camera import Camera, add_camera, delete_camera, list_cameras, update_camera, test_connection
from ui.camera_dialog import CameraDialog

PROTOCOLS = {"rtsp": "RTSP", "onvif": "ONVIF", "http": "HTTP/HLS"}

STATUS_COLOR = {
    "ok": "#3fb950",
    "auth": "#f0883e",
    "timeout": "#f85149",
    "refused": "#f85149",
    "unreachable": "#f85149",
    "dns": "#f85149",
    "bad_url": "#d29922",
    "bad_config": "#d29922",
    "error": "#f85149",
    "unknown": "#8b949e",
}


class DeviceManager(QDialog):
    # 请求把若干路（多通道）上墙
    playRequested = pyqtSignal(list)
    # 设备库发生变化（增删改）
    changed = pyqtSignal()
    # 后台测试结果：row, code, message
    testResult = pyqtSignal(int, str, str)

    HEADERS = ["启用", "名称", "协议", "地址", "端口", "用户名", "密码",
               "通道", "码流", "厂商", "状态"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设备管理")
        self.resize(920, 520)
        self._cams: list[Camera] = []
        self.testResult.connect(self._on_test_result)
        self._build()
        self.refresh()

    def _build(self):
        root = QVBoxLayout(self)

        self.hint = QLabel("双击一行编辑；选中多行可批量删除/测试；"
                           "「全部通道上墙」会把设备的 1..N 通道依次铺到预览窗口。")
        self.hint.setStyleSheet("color:#9aa0a6; font-size:12px;")
        root.addWidget(self.hint)

        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.itemDoubleClicked.connect(lambda _i: self._edit())
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hdr.setStretchLastSection(True)
        root.addWidget(self.table)

        bar = QHBoxLayout()
        for text, slot in [
            ("添加", self._add),
            ("编辑", self._edit),
            ("删除", self._delete),
        ]:
            bar.addWidget(self._btn(text, slot))
        bar.addSpacing(12)
        for text, slot in [
            ("连接测试(选中)", self._test_selected),
            ("全部测试", self._test_all),
        ]:
            bar.addWidget(self._btn(text, slot))
        bar.addSpacing(12)
        self.btn_play = self._btn("全部通道上墙", self._play_channels)
        bar.addWidget(self.btn_play)
        bar.addStretch(1)
        bar.addWidget(self._btn("刷新", self.refresh))
        bar.addWidget(self._btn("关闭", self.accept))
        root.addLayout(bar)

    def _btn(self, text, slot):
        b = QPushButton(text)
        b.clicked.connect(slot)
        return b

    # ---------- 数据 ----------
    def refresh(self):
        self._cams = list_cameras()
        self.table.setRowCount(len(self._cams))
        for row, cam in enumerate(self._cams):
            self._fill_row(row, cam)

    def _fill_row(self, row, cam: Camera):
        proto = PROTOCOLS.get((cam.protocol or "rtsp").lower(), cam.protocol)
        ch = f"{cam.channel}/{cam.channels}" if (cam.channels or 1) > 1 else str(cam.channel)
        values = [
            "✓" if cam.enabled else "✗",
            cam.name,
            proto,
            cam.ip,
            str(cam.port),
            cam.username,
            "●●●●" if cam.password else "",
            ch,
            "主" if cam.stream_type == "main" else "子",
            cam.vendor,
            self.table.item(row, len(self.HEADERS) - 1).text()
            if self.table.item(row, len(self.HEADERS) - 1) else "未测试",
        ]
        for col, val in enumerate(values):
            item = self.table.item(row, col) or QTableWidgetItem()
            item.setText(val)
            if col not in (0, len(self.HEADERS) - 1):
                item.setForeground(QColor("#c9d1d9"))
            self.table.setItem(row, col, item)
        self.table.item(row, 1).setData(Qt.ItemDataRole.UserRole, cam)
        self._set_status(row, "unknown", "未测试")

    def _set_status(self, row, code, msg):
        item = self.table.item(row, len(self.HEADERS) - 1) or QTableWidgetItem()
        item.setText(msg)
        item.setForeground(QColor(STATUS_COLOR.get(code, "#8b949e")))
        self.table.setItem(row, len(self.HEADERS) - 1, item)

    def _selected_cams(self) -> list[Camera]:
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()})
        return [self._cams[r] for r in rows if 0 <= r < len(self._cams)]

    # ---------- 增删改 ----------
    def _add(self):
        dlg = CameraDialog(None, self)
        if dlg.exec():
            add_camera(dlg.get_camera())
            self.refresh()
            self.changed.emit()

    def _edit(self):
        cams = self._selected_cams()
        if not cams:
            QMessageBox.information(self, "提示", "请先选择一行")
            return
        cam = cams[0]
        dlg = CameraDialog(cam, self)
        if dlg.exec():
            update_camera(dlg.get_camera())
            self.refresh()
            self.changed.emit()

    def _delete(self):
        cams = self._selected_cams()
        if not cams:
            return
        if QMessageBox.question(self, "确认", f"删除选中的 {len(cams)} 个设备？") != QMessageBox.StandardButton.Yes:
            return
        for cam in cams:
            if cam.id is not None:
                delete_camera(cam.id)
        self.refresh()
        self.changed.emit()

    # ---------- 测试（后台线程，错误分类）----------
    def _test_rows(self, rows):
        if not rows:
            return
        for r in rows:
            self._set_status(r, "unknown", "测试中…")

        def worker():
            for r in rows:
                cam = self._cams[r]
                try:
                    ok, msg = test_connection(cam, timeout=5.0)
                except Exception as e:  # noqa: BLE001
                    ok, msg = False, f"测试异常：{e}"
                code = "ok" if ok else self._code_of(msg)
                self.testResult.emit(r, code, msg)

        threading.Thread(target=worker, daemon=True).start()

    @staticmethod
    def _code_of(msg: str) -> str:
        if "密码" in msg or "认证" in msg or "无权" in msg:
            return "auth"
        if "超时" in msg:
            return "timeout"
        if "拒绝" in msg:
            return "refused"
        if "解析" in msg:
            return "dns"
        if "地址" in msg or "通道错误" in msg:
            return "bad_url"
        return "error"

    def _on_test_result(self, row, code, msg):
        if 0 <= row < self.table.rowCount():
            self._set_status(row, code, msg)

    def _test_selected(self):
        self._test_rows(sorted({i.row() for i in self.table.selectedIndexes()}))

    def _test_all(self):
        self._test_rows(list(range(len(self._cams))))

    # ---------- 多通道批量上墙 ----------
    def _play_channels(self):
        cams = self._selected_cams()
        if not cams:
            QMessageBox.information(self, "提示", "请先选择设备")
            return
        out: list[Camera] = []
        for cam in cams:
            n = max(1, int(cam.channels or 1))
            for i in range(1, n + 1):
                out.append(cam.channel_camera(i))
        self.playRequested.emit(out)
