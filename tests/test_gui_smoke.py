"""GUI 冒烟测试（offscreen）：主窗口与对话框可构造，覆盖历史崩溃点。"""


def test_main_window_constructs(qt_app, tmp_db):
    from ui.main_window import MainWindow

    win = MainWindow()
    win.show()
    qt_app.processEvents()
    assert "EasyVIEW" in win.windowTitle()
    win.close()


def test_camera_dialog_roundtrip(qt_app):
    from ui.camera_dialog import CameraDialog

    dlg = CameraDialog()
    dlg.name.setText("前门")
    dlg.ip.setText("10.0.0.1")
    dlg.user.setText("admin")
    dlg.pwd.setText("secret")
    cam = dlg.get_camera()
    assert cam.name == "前门"
    assert cam.ip == "10.0.0.1"
    assert cam.password == "secret"

    # 重新载入已保存的摄像机，字段应回填一致
    dlg2 = CameraDialog(cam)
    assert dlg2.get_camera().ip == "10.0.0.1"
    assert dlg2.get_camera().protocol == cam.protocol


def test_http_protocol_uses_full_uri(qt_app):
    from ui.camera_dialog import CameraDialog

    dlg = CameraDialog()
    dlg.ip.setText("127.0.0.1")
    dlg.uri.setText("http://127.0.0.1:8080/cam1/index.m3u8")
    dlg.protocol.setCurrentIndex(1)  # HTTP/HLS
    cam = dlg.get_camera()
    assert cam.rtsp_url() == "http://127.0.0.1:8080/cam1/index.m3u8"


def test_auto_layout_counts():
    from ui.layouts import auto_layout

    # 完美平方 -> 等分，全部 1×1
    r, c, tiles = auto_layout(9)
    assert (r, c) == (3, 3)
    assert len(tiles) == 9
    assert all(rs == 1 and cs == 1 for _, _, rs, cs in tiles)

    # 6 -> 1 大(2×2) + 5 小，铺满 3×3
    r, c, tiles = auto_layout(6)
    assert (r, c) == (3, 3)
    assert len(tiles) == 6
    big = [t for t in tiles if t[2] == 2 and t[3] == 2]
    assert big == [(0, 0, 2, 2)]
    assert len(tiles) - 1 == 5

    # 数量上限
    r, c, tiles = auto_layout(999, max_channels=64)
    assert len(tiles) == 64


def test_video_grid_layout(qt_app):
    import vlc
    from ui.video_grid import VideoGrid

    inst = vlc.Instance(["--no-audio", "--verbose=0"])
    g = VideoGrid(inst)
    g.resize(900, 600)
    g.show()
    g.apply_layout(2, 2)
    qt_app.processEvents()
    assert g.current_layout == (2, 2)
    for w in g.widgets[:4]:
        assert w.isVisible()
    for w in g.widgets[4:]:
        assert not w.isVisible()
    g.grab()  # 触发 paintEvent，确保分隔线绘制不崩溃
    inst.release()


def test_video_grid_apply_count_featured(qt_app):
    """6 窗口 -> 1 大 + 5 小，可正常绘制与还原。"""
    import vlc
    from ui.video_grid import VideoGrid

    inst = vlc.Instance(["--no-audio", "--verbose=0"])
    g = VideoGrid(inst)
    g.resize(900, 600)
    g.show()
    assert g.apply_count(6) == 6
    qt_app.processEvents()
    assert g.current_count == 6
    assert g.current_layout == (3, 3)
    assert all(w.isVisible() for w in g.widgets[:6])
    assert not g.widgets[6].isVisible()
    g.grab()
    inst.release()


def test_fullscreen_in_place_and_restore(qt_app):
    """回归：全屏不得把含原生视频子窗口的控件重挂为顶层窗口。"""
    import vlc
    from ui.video_grid import VideoGrid

    inst = vlc.Instance(["--no-audio", "--verbose=0"])
    g = VideoGrid(inst)
    g.resize(900, 600)
    g.show()
    g.apply_layout(2, 2)
    qt_app.processEvents()

    target = g.widgets[0]
    assert g.enter_fullscreen(target) is target
    qt_app.processEvents()
    assert g.fullscreen_widget is target
    assert target.isVisible()
    assert target.parent() is g          # 不脱离窗口层级
    assert not g.widgets[1].isVisible()  # 兄弟窗隐藏

    g.exit_fullscreen()
    qt_app.processEvents()
    assert g.fullscreen_widget is None
    assert g.current_layout == (2, 2)
    assert all(w.isVisible() for w in g.widgets[:4])
    inst.release()


def test_window_fullscreen_keeps_all_panes(qt_app, tmp_db):
    """视窗全屏保留全部窗格，仅隐藏框架；单路全屏只显示一路。"""
    from ui.main_window import MainWindow

    w = MainWindow()
    w.show()
    w._set_count(6)
    qt_app.processEvents()

    w._window_fullscreen()
    qt_app.processEvents()
    assert w._fs_mode == "window"
    assert sum(1 for x in w.grid.widgets if x.isVisible()) == 6
    assert not w.menuBar().isVisible()
    assert not w.left_widget.isVisible()
    w._window_fullscreen()
    qt_app.processEvents()
    assert w._fs_mode is None
    assert w.menuBar().isVisible()
    assert w.left_widget.isVisible()

    w._enter_preview_fullscreen(w.grid.widgets[0])
    qt_app.processEvents()
    assert w._fs_mode == "preview"
    assert w.grid.fullscreen_widget is w.grid.widgets[0]
    assert sum(1 for x in w.grid.widgets if x.isVisible()) == 1
    w._exit_preview_fullscreen()
    qt_app.processEvents()
    assert w._fs_mode is None
    assert sum(1 for x in w.grid.widgets if x.isVisible()) == 6
    w.close()


def test_main_window_grid_and_window_controls(qt_app, tmp_db):
    from ui.main_window import MainWindow

    w = MainWindow()
    assert w.max_btn.text() in ("最大化", "还原")
    assert 1 <= w.count_spin.value() <= 64

    w._set_count(1)
    assert w.grid.current_count == 1
    w._add_slot()
    assert w.grid.current_count == 2
    w._set_count(6)
    assert w.grid.current_count == 6
    assert w.grid.current_layout == (3, 3)
    w._remove_slot()
    assert w.grid.current_count == 5
    w.close()


def test_list_double_click_keeps_layout(qt_app, tmp_db):
    """回归：双击左侧列表摄像机不得改变分屏布局或进入全屏。"""
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest

    from core.camera import Camera, add_camera
    from ui.main_window import MainWindow

    add_camera(Camera(name="t", ip="127.0.0.1", port=1))
    w = MainWindow()
    w.show()
    w._set_count(4)
    qt_app.processEvents()

    item = w.cam_list.item(0)
    assert item is not None
    rect = w.cam_list.visualItemRect(item)
    QTest.mouseDClick(w.cam_list.viewport(), Qt.MouseButton.LeftButton,
                      Qt.KeyboardModifier.NoModifier, rect.center())
    qt_app.processEvents()

    assert w.grid.current_count == 4
    assert w.grid.current_layout == (2, 2)
    assert w.grid.fullscreen_widget is None
    assert w.isFullScreen() is False
    w.close()
