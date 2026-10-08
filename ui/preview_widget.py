"""单路视频预览控件：封装一个 VLC MediaPlayer，渲染到子窗口句柄。

交互统一在事件过滤器中处理。关键修复（v5）：
之前 video_frame 是 WA_NativeWindow 原生窗口，VLC 直渲进去后 Win32 把鼠标事件
直接发给这个原生 HWND，Qt 的 eventFilter 收不到单击，导致「点窗口无法选中」。
v5 新增一层透明原生 click_catcher（置于 video_frame 之上、视觉全透明），由它专门
接收鼠标事件并转发，VLC 渲染与鼠标捕获互不干扰，单击/双击/右键/拖拽全部可靠。

分隔线 / 选中高亮不由本控件画（原生窗口会盖掉自身矩形内的 Qt 绘制），改由 VideoGrid
在单元格「间隙」区绘制（见 video_grid.py）—— 间隙不在任何原生视频窗口矩形内，绝对可见。
"""
import os
import sys
import time
from pathlib import Path

from PyQt6.QtCore import Qt, QEvent, QTimer, pyqtSignal
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout, QWidget

import vlc
from core.camera import Camera
from core.config import DATA_DIR, HW_MODE, VOUT


class PreviewWidget(QWidget):
    doubleClicked = pyqtSignal(object)      # 双击 -> 切换单画面 / 退出全屏
    selected = pyqtSignal(object)           # 单击 -> 选中（激活 / 全屏目标）
    clearRequested = pyqtSignal(object)     # 右键 -> 清空该窗口（停止并解除设备）
    dragSwapRequested = pyqtSignal(object)  # 拖拽到其他窗口 -> 请求交换画面
    escapeRequested = pyqtSignal(object)    # 全屏下按 ESC -> 请求退出全屏

    def __init__(self, vlc_instance: vlc.Instance, channel_index: int = 0):
        super().__init__()
        self.channel_index = channel_index
        self.camera: Camera = None
        self.instance = vlc_instance
        self.player: vlc.MediaPlayer = None
        self._is_active = False
        self._press_pos = None
        self._dragging = False
        self._setup_ui()
        # 三层都挂事件过滤器：视频态由 click_catcher 收，空窗态由 overlay 收
        self.video_frame.installEventFilter(self)
        self.click_catcher.installEventFilter(self)
        self.overlay.installEventFilter(self)

    def _setup_ui(self):
        # VLC 渲染目标：稳定原生窗口（HWND），set_hwnd 直渲
        self.video_frame = QFrame(self)
        self.video_frame.setFrameShape(QFrame.Shape.NoFrame)
        self.video_frame.setMinimumSize(160, 120)
        self.video_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.video_frame.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        pal_vf = self.video_frame.palette()
        pal_vf.setColor(self.video_frame.backgroundRole(), QColor("black"))
        self.video_frame.setPalette(pal_vf)
        self.video_frame.setAutoFillBackground(True)

        # 透明点击捕获层：原生窗口、置于 video_frame 之上、视觉全透明，但「吃」鼠标事件
        self.click_catcher = QFrame(self)
        self.click_catcher.setFrameShape(QFrame.Shape.NoFrame)
        self.click_catcher.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self.click_catcher.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.click_catcher.setMouseTracking(True)

        # 「无信号」提示层（空窗态显示；原生窗口之上不可靠，故空窗时单独置顶）
        self.overlay = QLabel(self)
        self.overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overlay.setText("无信号")
        self.overlay.setStyleSheet("color: #9aa0a6; font-size: 13px;")

        # 窗口序号徽标：左上角常驻（鼠标穿透），便于在多个窗口间区分
        self.badge = QLabel(self)
        self.badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._style_badge(False)

        # 自身底色黑：空窗态也保持黑底，与视频一致
        pal_self = self.palette()
        pal_self.setColor(self.backgroundRole(), QColor("black"))
        self.setPalette(pal_self)
        self.setAutoFillBackground(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.video_frame)
        self.setLayout(layout)

        # 初始为空窗态
        self._show_empty_layers()

    def _style_badge(self, active: bool):
        bg = "#2d8cf0" if active else "rgba(15,15,15,150)"
        self.badge.setStyleSheet(
            f"background:{bg}; color:white; border-radius:3px; "
            f"padding:1px 5px; font-size:11px; font-weight:bold;"
        )
        self.badge.setText(str(self.channel_index + 1))

    def _show_empty_layers(self):
        """空窗态：隐藏视频与点击层，显示「无信号」并置顶（由 overlay 收鼠标）。"""
        self.video_frame.hide()
        self.click_catcher.hide()
        self.overlay.show()
        self.overlay.raise_()
        self.badge.raise_()

    def _show_playing_layers(self):
        """播放态：显示视频层，透明点击层置顶收鼠标，「无信号」隐藏。"""
        self.overlay.hide()
        self.video_frame.show()
        self.click_catcher.show()
        self.click_catcher.raise_()
        self.badge.raise_()

    def set_active(self, flag: bool):
        if self._is_active != flag:
            self._is_active = flag
            self._style_badge(flag)

    def resizeEvent(self, event):
        w, h = self.width(), self.height()
        self.video_frame.setGeometry(0, 0, w, h)
        self.click_catcher.setGeometry(0, 0, w, h)
        self.overlay.setGeometry(0, 0, w, h)
        self.badge.setGeometry(6, 6, 22, 18)
        # 按当前状态维持正确的置顶层
        if self.camera is None:
            self.overlay.raise_()
        else:
            self.click_catcher.raise_()
        self.badge.raise_()
        super().resizeEvent(event)

    # ---------- 播放控制 ----------
    def set_camera(self, camera: Camera):
        self.camera = camera
        if camera is None:
            self.stop()
            self.overlay.setText("无信号")
            self._show_empty_layers()
            return
        self._show_playing_layers()
        self.start()

    def start(self):
        if self.camera is None or self.instance is None:
            return
        if self.player is None:
            self.player = self.instance.media_player_new()
            try:
                self.player.event_manager().event_attach(
                    vlc.EventType.MediaPlayerVout,
                    lambda e: (self._log("vout created -> video output active"),
                               QTimer.singleShot(0, self.click_catcher.raise_)),
                )
            except Exception:
                pass
        try:
            self.video_frame.show()
            win_id = int(self.video_frame.winId())
            if sys.platform.startswith("win"):
                self.player.set_hwnd(win_id)
            else:
                self.player.set_xwindow(win_id)
            self._log(f"start bind hwnd={win_id} hw={HW_MODE} vout={VOUT} host={self._safe_url()}")
        except Exception as e:
            self._log(f"start bind hwnd FAILED: {e}")
        media = self.instance.media_new(self.camera.rtsp_url())
        media.add_option("network-caching=300")
        media.add_option("rtsp-tcp")
        self.player.set_media(media)
        self.player.play()
        QTimer.singleShot(120, self._rebind_hwnd)
        QTimer.singleShot(150, self.click_catcher.raise_)
        QTimer.singleShot(1500, self._check_playing)

    # ---------- 诊断辅助 ----------
    def _safe_url(self) -> str:
        try:
            u = self.camera.rtsp_url()
            if "://" in u:
                rest = u.split("://", 1)[1]
                return rest.split("@")[-1].split("/")[0]
            return u
        except Exception:
            return "<url-error>"

    def _log(self, msg: str):
        try:
            p = Path(DATA_DIR) / "ivms_debug.log"
            with open(p, "a", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S") + f" ch{self.channel_index} {msg}\n")
        except Exception:
            pass

    def _check_playing(self):
        if self.player is None:
            self._log("check: player is None")
            return
        if self.player.is_playing():
            self._log("check: PLAYING ok")
        else:
            self._log(f"check: NOT playing, state={self.player.get_state()}")

    def stop(self):
        if self.player:
            self.player.stop()

    def play_file(self, path: str):
        self.camera = None
        self.overlay.hide()
        self._show_playing_layers()
        if self.player is None:
            self.player = self.instance.media_player_new()
            win_id = int(self.video_frame.winId())
            if sys.platform.startswith("win"):
                self.player.set_hwnd(win_id)
            else:
                self.player.set_xwindow(win_id)
        media = self.instance.media_new("file:///" + path)
        media.add_option("network-caching=300")
        self.player.set_media(media)
        self.player.play()

    def is_playing(self) -> bool:
        return bool(self.player and self.player.is_playing())

    def _rebind_hwnd(self):
        if self.player is None:
            return
        try:
            win_id = int(self.video_frame.winId())
            if sys.platform.startswith("win"):
                self.player.set_hwnd(win_id)
            else:
                self.player.set_xwindow(win_id)
            self.video_frame.repaint()
            self.click_catcher.raise_()
        except Exception:
            pass

    def reattach(self):
        if self.player is None:
            return
        try:
            win_id = int(self.video_frame.winId())
            if sys.platform.startswith("win"):
                self.player.set_hwnd(win_id)
            else:
                self.player.set_xwindow(win_id)
            self.click_catcher.raise_()
        except Exception:
            pass

    # ---------- 截图抓拍 ----------
    def take_snapshot(self, path: str) -> bool:
        if self.player is None or not self.player.is_playing():
            return False
        try:
            return bool(self.player.video_take_snapshot(0, path, 0, 0))
        except Exception:
            return False

    # ---------- 事件过滤器：全部交互的统一入口 ----------
    def eventFilter(self, obj, event):
        if obj in (self.video_frame, self.click_catcher, self.overlay):
            t = event.type()
            if t == QEvent.Type.MouseButtonDblClick:
                self._on_double_click()
                return True
            if t == QEvent.Type.MouseButtonPress:
                self._on_press(event)
                return True
            if t == QEvent.Type.MouseButtonRelease:
                if event.button() == Qt.MouseButton.RightButton:
                    self.clearRequested.emit(self)
                    return True
                self._on_release(event)
                return True
            if t == QEvent.Type.MouseMove:
                self._on_move(event)
                return True
            if t == QEvent.Type.KeyPress:
                self._on_key(event)
                return True
        return super().eventFilter(obj, event)

    def _on_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.globalPosition().toPoint()
            self._dragging = False
            self.selected.emit(self)

    def _on_move(self, event):
        if self._press_pos is None:
            return
        if event.buttons() & Qt.MouseButton.LeftButton:
            p = event.globalPosition().toPoint()
            if abs(p.x() - self._press_pos.x()) + abs(p.y() - self._press_pos.y()) > 8:
                self._dragging = True

    def _on_release(self, event):
        if self._dragging and event.button() == Qt.MouseButton.LeftButton:
            self.dragSwapRequested.emit(self)
        self._dragging = False
        self._press_pos = None

    def _on_double_click(self):
        self.doubleClicked.emit(self)

    def _on_key(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.escapeRequested.emit(self)
        else:
            super().keyPressEvent(event)
