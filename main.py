"""应用入口。"""
import os
import sys

# Linux：必须让 Qt 走 X11(xcb) 平台。
# 原因：本程序通过 libvlc 的 set_xwindow(X11 窗口 ID) 把视频嵌进自制窗口；
# 若 Qt 使用 Wayland 平台，winId() 不是 X11 窗口，VLC 会在 XWayland 里另开窗口，
# 表现为视频画面/「无信号」框与主界面错位、重叠。只要存在 DISPLAY(XWayland/原生 X11)
# 就强制 xcb（即使环境里已有 QT_QPA_PLATFORM=wayland;xcb，也改为 xcb）。
# 需要强制其它平台时，设置环境变量 EASYVIEW_QT_PLATFORM 覆盖。
if sys.platform.startswith("linux") and os.environ.get("DISPLAY"):
    os.environ["QT_QPA_PLATFORM"] = os.environ.get("EASYVIEW_QT_PLATFORM", "xcb")

from PyQt6.QtCore import QtMsgType, qInstallMessageHandler
from PyQt6.QtWidgets import QApplication

from core.crypto import reset_all_passwords
from core.database import init_db
from ui.main_window import MainWindow
from ui.theme import apply_theme


def _qt_message_handler(mode: QtMsgType, context, message: str) -> None:
    """过滤 VLC 嵌入式子窗口触发的良性 Qt 警告。

    VLC 通过 set_xwindow 把视频渲染进 QFrame 的子原生窗口时，X11/窗口管理器会向该
    子窗口发送窗口状态变化，Qt 对非顶层 QWidgetWindow 打印
    "QWidgetWindow(...) must be a top level window."。该警告不影响播放，属噪声。
    设置 EASYVIEW_QT_DEBUG=1 可关闭过滤，查看全部 Qt 输出。
    """
    if "must be a top level window" in message and not os.environ.get("EASYVIEW_QT_DEBUG"):
        return
    stream = sys.stderr
    stream.write(message + "\n")
    stream.flush()


def main():
    # 命令行紧急恢复：清空所有摄像机密码（保留元数据），不启动 GUI
    if "--reset-vault" in sys.argv:
        init_db()
        n = reset_all_passwords()
        print(f"[--reset-vault] 已清空 {n} 条摄像机的密码字段。")
        print("请重新打开应用并逐个编辑摄像机重新输入密码。")
        return 0

    init_db()
    qInstallMessageHandler(_qt_message_handler)
    app = QApplication(sys.argv)
    apply_theme(app)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
