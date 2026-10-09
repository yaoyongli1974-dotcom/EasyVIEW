"""添加/编辑摄像机对话框。"""
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QCheckBox,
    QSpinBox,
)

from core.camera import Camera


class CameraDialog(QDialog):
    def __init__(self, camera: Camera = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加摄像机" if camera is None else "编辑摄像机")
        self.cam = camera or Camera()
        self._build()
        if camera:
            self._load(camera)

    def _build(self):
        lay = QFormLayout(self)

        self.name = QLineEdit()
        self.name.setPlaceholderText("摄像机名称（留空则用 IP）")
        self.ip = QLineEdit()
        self.ip.setPlaceholderText("如 192.168.1.64")
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(554)
        self.user = QLineEdit()
        self.user.setText("admin")
        self.pwd = QLineEdit()
        self.pwd.setEchoMode(QLineEdit.EchoMode.Password)
        self.pwd.setPlaceholderText("密码将以加密方式存储")
        self.channel = QSpinBox()
        self.channel.setRange(1, 64)
        self.channel.setValue(1)
        self.stream = QComboBox()
        self.stream.addItems(["主码流(main)", "子码流(sub)"])
        self.protocol = QComboBox()
        for label, code in [
            ("RTSP（厂商模板）", "rtsp"),
            ("HTTP / HLS / MJPEG", "http"),
        ]:
            self.protocol.addItem(label, code)
        self.uri = QLineEdit()
        self.uri.setPlaceholderText("可选：完整流地址，填了优先使用")
        self.vendor = QComboBox()
        self.vendor.addItems(["hikvision", "dahua", "uniview", "imou"])
        self.enabled = QCheckBox("启用")

        for label, widget in [
            ("名称", self.name), ("IP 地址", self.ip), ("端口", self.port),
            ("接入协议", self.protocol), ("用户名", self.user), ("密码", self.pwd),
            ("通道号", self.channel), ("码流类型", self.stream), ("厂商", self.vendor),
            ("流地址", self.uri), ("状态", self.enabled),
        ]:
            lay.addRow(label, widget)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addRow(btns)

    def _load(self, cam: Camera):
        self.name.setText(cam.name)
        self.ip.setText(cam.ip)
        self.port.setValue(cam.port)
        self.user.setText(cam.username)
        self.pwd.setText(cam.password)
        self.channel.setValue(cam.channel)
        self.stream.setCurrentIndex(0 if cam.stream_type == "main" else 1)
        idx = self.protocol.findData(getattr(cam, "protocol", "rtsp") or "rtsp")
        self.protocol.setCurrentIndex(idx if idx >= 0 else 0)
        self.uri.setText(getattr(cam, "stream_uri", "") or "")
        if cam.vendor in [self.vendor.itemText(i) for i in range(self.vendor.count())]:
            self.vendor.setCurrentText(cam.vendor)
        self.enabled.setChecked(cam.enabled)

    def get_camera(self) -> Camera:
        cam = self.cam
        cam.name = self.name.text().strip() or self.ip.text().strip()
        cam.ip = self.ip.text().strip()
        cam.port = self.port.value()
        cam.username = self.user.text().strip()
        cam.password = self.pwd.text()
        cam.channel = self.channel.value()
        cam.stream_type = "main" if self.stream.currentIndex() == 0 else "sub"
        cam.protocol = self.protocol.currentData() or "rtsp"
        cam.vendor = self.vendor.currentText()
        cam.enabled = self.enabled.isChecked()
        cam.stream_uri = self.uri.text().strip()
        return cam
