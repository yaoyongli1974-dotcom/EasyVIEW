"""预览网格：管理 1~9 路 PreviewWidget 的布局、单画面、全屏与拖拽交换。

分隔线方案（v5，优雅中性 + 真机绝对可见）：
分隔线画在「单元格自身」会被 video_frame 的 WA_NativeWindow 原生窗口吃掉，故改为由
网格容器 VideoGrid 自己画——VideoGrid 是普通 QWidget（非原生），paintEvent 100% 可靠；
用 QGridLayout 的 spacing 在单元格间留「间隙」，间隙属于网格自身、不在任何原生视频窗口
矩形内，因此画什么绝对可见。v5 视觉升级为「监控墙边框」风格：中性石板灰细线作为分隔，
选中窗整圈品牌蓝高亮，均画在间隙正中而非压在视频上。
"""
from PyQt6.QtCore import Qt, QPoint, QRect
from PyQt6.QtGui import QCursor, QPalette, QColor, QPainter, QPen
from PyQt6.QtWidgets import QGridLayout, QWidget

import vlc

from core.config import MAX_CHANNELS
from ui.preview_widget import PreviewWidget

# 间隙宽度（px）：单元格之间留出的间距，分隔线画在间隙正中
GAP = 6
# 分隔线颜色：中性石板灰（监控墙「边框」质感），深色视频上也清晰但不刺眼
SEP_COLOR = QColor("#64748b")
# 选中窗高亮颜色：品牌蓝
ACTIVE_COLOR = QColor("#2d8cf0")
ACTIVE_THICK = 3
SEP_THICK = 2


