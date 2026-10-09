"""单路视频预览控件：封装一个 VLC MediaPlayer，渲染到子窗口句柄。

交互在事件过滤器中统一处理（v8）：
- 每路只保留「一个原生窗口」video_frame 作为 VLC 渲染目标，鼠标事件直接在其
  eventFilter 中处理。v5~v7 曾在 video_frame 之上叠加一个「透明原生」click_catcher
  来接管鼠标，但那会让每个单元格产生 2 个原生窗口；9 路即 18 个相互堆叠的原生窗口，
  在没有合成器（compositor）的 X11 上极易出现画面残留/重叠。现予移除。
- 空白态显示 overlay（无信号）接收事件；播放态由 video_frame 接收。

分隔线 / 选中高亮不由本控件画（原生窗口会盖掉自身矩形内的 Qt 绘制），改由 VideoGrid
在单元格「间隙」区绘制（见 video_grid.py）—— 间隙不在任何原生视频窗口矩形内，绝对可见。
"""
import sys
import time
from pathlib import Path

from PyQt6.QtCore import Qt, QEvent, QTimer, QSize, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QFrame, QLabel, QMenu, QSizePolicy, QVBoxLayout, QWidget

# 必须先用 core.config 完成 VLC 运行时路径注入，再 import vlc
from core.config import DATA_DIR, HW_MODE, VOUT
from core.camera import Camera
from ui.theme import ACCENT, TEXT_DIM

import vlc


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
        self._aspect = "auto"   # 画面比例：auto/16:9/4:3/1:1
        # 尺寸策略：始终「可扩展」，避免视频未播放（video_frame 隐藏）时尺寸提示为 0，
        # 导致 QGridLayout 在某路开始播放后把空间全给该路、其余窗格塌缩为 0。
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._setup_ui()
        # 事件过滤器挂在视频层与各覆盖层：鼠标事件不再依赖额外的透明原生窗口
        self.video_frame.installEventFilter(self)
        self.overlay.installEventFilter(self)
        self.badge.installEventFilter(self)

    def sizeHint(self):
        return QSize(160, 120)

    def minimumSizeHint(self):
        return QSize(80, 60)

    def _setup_ui(self):
        # VLC 渲染目标：稳定原生窗口（HWND），set_hwnd 直渲
        self.video_frame = QFrame(self)
        self.video_frame.setFrameShape(QFrame.Shape.NoFrame)
        self.video_frame.setMinimumSize(80, 60)
        self.video_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.video_frame.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        # 不透明自绘：避免半透明/合成路径在无合成器的 X11 上产生残影
        self.video_frame.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        pal_vf = self.video_frame.palette()
        pal_vf.setColor(self.video_frame.backgroundRole(), QColor("black"))
        self.video_frame.setPalette(pal_vf)
        self.video_frame.setAutoFillBackground(True)
        self.video_frame.setMouseTracking(True)

        # 「无信号」提示层（空窗态显示；原生窗口之上不可靠，故空窗时单独置顶）
        self.overlay = QLabel(self)
        self.overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overlay.setText("无信号")
        self.overlay.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 13px; letter-spacing: 3px;"
        )

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
        if active:
            self.badge.setStyleSheet(
                f"background: {ACCENT}; color: #04121a; border-radius: 4px; "
                f"padding: 1px 6px; font-size: 11px; font-weight: 800;"
            )
        else:
            self.badge.setStyleSheet(
                "background: rgba(11,15,25,180); color: #8b98b0; "
                "border: 1px solid rgba(38,48,74,180); border-radius: 4px; "
                "padding: 1px 6px; font-size: 11px; font-weight: 700;"
            )
        self.badge.setText(str(self.channel_index + 1))

    def _show_empty_layers(self):
        """空窗态：隐藏视频层，显示「无信号」并置顶（由 overlay 收鼠标）。"""
        self.video_frame.hide()
        self.overlay.show()
        self.overlay.raise_()
        self.badge.raise_()

    def _show_playing_layers(self):
        """播放态：显示视频层，「无信号」隐藏。"""
        self.overlay.hide()
        self.video_frame.show()
        self.badge.raise_()

    def set_active(self, flag: bool):
        if self._is_active != flag:
            self._is_active = flag
            self._style_badge(flag)

    def resizeEvent(self, event):
        w, h = self.width(), self.height()
        self.video_frame.setGeometry(0, 0, w, h)
        self.overlay.setGeometry(0, 0, w, h)
        self.badge.setGeometry(6, 6, 22, 18)
        # 按当前状态维持正确的置顶层
        if self.camera is None:
            self.overlay.raise_()
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
                               QTimer.singleShot(0, self._rebind_hwnd)),
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
        self._apply_aspect(media)
        self.player.set_media(media)
        self.player.play()
        QTimer.singleShot(120, self._rebind_hwnd)
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
            p = Path(DATA_DIR) / "easyview_debug.log"
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
        except Exception:
            pass

    # ---------- 画面比例 ----------
    def _apply_aspect(self, media):
        if self._aspect and self._aspect != "auto":
            # VLC 媒体级选项：强制源画面比例（等比缩放到窗口）
            media.add_option(f":aspect-ratio={self._aspect}")

    def set_aspect(self, aspect: str):
        """设置画面比例并即时重连当前流使其生效。"""
        self._aspect = aspect or "auto"
        if self.camera is not None:
            self.start()

    # ---------- 右键菜单 ----------
    def _show_context_menu(self, global_pos):
        menu = QMenu(self)
        if self.camera is not None:
            menu.addAction("清空窗口", lambda: self.clearRequested.emit(self))
            menu.addSeparator()
            ratio = menu.addMenu("画面比例")
            for label, val in [("自动（等比）", "auto"), ("16:9", "16:9"),
                               ("4:3", "4:3"), ("1:1", "1:1")]:
                act = ratio.addAction(label)
                act.setCheckable(True)
                act.setChecked(self._aspect == val)
                act.triggered.connect(lambda _checked=False, v=val: self.set_aspect(v))
        else:
            menu.addAction("（无信号）", lambda: None)
            menu.addAction("清空窗口", lambda: self.clearRequested.emit(self))
        menu.exec(global_pos)

    # ---------- 事件过滤器：全部交互的统一入口 ----------
    def eventFilter(self, obj, event):
        if obj in (self.video_frame, self.overlay, self.badge):
            t = event.type()
            if t == QEvent.Type.MouseButtonDblClick:
                self._on_double_click()
                return True
            if t == QEvent.Type.MouseButtonPress:
                self._on_press(event)
                return True
            if t == QEvent.Type.MouseButtonRelease:
                if event.button() == Qt.MouseButton.RightButton:
                    self._show_context_menu(event.globalPosition().toPoint())
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

    # 全屏时键盘焦点在本控件自身（而非子层），需在此兜底处理 Esc
    def keyPressEvent(self, event):
        self._on_key(event)

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
