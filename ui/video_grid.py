"""预览网格：1~64 路的自适应布局、单画面、全屏与拖拽交换。

v7（稳定性修复）
- 单元格定位交回 QGridLayout 管理（Qt 会在窗口缩放时批量、正确地重排原生视频窗口），
  避免手工 setGeometry 在缩放过程中频繁移动 9 个原生窗口导致的画面残留/错位。
- 分隔线与选中高亮按「实际控件几何」绘制（画在 QGridLayout 的 spacing 间隙中，
  位于原生视频窗口之外，绝对可见且与真实布局一致）。
- 支持动态增删窗口（收缩时自动把被隐藏格子的设备迁移到空闲格子）。
"""
from PyQt6.QtCore import Qt, QPoint, QRect, pyqtSignal
from PyQt6.QtGui import QCursor, QColor, QPainter, QPen
from PyQt6.QtWidgets import QGridLayout, QWidget

import vlc

from core.config import MAX_CHANNELS
from ui.preview_widget import PreviewWidget
from ui.theme import ACCENT as ACCENT_HEX, GRID_BG, SEP as SEP_HEX

# 间隙宽度（px）：单元格之间留出的间距，分隔线画在间隙正中
GAP = 8
# 分隔线颜色：与主题一致的中性描边
SEP_COLOR = QColor(SEP_HEX)
# 选中窗高亮颜色：主题强调色（青）
ACTIVE_COLOR = QColor(ACCENT_HEX)
ACTIVE_THICK = 3
SEP_THICK = 2


