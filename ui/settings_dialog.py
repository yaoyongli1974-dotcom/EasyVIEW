"""解码 / 渲染设置对话框。

把"解码模式"与"视频输出模块"做成界面可点选，写入 settings.json，重启后生效。
环境变量 EASYVIEW_VLC_HW / EASYVIEW_VLC_VOUT 仍可临时覆盖（优先级最高、无需重启）。

背景：预览黑屏的根因是 Windows 下 LibVLC 默认 direct3d vout 把画面渲染到独立 surface，
set_hwnd 拿不到像素。软件解码（none）+ wingdi（GDI 直绘进 HWND）是最稳组合。若某台机器
wingdi 异常，可在本对话框切 directdraw / direct3d11 排查，无需重装。
"""
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)

from core.config import HW_MODE, VOUT, set_hw_mode, set_vout_mode

HW_OPTIONS = [
    ("none", "软件解码（默认·最稳）"),
    ("dxva2", "DXVA2 硬件加速"),
    ("d3d11va", "D3D11VA 硬件加速"),
    ("any", "自动（VLC 自选）"),
]
# vout 选项：wingdi 为根治黑屏的默认推荐；auto 表示交给 VLC 自选。
VOUT_OPTIONS = [
    ("wingdi", "wingdi（GDI 直绘·推荐）"),
    ("directdraw", "directdraw（GDI 的 DX 前身·备选）"),
    ("direct3d11", "direct3d11（需配合硬件解码）"),
    ("auto", "auto（交 VLC 自选）"),
]


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("解码 / 渲染设置")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.hw_combo = QComboBox()
        for val, label in HW_OPTIONS:
            self.hw_combo.addItem(label, val)
        self._select(self.hw_combo, HW_MODE)

        self.vout_combo = QComboBox()
        for val, label in VOUT_OPTIONS:
            self.vout_combo.addItem(label, val)
        # VOUT 为 None 表示"auto / 交 VLC 自选"
        self._select(self.vout_combo, VOUT or "auto")

        form.addRow("解码模式 (hw):", self.hw_combo)
        form.addRow("视频输出 (vout):", self.vout_combo)
        layout.addLayout(form)

        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet("color:#9aa0a6; font-size:12px;")
        self._update_summary()
        layout.addWidget(self.summary)

        self.hint = QLabel(
            "说明：修改后需重启程序生效。\n"
            "临时覆盖（立即生效、无需重启）可在启动前设置环境变量：\n"
            "  EASYVIEW_VLC_HW=none|dxva2|d3d11va|any\n"
            "  EASYVIEW_VLC_VOUT=wingdi|directdraw|direct3d11|auto"
        )
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("color:#9aa0a6; font-size:12px;")
        layout.addWidget(self.hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.hw_combo.currentIndexChanged.connect(self._update_summary)
        self.vout_combo.currentIndexChanged.connect(self._update_summary)

    @staticmethod
    def _select(combo: QComboBox, value: str):
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _update_summary(self):
        hw = self.hw_combo.currentData()
        vout = self.vout_combo.currentData()
        bits = [f"--avcodec-hw={hw}"]
        if vout != "auto":
            bits.append(f"--vout={vout}")
        else:
            bits.append("--vout=(VLC 自选)")
        self.summary.setText("重启后实际生效参数： " + "  ".join(bits))

    def accept(self):
        hw = self.hw_combo.currentData()
        vout = self.vout_combo.currentData()
        set_hw_mode(hw)
        set_vout_mode(vout)
        super().accept()
