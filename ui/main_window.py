"""主窗口：左摄像机列表 + 右预览网格，支持自动分屏、单路/整墙全屏。

极简预览客户端：
- 自适应屏幕：首次启动按可用屏幕区域居中并自适应尺寸；
- 记忆布局：退出时用 QSettings 保存窗口几何 / 最大化状态与窗口数量，下次恢复；
- 灵活分屏：输入窗口数量（1~64）自动排版（等分 / 1 大 + N 小），也可动态增删窗口。
"""
from PyQt6.QtCore import Qt, QSettings, QEvent
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from core.camera import Camera, add_camera, delete_camera, test_connection, update_camera
from core.config import MAX_CHANNELS, VLC_ARGS
# 必须在 import vlc 之前完成 VLC 运行时路径注入（core.config 在导入时执行 _inject_vlc_path）
import vlc
from ui.camera_dialog import CameraDialog
from ui.camera_list import CameraListPanel
from ui.channel_manager import ChannelManager
from ui.video_grid import VideoGrid


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EasyVIEW  视频预览客户端")
        self.resize(1360, 860)

        # 全局共享一个 LibVLC 实例（所有 MediaPlayer 共用）
        self.instance = vlc.Instance(VLC_ARGS)

        self._build_body()
        self._build_menu()
        self._build_toolbar()
        self._wire()
        # 恢复上次窗口几何/状态与网格布局（首次启动则自适应屏幕）
        self._restore_window()

    # ---------- 菜单栏 ----------
    def _menu_action(self, menu, text, slot, shortcut=None):
        act = menu.addAction(text)
        if shortcut:
            act.setShortcut(QKeySequence(shortcut))
        act.triggered.connect(slot)
        return act

    def _build_menu(self):
        mbar = self.menuBar()

        filem = mbar.addMenu("文件(&F)")
        self._menu_action(filem, "添加摄像机…", self._add_camera)
        self._menu_action(filem, "监控通道管理…", self._open_channel_manager)
        filem.addSeparator()
        self._menu_action(filem, "退出", self.close, "Ctrl+Q")

        view = mbar.addMenu("视图(&V)")
        self._menu_action(view, "单画面", lambda: self._set_count(1), "Ctrl+1")
        self._menu_action(view, "4画面", lambda: self._set_count(4), "Ctrl+2")
        self._menu_action(view, "6画面（1大+5小）", lambda: self._set_count(6), "Ctrl+3")
        self._menu_action(view, "9画面", lambda: self._set_count(9))
        self._menu_action(view, "16画面", lambda: self._set_count(16))
        self._menu_action(view, "自定义窗口数…", self._custom_layout)
        view.addSeparator()
        self._menu_action(view, "添加窗口", self._add_slot)
        self._menu_action(view, "删除窗口", self._remove_slot)
        view.addSeparator()
        self._menu_action(view, "视窗全屏 / 退出全屏", self._window_fullscreen, "F11")
        self._menu_action(view, "停止全部", self.grid.clear_all)

        # 窗口控制按钮固定到菜单栏右上角，始终可见
        self._build_window_buttons()

    def _build_window_buttons(self):
        box = QWidget()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(4, 0, 6, 0)
        lay.setSpacing(4)
        self.min_btn = QPushButton("最小化")
        self.min_btn.setObjectName("winBtn")
        self.min_btn.clicked.connect(self.showMinimized)
        self.max_btn = QPushButton("最大化")
        self.max_btn.setObjectName("winBtn")
        self.max_btn.clicked.connect(self._toggle_max)
        self.close_btn = QPushButton("关闭")
        self.close_btn.setObjectName("closeBtn")
        self.close_btn.clicked.connect(self.close)
        for b in (self.min_btn, self.max_btn, self.close_btn):
            b.setFixedHeight(22)
            lay.addWidget(b)
        self.menuBar().setCornerWidget(box, Qt.Corner.TopRightCorner)

    # ---------- 工具栏 ----------
    def _build_toolbar(self):
        """精简工具栏：只保留高频的分屏操作。"""
        tb = QToolBar("主工具栏")
        tb.setObjectName("mainToolBar")
        tb.setMovable(False)
        self.addToolBar(tb)
        self.main_toolbar = tb
        tb.addWidget(QLabel("窗口数"))
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, MAX_CHANNELS)
        self.count_spin.setValue(1)
        self.count_spin.setToolTip(f"1~{MAX_CHANNELS} 路，自动分配「等分」或「1 大 + N 小」")
        self.count_spin.valueChanged.connect(self._apply_count)
        tb.addWidget(self.count_spin)
        self._add_btn(tb, "应用", self._apply_count)
        tb.addSeparator()
        self._add_btn(tb, "通道管理", self._open_channel_manager)
        tb.addSeparator()
        for n in (1, 4, 6, 9, 16):
            self._add_btn(tb, str(n), lambda _checked=False, v=n: self._set_count(v))
        tb.addSeparator()
        self._add_btn(tb, "添加窗口", self._add_slot)
        self._add_btn(tb, "删除窗口", self._remove_slot)
        tb.addSeparator()
        self._add_btn(tb, "视窗全屏", self._window_fullscreen, name="accent")
        self._add_btn(tb, "停止全部", self.grid.clear_all)

    def _add_btn(self, tb: QToolBar, text: str, slot, name: str = None) -> QPushButton:
        btn = QPushButton(text)
        if name:
            btn.setObjectName(name)
        btn.clicked.connect(slot)
        tb.addWidget(btn)
        return btn

    # ---------- 主体 ----------
    def _build_body(self):
        left = QVBoxLayout()
        left.setContentsMargins(8, 10, 4, 8)
        left.setSpacing(6)
        title = QLabel("摄像机")
        title.setObjectName("sideTitle")
        left.addWidget(title)
        self.cam_list = CameraListPanel()
        left.addWidget(self.cam_list)
        left_widget = QWidget()
        left_widget.setLayout(left)
        left_widget.setMinimumWidth(200)
        left_widget.setMaximumWidth(320)
        self.left_widget = left_widget

        self.grid = VideoGrid(self.instance)

        body = QWidget()
        body.setObjectName("CentralRoot")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(6, 6, 8, 8)
        body_layout.setSpacing(8)
        body_layout.addWidget(left_widget)
        body_layout.addWidget(self.grid, 1)
        self.setCentralWidget(body)

    def _wire(self):
        self.cam_list.playRequested.connect(self._on_play_requested)
        self.cam_list.editRequested.connect(self._edit_camera)
        self.cam_list.deleteRequested.connect(self._delete_camera)
        self.cam_list.testRequested.connect(self._test_camera)
        self.grid.fullscreenRequested.connect(self._enter_preview_fullscreen)
        self.grid.fullscreenExitRequested.connect(self._exit_preview_fullscreen)

    # ---------- 窗口几何 / 状态 ----------
    @staticmethod
    def _as_bool(v) -> bool:
        if isinstance(v, bool):
            return v
        return str(v).lower() in ("1", "true", "yes", "on")

    def _fit_to_screen(self):
        """按可用屏幕区域自适应尺寸并居中（不大于设计尺寸，且绝不超出屏幕）。"""
        screen = QApplication.primaryScreen()
        if screen is None:
            self.resize(1360, 860)
            return
        avail = screen.availableGeometry()
        w = min(1360, int(avail.width() * 0.95), avail.width())
        h = min(860, int(avail.height() * 0.95), avail.height())
        w = max(480, w)
        h = max(360, h)
        self.resize(w, h)
        self.move(avail.x() + (avail.width() - w) // 2, avail.y() + (avail.height() - h) // 2)

    def _ensure_on_screen(self):
        """校验恢复的窗口几何：若尺寸超屏或位置跑到屏幕外，则回退为自适应。"""
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        g = self.geometry()
        if g.width() > avail.width() or g.height() > avail.height() or not avail.intersects(g):
            self._fit_to_screen()
            return
        x = min(max(g.x(), avail.x()), avail.right() - g.width() + 1)
        y = min(max(g.y(), avail.y()), avail.bottom() - g.height() + 1)
        if x != g.x() or y != g.y():
            self.move(x, y)

    def _restore_window(self):
        self._settings = QSettings("EasyVIEW", "EasyVIEW")
        geo = self._settings.value("window/geometry")
        if geo is not None:
            self.restoreGeometry(geo)
            self._ensure_on_screen()
        else:
            self._fit_to_screen()
        try:
            n = int(self._settings.value("grid/count", 1))
            if 1 <= n <= MAX_CHANNELS:
                self._set_count(n)
        except (TypeError, ValueError):
            pass
        if self._as_bool(self._settings.value("window/maximized")):
            self.showMaximized()
        self._sync_max_btn()

    def _save_window(self):
        try:
            self._settings.setValue("window/geometry", self.saveGeometry())
            self._settings.setValue("window/maximized", self.isMaximized())
            self._settings.setValue("grid/count", self.grid.current_count)
        except Exception:
            pass

    def _toggle_max(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        self._sync_max_btn()

    def _sync_max_btn(self):
        if getattr(self, "max_btn", None) is not None:
            self.max_btn.setText("还原" if self.isMaximized() else "最大化")

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
            self._sync_max_btn()
        super().changeEvent(event)

    # ---------- 网格控制 ----------
    def _set_count(self, n: int):
        """按窗口数量应用布局（自动等分 / 1 大 + N 小）。"""
        n = max(1, min(int(n), MAX_CHANNELS))
        self.count_spin.blockSignals(True)
        self.count_spin.setValue(n)
        self.count_spin.blockSignals(False)
        self.grid.apply_count(n)

    def _apply_count(self):
        self._set_count(self.count_spin.value())

    def _add_slot(self):
        cur = self.grid.current_count or self.count_spin.value()
        if cur >= MAX_CHANNELS:
            self.statusBar().showMessage(f"已是最大分屏（{MAX_CHANNELS} 路）")
            return
        n = cur + 1
        self._set_count(n)
        self.statusBar().showMessage(f"已添加窗口：共 {n} 路")

    def _remove_slot(self):
        cur = self.grid.current_count or self.count_spin.value()
        if cur <= 1:
            return
        n = cur - 1
        self._set_count(n)
        self.statusBar().showMessage(f"已删除窗口：共 {n} 路")

    def _custom_layout(self):
        n, ok = QInputDialog.getInt(
            self, "自定义窗口数", f"输入窗口数量（1~{MAX_CHANNELS}）:",
            self.grid.current_count or 1, 1, MAX_CHANNELS,
        )
        if ok:
            self._set_count(n)

    # ---------- 摄像机操作 ----------
    def _on_play_requested(self, cam):
        slot = self.grid.play_camera(cam)
        if slot is not None:
            self.statusBar().showMessage(f"设备「{cam.name}」已上墙到 窗口{slot + 1}")
        else:
            self.statusBar().showMessage("没有可用窗口，请先增加窗口数量")

    def _open_channel_manager(self):
        """打开监控通道管理窗口（非模态，可边管理边预览）。"""
        dlg = getattr(self, "_channel_manager", None)
        if dlg is None:
            dlg = ChannelManager(self)
            dlg.playRequested.connect(self._play_channels)
            dlg.changed.connect(self.cam_list.refresh)
            self._channel_manager = dlg
        dlg.refresh()
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _play_channels(self, cams):
        """上墙若干路：单路进当前窗格（不改布局）；多路按数量自动分屏。"""
        cams = [c for c in cams if c is not None]
        if not cams:
            return
        if len(cams) == 1:
            self._on_play_requested(cams[0])
            return
        if self.grid.current_count < len(cams):
            self._set_count(len(cams))
        n = self.grid.current_count
        free = [i for i in range(n) if self.grid.widgets[i].camera is None]
        order = free + [i for i in range(n) if i not in free]
        last = None
        for cam, slot in zip(cams, order):
            self.grid.widgets[slot].set_camera(cam)
            last = slot
        if last is not None:
            self.grid.on_select(self.grid.widgets[last])
        self.statusBar().showMessage(f"已上墙 {min(len(cams), n)} 路")

    def _add_camera(self):
        dlg = CameraDialog()
        if dlg.exec():
            add_camera(dlg.get_camera())
            self.cam_list.refresh()

    def _edit_camera(self, cam: Camera):
        dlg = CameraDialog(cam)
        if dlg.exec():
            update_camera(dlg.get_camera())
            self.cam_list.refresh()

    def _delete_camera(self, cam: Camera):
        if cam.id is None:
            return
        if QMessageBox.question(self, "确认", f"删除摄像机「{cam.name}」？") == QMessageBox.StandardButton.Yes:
            delete_camera(cam.id)
            self.cam_list.refresh()

    def _test_camera(self, cam: Camera):
        ok, msg = test_connection(cam)
        QMessageBox.information(self, "连接测试", f"[{'成功' if ok else '失败'}] {msg}")

    # ---------- 布局 / 全屏 ----------
    def _window_fullscreen(self):
        """视窗全屏：整个主窗口铺满屏幕（保留当前所有窗格），隐藏框架。

        与「单路全屏」（双击某窗格触发）不同——后者只放大一路画面。
        """
        if getattr(self, "_fs_mode", None) == "window":
            self._exit_window_fullscreen()
        else:
            self._enter_window_fullscreen()

    def _hide_chrome(self):
        """记录并隐藏菜单/工具栏/状态栏/列表（幂等，重复调用不覆盖快照）。"""
        if getattr(self, "_chrome_hidden", False):
            return
        self._chrome_hidden = True
        self._fs_state = {
            "maximized": self.isMaximized(),
            "menu": self.menuBar().isVisible(),
            "toolbar": self.main_toolbar.isVisible(),
            "status": self.statusBar().isVisible(),
            "left": self.left_widget.isVisible(),
        }
        self.menuBar().hide()
        self.main_toolbar.hide()
        self.statusBar().hide()
        self.left_widget.hide()

    def _show_chrome(self):
        if not getattr(self, "_chrome_hidden", False):
            return
        self._chrome_hidden = False
        st = getattr(self, "_fs_state", None) or {}
        if st.get("menu", True):
            self.menuBar().show()
        if st.get("toolbar", True):
            self.main_toolbar.show()
        if st.get("status", True):
            self.statusBar().show()
        if st.get("left", True):
            self.left_widget.show()

    def _leave_fullscreen_window_state(self):
        """从全屏恢复到（进入前的）普通/最大化窗口状态。"""
        if not getattr(self, "_chrome_hidden", False):
            return
        self.showNormal()
        st = getattr(self, "_fs_state", None) or {}
        if st.get("maximized"):
            self.showMaximized()
        self._sync_max_btn()

    def _enter_window_fullscreen(self):
        # 若当前处于单路全屏，先还原回网格再看整窗全屏
        if getattr(self, "_fs_mode", None) == "preview" and self.grid.fullscreen_widget is not None:
            self.grid.exit_fullscreen()
        self._hide_chrome()
        self.showFullScreen()
        self._fs_mode = "window"

    def _exit_window_fullscreen(self):
        if getattr(self, "_fs_mode", None) != "window":
            return
        self._fs_mode = None
        self._leave_fullscreen_window_state()
        self._show_chrome()

    def _enter_preview_fullscreen(self, target=None):
        """单路全屏（双击窗格）：隐藏框架，让目标预览铺满整屏。

        直接对现有主窗口 showFullScreen，而不是把预览控件浮出为新的顶层窗口——
        含原生 VLC 子窗口的控件重挂为顶层后，平铺式 Wayland（XWayland）会拒绝全屏。
        """
        if self.grid.fullscreen_widget is not None:
            return
        if target is None:
            target = self.grid.active_widget or next(
                (w for w in self.grid.widgets if w.isVisible()), None
            )
        if target is None:
            return
        if self.grid.enter_fullscreen(target) is None:
            return
        self._hide_chrome()
        self.showFullScreen()
        self._fs_mode = "preview"

    def _exit_preview_fullscreen(self):
        if self.grid.fullscreen_widget is None:
            return
        self.grid.exit_fullscreen()
        self._fs_mode = None
        self._leave_fullscreen_window_state()
        self._show_chrome()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if self.grid.fullscreen_widget is not None:
                self._exit_preview_fullscreen()
            elif getattr(self, "_fs_mode", None) == "window":
                self._exit_window_fullscreen()
        super().keyPressEvent(event)

    def closeEvent(self, event):
        if self.grid.fullscreen_widget is not None:
            self._exit_preview_fullscreen()
        elif getattr(self, "_fs_mode", None) == "window":
            self._exit_window_fullscreen()
        self._save_window()
        self.grid.clear_all()
        if self.instance:
            self.instance.release()
        super().closeEvent(event)