class VideoGrid(QWidget):
    # 请求进入某路全屏 / 退出全屏（窗口级全屏由 MainWindow 负责）
    fullscreenRequested = pyqtSignal(object)
    fullscreenExitRequested = pyqtSignal()

    def __init__(self, vlc_instance: vlc.Instance, max_channels: int = MAX_CHANNELS):
        super().__init__()
        self.instance = vlc_instance
        self.max_channels = max_channels

        # 预创建 MAX_CHANNELS 个预览控件，布局切换时复用，避免频繁创建销毁 MediaPlayer
        self.widgets = []
        for i in range(max_channels):
            w = PreviewWidget(vlc_instance, i)
            w.doubleClicked.connect(self.on_double_click)
            w.selected.connect(self.on_select)
            w.dragSwapRequested.connect(self.on_drag_swap)
            w.escapeRequested.connect(self.on_escape)
            w.clearRequested.connect(self.on_clear)
            self.widgets.append(w)

        self.grid = QGridLayout(self)
        self.grid.setSpacing(GAP)
        self.grid.setContentsMargins(GAP, GAP, GAP, GAP)

        # 网格底色：深空黑，突出画面
        pal = self.palette()
        pal.setColor(self.backgroundRole(), QColor(GRID_BG))
        self.setPalette(pal)
        self.setAutoFillBackground(True)

        self.current_layout = (1, 1)
        self.single_widget = None
        self.active_widget = None
        self.fullscreen_widget = None
        self.apply_layout(1, 1)

    # ---------- 布局管理 ----------
    def _clear(self):
        while self.grid.count():
            self.grid.takeAt(0)

    def apply_layout(self, rows: int, cols: int, tiles=None):
        """应用分屏。

        tiles 为可选窗格列表 ``(row, col, row_span, col_span)``；缺省时按
        rows×cols 等分。窗格数量即上墙窗口数（≤ len(tiles)）。
        """
        rows = max(1, min(int(rows), self.max_channels))
        cols = max(1, min(int(cols), self.max_channels))
        if tiles is None:
            count = min(rows * cols, self.max_channels)
            tiles = [(i // cols, i % cols, 1, 1) for i in range(count)]
        else:
            count = min(len(tiles), self.max_channels)
            tiles = list(tiles[:count])

        # 收缩时把将被隐藏格子的设备迁移到新的空闲格子，避免上墙丢失
        orphans = [(w, w.camera) for w in self.widgets[count:] if w.camera is not None]
        for w, _ in orphans:
            w.set_camera(None)
        free = [self.widgets[i] for i in range(count) if self.widgets[i].camera is None]
        for _, cam in orphans:
            if not free:
                break
            free.pop(0).set_camera(cam)

        self._clear()
        for idx, w in enumerate(self.widgets[:count]):
            r, c, rs, cs = tiles[idx]
            self.grid.addWidget(w, r, c, rs, cs)
            w.show()
        for w in self.widgets[count:]:
            w.set_camera(None)
            w.hide()
        self.current_layout = (rows, cols)
        self.current_tiles = tiles
        self.single_widget = None
        self.update()

    def apply_count(self, n: int):
        """按窗口数量自动排版（含「1 大 + N 小」）。"""
        from ui.layouts import auto_layout

        rows, cols, tiles = auto_layout(n, self.max_channels)
        self.apply_layout(rows, cols, tiles)
        return len(tiles)

    @property
    def current_count(self) -> int:
        return len(getattr(self, "current_tiles", []) or [])

    def _active_widgets(self):
        """当前处于网格中的可见控件（全屏浮出的不算）。"""
        return [w for w in self.widgets if w.isVisible() and w.parent() is self]

    # ---------- 选中 / 双击 / 清空 ----------
    def on_double_click(self, widget: PreviewWidget):
        if self.fullscreen_widget is widget:
            self.fullscreenExitRequested.emit()
            return
        self.fullscreenRequested.emit(widget)

    def on_select(self, widget: PreviewWidget):
        self.active_widget = widget
        for w in self.widgets:
            w.set_active(w is widget)
        self.update()

    def on_clear(self, widget: PreviewWidget):
        widget.set_camera(None)
        if self.active_widget is widget:
            self.active_widget = None
        widget.set_active(False)
        self.update()

    # ---------- 拖拽交换两路画面 ----------
    def on_drag_swap(self, src: PreviewWidget):
        if self.fullscreen_widget:
            return
        if not src.isVisible():
            return
        gp = QCursor.pos()
        for w in self._active_widgets():
            if w is src:
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
        """网格内只显示 widget 并铺满整个网格区（不脱离窗口层级）。

        真正的窗口级全屏（隐藏工具栏/列表/停靠窗并 showFullScreen）由 MainWindow
        负责。这里刻意不把控件 setParent(None) 浮出为顶层窗口：含原生 VLC 子窗口
        （video_frame）的控件一旦被重新挂载为顶层窗口，XWayland（Hyprland 等平铺式
        Wayland 合成器）会拒绝其全屏请求，表现为「全屏不了」。
        """
        if self.fullscreen_widget is not None:
            return None
        target = widget or self.active_widget or self.widgets[0]
        if target is None or not target.isVisible():
            return None
        self._fs_prev_layout = self.current_layout
        self._fs_prev_tiles = self.current_tiles
        self._clear()
        self.grid.addWidget(target, 0, 0)
        for w in self.widgets:
            w.setVisible(w is target)
        self.fullscreen_widget = target
        self.update()
        return target

    def exit_fullscreen(self):
        if self.fullscreen_widget is None:
            return
        self.fullscreen_widget = None
        # 还原到全屏前的分屏布局（含「1 大 + N 小」的跨格窗格）
        rows, cols = getattr(self, "_fs_prev_layout", self.current_layout)
        tiles = getattr(self, "_fs_prev_tiles", None)
        self.apply_layout(rows, cols, tiles)

    def on_escape(self, widget: PreviewWidget):
        if self.fullscreen_widget is widget:
            self.fullscreenExitRequested.emit()

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

    # ---------- 分隔线绘制（按实际控件几何，画在间隙中）----------
    def paintEvent(self, event):
        super().paintEvent(event)
        if self.fullscreen_widget is not None:
            return
        active = self.active_widget
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        exp_off = GAP // 2
        # 第一遍：所有 cell 画中性分隔线
        for w in self._active_widgets():
            if w is active:
                continue
            rect = w.geometry()
            if rect.width() <= 0 or rect.height() <= 0:
                continue
            painter.setPen(QPen(SEP_COLOR, SEP_THICK))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect.adjusted(-exp_off, -exp_off, exp_off, exp_off))
        # 第二遍：激活 cell 画品牌蓝高亮
        if active is not None and active.parent() is self and active.isVisible():
            rect = active.geometry()
            if rect.width() > 0 and rect.height() > 0:
                painter.setPen(QPen(ACTIVE_COLOR, ACTIVE_THICK))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(rect.adjusted(-exp_off, -exp_off, exp_off, exp_off))
        painter.end()
