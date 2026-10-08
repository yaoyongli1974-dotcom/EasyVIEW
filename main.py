"""应用入口。"""
import sys

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
