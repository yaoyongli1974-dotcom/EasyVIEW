"""ONVIF 设备自动发现对话框（WS-Discovery）。"""
from PyQt6.QtCore import pyqtSignal, QThread, Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from core.camera import Camera
from core.onvif_device import OnvifDevice
from core.onvif_discovery import discover
from core.rtsp_templates import match_vendor


class DiscoverWorker(QThread):
    found = pyqtSignal(dict)
    finished = pyqtSignal()

    def run(self):
        try:
            for dev in discover(timeout=3.0):
                self.found.emit(dev)
        except Exception as e:  # 探测失败也反馈
            self.found.emit({"error": str(e)})
        self.finished.emit()


class DiscoveryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ONVIF 设备发现")
        self.resize(560, 480)
        self.result_camera: Camera | None = None
        self._devices: list[dict] = []
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        self.btn_scan = QPushButton("开始发现")
        self.btn_scan.clicked.connect(self._scan)
        top.addWidget(self.btn_scan)
        top.addStretch(1)
        lay.addLayout(top)

        self.list = QListWidget()
        self.list.currentItemChanged.connect(self._on_select)
        lay.addWidget(self.list, 2)

        # 选中设备详情 + 凭据
        self.info = QLabel("未发现设备。点击「开始发现」搜索局域网 ONVIF 摄像机。")
        self.info.setWordWrap(True)
        lay.addWidget(self.info)

        cred = QHBoxLayout()
        self.user = QLineEdit(); self.user.setPlaceholderText("用户名(通常 admin)")
        self.pwd = QLineEdit(); self.pwd.setEchoMode(QLineEdit.EchoMode.Password)
        self.pwd.setPlaceholderText("密码")
        cred.addWidget(QLabel("账号")); cred.addWidget(self.user)
        cred.addWidget(QLabel("密码")); cred.addWidget(self.pwd)
        lay.addLayout(cred)

        btn_row = QHBoxLayout()
        self.btn_uri = QPushButton("获取流地址")
        self.btn_uri.clicked.connect(self._fetch_uri)
        self.btn_add = QPushButton("添加所选")
        self.btn_add.clicked.connect(self._add)
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_uri)
        btn_row.addWidget(self.btn_add)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_cancel)
        lay.addLayout(btn_row)

        self._worker = None

    def _scan(self):
        self.list.clear()
        self._devices = []
        self.btn_scan.setEnabled(False)
        self._worker = DiscoverWorker()
        self._worker.found.connect(self._on_found)
        self._worker.finished.connect(lambda: self.btn_scan.setEnabled(True))
        self._worker.start()

    def _on_found(self, dev: dict):
        if "error" in dev:
            QMessageBox.warning(self, "发现错误", dev["error"])
            return
        self._devices.append(dev)
        label = f"{dev.get('manufacturer','?')} {dev.get('model','')} @ {dev.get('address','?')}"
        self.list.addItem(label)

    def _selected(self) -> dict | None:
        row = self.list.currentRow()
        if 0 <= row < len(self._devices):
            return self._devices[row]
        return None

    def _on_select(self, _cur, _prev):
        dev = self._selected()
        if dev:
            self.info.setText(
                f"厂商: {dev.get('manufacturer','?')}\n型号: {dev.get('model','?')}\n"
                f"IP: {dev.get('address','?')}\nXAddrs: {dev.get('xaddrs') or '?'}"
            )

    def _fetch_uri(self):
        dev = self._selected()
        if not dev:
            return
        ip = dev.get("address")
        user = self.user.text().strip()
        pwd = self.pwd.text()
        if not user:
            QMessageBox.warning(self, "提示", "请先填写账号密码再获取流地址")
            return
        try:
            dev_api = OnvifDevice(ip, 554, user, pwd)
            uri = dev_api.stream_uri()
            self._last_uri = uri
            QMessageBox.information(self, "流地址", f"已获取 RTSP：\n{uri}")
        except Exception as e:
            self._last_uri = None
            QMessageBox.warning(self, "获取失败", f"ONVIF 取流失败：{e}")

    def _add(self):
        dev = self._selected()
        if not dev:
            return
        ip = dev.get("address")
        user = self.user.text().strip()
        pwd = self.pwd.text()
        if not user:
            QMessageBox.warning(self, "提示", "请填写账号密码")
            return
        vendor = match_vendor(dev.get("manufacturer", ""))
        cam = Camera(
            name=f"{dev.get('manufacturer','IPC')} {ip}",
            ip=ip,
            port=554,
            username=user,
            password=pwd,
            vendor=vendor,
            stream_uri=getattr(self, "_last_uri", "") or "",
        )
        self.result_camera = cam
        self.accept()
