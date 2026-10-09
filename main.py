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

from PyQt6.QtWidgets import QApplication

from core.crypto import reset_all_passwords
from core.database import init_db
from ui.main_window import MainWindow

# 简易深色主题，统一 Windows / Linux 观感
DARK_STYLE = """
QMainWindow, QWidget { background-color: #1e1e1e; color: #e6e6e6; }
QToolBar { background: #2b2b2b; border: none; spacing: 4px; padding: 4px; }
QPushButton { background: #3a3a3a; color: #e6e6e6; border: 1px solid #4a4a4a;
              padding: 5px 10px; border-radius: 3px; }
QPushButton:hover { background: #4a4a4a; }
QListWidget { background: #252526; border: 1px solid #3a3a3a; }
QLabel { color: #cfcfcf; }
QDialog, QMenu { background: #2b2b2b; color: #e6e6e6; }
QLineEdit, QSpinBox, QComboBox { background: #1e1e1e; color: #e6e6e6;
              border: 1px solid #4a4a4a; padding: 3px; }
"""


def main():
    # 命令行紧急恢复：清空所有摄像机密码（保留元数据），不启动 GUI
    if "--reset-vault" in sys.argv:
        init_db()
        n = reset_all_passwords()
        print(f"[--reset-vault] 已清空 {n} 条摄像机的密码字段。")
        print("请重新打开应用并逐个编辑摄像机重新输入密码。")
        return 0

    init_db()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_STYLE)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
