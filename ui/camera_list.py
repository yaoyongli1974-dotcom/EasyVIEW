"""左侧摄像机列表面板：展示、右键菜单（播放/编辑/测试/删除）、双击播放。"""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QMenu

from core.camera import Camera, list_cameras


class CameraListPanel(QListWidget):
    playRequested = pyqtSignal(object)
    editRequested = pyqtSignal(object)
    deleteRequested = pyqtSignal(object)
    testRequested = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        self.itemDoubleClicked.connect(self._on_double)
        self.refresh()

    def refresh(self):
        self.clear()
        for cam in list_cameras():
            item = QListWidgetItem(f"{cam.name}  ({cam.ip})")
            item.setData(Qt.ItemDataRole.UserRole, cam)
            self.addItem(item)

    def _selected_camera(self) -> Camera | None:
        item = self.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def highlight_camera(self, cam):
        """在列表中高亮当前上墙到选中窗口的设备，便于在多个窗口间核对分配。"""
        target_id = getattr(cam, "id", None)
        for i in range(self.count()):
            item = self.item(i)
            c = item.data(Qt.ItemDataRole.UserRole)
            match = bool(c and target_id is not None and getattr(c, "id", None) == target_id)
            item.setBackground(QColor("#264f78") if match else QColor("transparent"))
        if cam is not None:
            for i in range(self.count()):
                if self.item(i).data(Qt.ItemDataRole.UserRole) is cam:
                    self.setCurrentRow(i)
                    break

    def _on_double(self, item: QListWidgetItem):
        cam = item.data(Qt.ItemDataRole.UserRole)
        if cam:
            self.playRequested.emit(cam)

    def _context_menu(self, pos):
        cam = self._selected_camera()
        if not cam:
            return
        menu = QMenu(self)
        menu.addAction("播放", lambda: self.playRequested.emit(cam))
        menu.addAction("编辑", lambda: self.editRequested.emit(cam))
        menu.addAction("连接测试", lambda: self.testRequested.emit(cam))
        menu.addSeparator()
        menu.addAction("删除", lambda: self.deleteRequested.emit(cam))
        menu.exec(self.mapToGlobal(pos))
