"""监控通道管理：分组 → 设备 → 通道 树形管理。

- 增删改设备（协议/地址/账号/密码/通道数/分组）
- 连接测试（后台线程，状态分类着色）
- 双击通道上墙：单通道 → 当前窗格；设备/分组 → 按通道数自动分屏
"""
import threading

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from core.camera import Camera, add_camera, delete_camera, list_cameras, test_connection, update_camera
from ui.camera_dialog import CameraDialog

PROTOCOLS = {"rtsp": "RTSP", "onvif": "ONVIF", "http": "HTTP/HLS"}

STATUS_COLOR = {
    "ok": "#22c55e",
    "auth": "#f59e0b",
    "timeout": "#f43f5e",
    "refused": "#f43f5e",
    "unreachable": "#f43f5e",
    "dns": "#f43f5e",
    "bad_url": "#f59e0b",
    "bad_config": "#f59e0b",
    "error": "#f43f5e",
    "unknown": "#8b98b0",
}

DEFAULT_GROUP = "默认分组"


class ChannelManager(QDialog):
    # 请求把若干路（多通道/分组）上墙
    playRequested = pyqtSignal(list)
    # 设备库发生变化（增删改）
    changed = pyqtSignal()
    # 后台测试结果：node-key(设备 id), code, message
    testResult = pyqtSignal(object, str, str)

    HEADERS = ["名称", "协议", "地址", "通道", "状态"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("监控通道管理")
        self.resize(880, 560)
        self._cams: list[Camera] = []
        self.testResult.connect(self._on_test_result)
        self._build()
        self.refresh()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        self.hint = QLabel("双击：通道→上墙到当前窗格；设备/分组→按通道数自动分屏。")
        self.hint.setObjectName("hint")
        root.addWidget(self.hint)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(len(self.HEADERS))
        self.tree.setHeaderLabels(self.HEADERS)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.setUniformRowHeights(True)
        self.tree.itemDoubleClicked.connect(lambda _i, _c: self._play_selected())
        hdr = self.tree.header()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in range(1, len(self.HEADERS)):
            hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        root.addWidget(self.tree)

        bar = QHBoxLayout()
        for text, slot in [
            ("添加设备", self._add),
            ("编辑", self._edit),
            ("删除", self._delete),
        ]:
            bar.addWidget(self._btn(text, slot))
        bar.addSpacing(12)
        for text, slot in [
            ("连接测试", self._test_selected),
            ("全部测试", self._test_all),
        ]:
            bar.addWidget(self._btn(text, slot))
        bar.addSpacing(12)
        bar.addWidget(self._btn("选中上墙", self._play_selected))
        bar.addStretch(1)
        bar.addWidget(self._btn("展开", self.tree.expandAll))
        bar.addWidget(self._btn("折叠", self.tree.collapseAll))
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
        self.tree.clear()
        groups: dict[str, list[Camera]] = {}
        for cam in self._cams:
            groups.setdefault(cam.group or DEFAULT_GROUP, []).append(cam)

        bold = QFont()
        bold.setBold(True)
        for gname in sorted(groups):
            devices = groups[gname]
            total_ch = sum(max(1, int(c.channels or 1)) for c in devices)
            gitem = QTreeWidgetItem([gname, "", "", f"{len(devices)} 台 / {total_ch} 路", ""])
            gitem.setData(0, Qt.ItemDataRole.UserRole, {"type": "group", "group": gname})
            gitem.setFont(0, bold)
            gitem.setForeground(0, QColor("#22d3ee"))
            self.tree.addTopLevelItem(gitem)

            for cam in devices:
                ditem = QTreeWidgetItem(self._device_row(cam))
                ditem.setData(0, Qt.ItemDataRole.UserRole, {"type": "device", "cam_id": cam.id})
                ditem.setForeground(len(self.HEADERS) - 1, QColor(STATUS_COLOR["unknown"]))
                gitem.addChild(ditem)

                n = max(1, int(cam.channels or 1))
                if n > 1:
                    for ch in range(1, n + 1):
                        citem = QTreeWidgetItem([f"通道 {ch}", "", "", str(ch), ""])
                        citem.setData(0, Qt.ItemDataRole.UserRole,
                                      {"type": "channel", "cam_id": cam.id, "channel": ch})
                        ditem.addChild(citem)
                ditem.setExpanded(False)
            gitem.setExpanded(True)

    def _device_row(self, cam: Camera) -> list[str]:
        proto = PROTOCOLS.get((cam.protocol or "rtsp").lower(), cam.protocol)
        n = max(1, int(cam.channels or 1))
        ch = f"{n} 路" if n > 1 else "1"
        return [cam.name, proto, f"{cam.ip}:{cam.port}", ch, "未测试"]

    def _cam_of(self, item: QTreeWidgetItem) -> Camera | None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return None
        cid = data.get("cam_id")
        return next((c for c in self._cams if c.id == cid), None)

    def _items(self):
        return [self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())]

    def _selected_cams(self) -> list[Camera]:
        out = []
        for item in self.tree.selectedItems():
            cam = self._cam_of(item)
            if cam is not None and cam not in out:
                out.append(cam)
        return out

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
            QMessageBox.information(self, "提示", "请先选择一个设备")
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
    def _test_devices(self, cams):
        if not cams:
            return
        for cam in cams:
            self._set_status_for(cam.id, "unknown", "测试中…")

        def worker():
            for cam in cams:
                try:
                    ok, msg = test_connection(cam, timeout=5.0)
                except Exception as e:  # noqa: BLE001
                    ok, msg = False, f"测试异常：{e}"
                code = "ok" if ok else self._code_of(msg)
                self.testResult.emit(cam.id, code, msg)

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

    def _iter_device_items(self):
        for g in self._items():
            for i in range(g.childCount()):
                yield g.child(i)

    def _set_status_for(self, cam_id, code, msg):
        for ditem in self._iter_device_items():
            data = ditem.data(0, Qt.ItemDataRole.UserRole) or {}
            if data.get("cam_id") == cam_id:
                ditem.setText(len(self.HEADERS) - 1, msg)
                ditem.setForeground(len(self.HEADERS) - 1, QColor(STATUS_COLOR.get(code, "#8b98b0")))

    def _on_test_result(self, cam_id, code, msg):
        self._set_status_for(cam_id, code, msg)

    def _test_selected(self):
        self._test_devices(self._selected_cams())

    def _test_all(self):
        self._test_devices(list(self._cams))

    # ---------- 上墙 ----------
    def _collect_play(self) -> list[Camera]:
        """把选中的节点展开为要上墙的通道列表。"""
        out: list[Camera] = []
        seen = set()
        for item in self.tree.selectedItems():
            data = item.data(0, Qt.ItemDataRole.UserRole) or {}
            kind = data.get("type")
            if kind == "channel":
                cam = self._cam_of(item)
                if cam:
                    out.append(cam.channel_camera(data["channel"]))
            elif kind == "device":
                cam = self._cam_of(item)
                if cam:
                    for ch in range(1, max(1, int(cam.channels or 1)) + 1):
                        out.append(cam.channel_camera(ch))
            elif kind == "group":
                gname = data["group"]
                for cam in self._cams:
                    if (cam.group or DEFAULT_GROUP) == gname:
                        for ch in range(1, max(1, int(cam.channels or 1)) + 1):
                            out.append(cam.channel_camera(ch))
        # 去重（按 设备id + 通道）
        uniq = []
        for c in out:
            key = (c.ip, c.port, c.channel, c.protocol)
            if key not in seen:
                seen.add(key)
                uniq.append(c)
        return uniq

    def _play_selected(self):
        cams = self._collect_play()
        if not cams:
            QMessageBox.information(self, "提示", "请先选择要上墙的通道/设备/分组")
            return
        self.playRequested.emit(cams)