class VideoGrid(QWidget):
    def __init__(self, vlc_instance: vlc.Instance, max_channels: int = MAX_CHANNELS):
        super().__init__()
        self.instance = vlc_instance
        self.max_channels = max_channels

        # 预创建 MAX_CHANNELS 个预览控件，布局切换时复用，避免频繁创建销毁 MediaPlayer
        self.widgets = [PreviewWidget(vlc_instance, i) for i in range(max_channels)]
        for w in self.widgets:
            w.doubleClicked.connect(self.on_double_click)
            w.selected.connect(self.on_select)
            w.dragSwapRequested.connect(self.on_drag_swap)
            w.escapeRequested.connect(self.on_escape)
            w.clearRequested.connect(self.on_clear)

        self.grid = QGridLayout(self)
        # 单元格之间留出 GAP px 间隙，间隙由网格自身背景填充（见 palette）。
        self.grid.setSpacing(GAP)
        self.grid.setContentsMargins(GAP, GAP, GAP, GAP)
        # 网格底色：深灰，让亮金分隔线对比鲜明
        pal = self.palette()
        pal.setColor(self.backgroundRole(), QColor("#111827"))
        self.setPalette(pal)
        self.setAutoFillBackground(True)
        self.setLayout(self.grid)

        self.current_layout = (1, 1)
        self.single_widget = None
        self.active_widget = None
        self.fullscreen_widget = None
        self.apply_layout(1, 1)

    # ---------- 布局管理 ----------
    def _clear(self):
        while self.grid.count():
            self.grid.takeAt(0)

    def apply_layout(self, rows: int, cols: int):
        rows = max(1, min(rows, self.max_channels))
        cols = max(1, min(cols, self.max_channels))
        self._clear()
        count = min(rows * cols, self.max_channels)
        for idx, w in enumerate(self.widgets[:count]):
            r, c = divmod(idx, cols)
            self.grid.addWidget(w, r, c)
            w.show()
        for w in self.widgets[count:]:
            w.set_camera(None)
            w.hide()
        self.current_layout = (rows, cols)
        self.single_widget = None
        self.update()   # 布局变化后立即重绘分隔线

    def on_double_click(self, widget: PreviewWidget):
        if self.fullscreen_widget is widget:
            self.exit_fullscreen()
            return
        self.enter_fullscreen(widget)

    def on_select(self, widget: PreviewWidget):
        self.active_widget = widget
        for w in self.widgets:
            w.set_active(w is widget)
        self.update()   # 选中态变化，重绘高亮

    def on_clear(self, widget: PreviewWidget):
        widget.set_camera(None)
        if self.active_widget is widget:
            self.active_widget = None
        widget.set_active(False)
        self.update()

    # ---------- 拖拽交换两路画面 ----------
    def on_drag_swap(self, src: PreviewWidget):
        if self.single_widget or self.fullscreen_widget:
            return
        if not src.isVisible():
            return
        gp = QCursor.pos()
        for w in self.widgets:
            if w is src or not w.isVisible():
                continue
            topleft = w.mapToGlobal(QPoint(0, 0))
            rect = QRect(topleft, w.size())
            if rect.contains(gp):
                self._swap(src, w)
                return

    def _swap(self, a: PreviewWidget, b: PreviewWidget):
        a.camera, b.camera = b.camera, a.camera
        a.set_camera(a.camera)
        b.set_camera(b.camera)

    # ---------- 全屏 ----------
    def enter_fullscreen(self, widget: PreviewWidget = None):
        if self.fullscreen_widget:
            return
        target = widget or self.active_widget or self.widgets[0]
        if target is None or not target.isVisible():
            return
        target.setParent(None)
        target.setWindowFlags(Qt.WindowType.Window)
        target.showFullScreen()
        target.activateWindow()
        target.setFocus()
        target.reattach()
        self.fullscreen_widget = target

    def exit_fullscreen(self):
        if not self.fullscreen_widget:
            return
        w = self.fullscreen_widget
        w.setWindowFlags(Qt.WindowType.Widget)
        idx = self.widgets.index(w)
        r, c = self.current_layout
        if self.single_widget is w:
            self.grid.addWidget(w, 0, 0, r, c)
        else:
            rr, cc = divmod(idx, c)
            self.grid.addWidget(w, rr, cc)
        w.show()
        w.raise_()
        w.reattach()
        self.fullscreen_widget = None
        self.update()

    def on_escape(self, widget: PreviewWidget):
        if self.fullscreen_widget is widget:
            self.exit_fullscreen()

    # ---------- 播放控制 ----------
    def play_camera(self, camera, slot: int = None) -> int | None:
        if slot is None:
            if self.active_widget is not None and self.active_widget.isVisible():
                slot = self.widgets.index(self.active_widget)
            else:
                slot = self._next_free_slot()
        if slot is None or slot >= self.max_channels:
            return None
        self.widgets[slot].set_camera(camera)
        self.on_select(self.widgets[slot])
        return slot

    def _next_free_slot(self):
        for i, w in enumerate(self.widgets):
            if w.camera is None and w.isVisible():
                return i
        return 0

    def clear_all(self):
        for w in self.widgets:
            w.set_camera(None)
        self.active_widget = None
        self.single_widget = None
        self.update()

    # ---------- 分隔线绘制（核心，网格自身，绝对可见）----------
    def _cell_geometry(self, idx: int, rows: int, cols: int):
        """按网格自身尺寸直接算第 idx 个单元格的矩形（不依赖 cellRect，避免布局未激活时失效）。"""
        m = GAP  # 与 setContentsMargins 一致
        total_w = self.width()
        total_h = self.height()
        inner_w = total_w - 2 * m
        inner_h = total_h - 2 * m
        cw = (inner_w - (cols - 1) * GAP) / cols
        ch = (inner_h - (rows - 1) * GAP) / rows
        rr, cc = divmod(idx, cols)
        x = m + cc * (cw + GAP)
        y = m + rr * (ch + GAP)
        return QRect(int(round(x)), int(round(y)), int(round(cw)), int(round(ch)))

    def paintEvent(self, event):
        super().paintEvent(event)
        rows, cols = self.current_layout
        n = min(rows * cols, self.max_channels)
        if n == 0 or self.width() <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        # 线画在「间隙正中」（cell 边界外 GAP//2 px），完全落在间隙内，
        # 不压在 video_frame 原生窗口上，因此始终可见、播放中也可见。
        exp_off = GAP // 2
        # 第一遍：非激活 cell 画中性分隔线
        for idx in range(n):
            w = self.widgets[idx]
            if w is self.active_widget:
                continue
            rect = self._cell_geometry(idx, rows, cols)
            if rect.width() <= 0 or rect.height() <= 0:
                continue
            painter.setPen(QPen(SEP_COLOR, SEP_THICK))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect.adjusted(-exp_off, -exp_off, exp_off, exp_off))
        # 第二遍：激活 cell 画品牌蓝高亮（后画，覆盖与邻居共享的间隙，形成完整蓝框）
        if self.active_widget is not None and self.active_widget.isVisible():
            idx = self.widgets.index(self.active_widget)
            if 0 <= idx < n:
                rect = self._cell_geometry(idx, rows, cols)
                if rect.width() > 0 and rect.height() > 0:
                    painter.setPen(QPen(ACTIVE_COLOR, ACTIVE_THICK))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawRect(rect.adjusted(-exp_off, -exp_off, exp_off, exp_off))
        painter.end()
