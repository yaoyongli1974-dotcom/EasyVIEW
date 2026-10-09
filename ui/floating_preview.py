"""独立浮出预览窗口：把某一路画面弹出为可自由移动/缩放的单独窗口。

与主窗口共享同一个 LibVLC 实例，但使用独立的 MediaPlayer（独立 RTSP 连接），
关闭窗口时停止并释放该路播放器。
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMainWindow

from ui.preview_widget import PreviewWidget


class FloatingPreview(QMainWindow):
    def __init__(self, camera, vlc_instance, parent=None):
        super().__init__(parent)
        self.camera = camera
        self.setWindowTitle(f"EasyVIEW · {camera.name if camera else ''}")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.resize(800, 560)
        self.preview = PreviewWidget(vlc_instance, 0)
        self.setCentralWidget(self.preview)
        if camera is not None:
            self.preview.set_camera(camera)

    def closeEvent(self, event):
        if self.preview is not None:
            self.preview.set_camera(None)
        super().closeEvent(event)
