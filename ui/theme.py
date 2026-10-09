"""EasyVIEW 现代深色主题（科技感）。

集中定义配色与全局 QSS，供 main.py 统一应用；网格/预览控件引用同一套色值，
保证整体观感一致。
"""

# ---------- 配色 ----------
BG = "#0b0f19"          # 应用底色（深空蓝黑）
BG_DEEP = "#0e1420"     # 工具栏/状态栏/输入框底
PANEL = "#111726"       # 面板/菜单底
SURFACE = "#151c2e"     # 卡片/次级面
SURFACE_HI = "#1b2438"  # hover
BORDER = "#26304a"      # 常规描边
BORDER_HI = "#334261"   # hover 描边
TEXT = "#e6edf7"        # 主文字
TEXT_DIM = "#8b98b0"    # 次要文字
TEXT_MUTE = "#5b6880"   # 禁用文字
ACCENT = "#22d3ee"      # 主强调色（青）
ACCENT_2 = "#3b82f6"    # 次强调色（蓝）
ACCENT_SOFT = "rgba(34, 211, 238, 0.14)"
DANGER = "#f43f5e"
OK = "#22c55e"
WARN = "#f59e0b"

# 预览网格专用
GRID_BG = "#070a12"     # 网格底色（比应用底色更深，突出画面）
SEP = "#2a3650"         # 窗格分隔线

FONT_STACK = '"Noto Sans CJK SC", "Source Han Sans SC", "Microsoft YaHei", "Segoe UI", "PingFang SC", sans-serif'


QSS = f"""
* {{
    font-family: {FONT_STACK};
    font-size: 13px;
    color: {TEXT};
    outline: none;
}}

QMainWindow, QDialog, QMessageBox, QInputDialog, QWidget#CentralRoot {{
    background: {BG};
}}

QLabel {{ color: {TEXT}; background: transparent; }}
QLabel#hint, QLabel#dim {{ color: {TEXT_DIM}; }}
QLabel#sideTitle {{
    color: {ACCENT};
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 2px;
    padding: 2px 4px 2px 6px;
}}

/* ---------- 菜单栏 ---------- */
QMenuBar {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {PANEL}, stop:1 {BG});
    padding: 3px 6px;
    border-bottom: 1px solid {BORDER};
    spacing: 2px;
}}
QMenuBar::item {{
    padding: 6px 12px;
    border-radius: 7px;
    background: transparent;
}}
QMenuBar::item:selected {{ background: {SURFACE_HI}; color: {ACCENT}; }}
QMenuBar::item:pressed {{ background: {ACCENT_SOFT}; }}

QMenu {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 6px;
}}
QMenu::item {{
    padding: 7px 26px 7px 14px;
    border-radius: 6px;
}}
QMenu::item:selected {{ background: {ACCENT_SOFT}; color: {ACCENT}; }}
QMenu::item:disabled {{ color: {TEXT_MUTE}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 6px 8px; }}

/* ---------- 工具栏 ---------- */
QToolBar {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {BG_DEEP}, stop:1 {BG});
    border: none;
    border-bottom: 1px solid {BORDER};
    spacing: 6px;
    padding: 7px 10px;
}}
QToolBar::separator {{
    background: {BORDER};
    width: 1px;
    margin: 4px 8px;
}}
QToolBar QLabel {{ color: {TEXT_DIM}; padding: 0 2px; }}

/* ---------- 按钮 ---------- */
QPushButton {{
    background: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 6px 13px;
    border-radius: 8px;
}}
QPushButton:hover {{ background: {SURFACE_HI}; border-color: {BORDER_HI}; }}
QPushButton:pressed {{
    background: {ACCENT_SOFT};
    border-color: {ACCENT};
    color: {ACCENT};
}}
QPushButton:disabled {{ color: {TEXT_MUTE}; border-color: {BORDER}; background: {BG_DEEP}; }}
QPushButton:focus {{ border-color: {ACCENT}; }}

/* 工具栏里的按钮走「幽灵」风格，更轻盈 */
QToolBar QPushButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 6px 11px;
}}
QToolBar QPushButton:hover {{ background: {SURFACE_HI}; border-color: {BORDER}; }}
QToolBar QPushButton:pressed {{
    background: {ACCENT_SOFT}; border-color: {ACCENT}; color: {ACCENT};
}}

/* 主按钮 / 窗口控制按钮 */
QPushButton#accent {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {ACCENT_2}, stop:1 {ACCENT});
    color: #04121a;
    border: none;
    font-weight: 600;
}}
QPushButton#accent:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {ACCENT}, stop:1 {ACCENT_2});
}}
QPushButton#winBtn {{
    background: transparent;
    border: 1px solid {BORDER};
    padding: 3px 11px;
    border-radius: 6px;
    color: {TEXT_DIM};
}}
QPushButton#winBtn:hover {{ background: {SURFACE_HI}; color: {TEXT}; }}
QPushButton#closeBtn {{
    background: transparent;
    border: 1px solid {BORDER};
    padding: 3px 11px;
    border-radius: 6px;
    color: {TEXT_DIM};
}}
QPushButton#closeBtn:hover {{ background: {DANGER}; border-color: {DANGER}; color: white; }}

/* ---------- 输入控件 ---------- */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {BG_DEEP};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 9px;
    selection-background-color: {ACCENT};
    selection-color: #04121a;
}}
QLineEdit:hover, QSpinBox:hover, QComboBox:hover {{ border-color: {BORDER_HI}; }}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {ACCENT}; }}
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{ color: {TEXT_MUTE}; }}

QSpinBox::up-button, QSpinBox::down-button {{
    background: transparent;
    width: 15px;
    border: none;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{ background: {SURFACE_HI}; border-radius: 4px; }}

QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 4px;
    selection-background-color: {ACCENT_SOFT};
    selection-color: {ACCENT};
    outline: 0;
}}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border-radius: 5px;
    border: 1px solid {BORDER_HI};
    background: {BG_DEEP};
}}
QCheckBox::indicator:hover {{ border-color: {ACCENT}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}

/* ---------- 列表 ---------- */
QListWidget {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 5px;
}}
QListWidget::item {{
    padding: 8px 10px;
    border-radius: 7px;
    margin: 2px 1px;
    color: {TEXT};
}}
QListWidget::item:hover {{ background: {SURFACE_HI}; }}
QListWidget::item:selected {{
    background: {ACCENT_SOFT};
    color: {ACCENT};
    border: 1px solid rgba(34, 211, 238, 0.45);
}}

/* ---------- 树（通道管理）---------- */
QTreeWidget {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 4px;
    show-decoration-selected: 1;
}}
QTreeWidget::item {{ padding: 5px 6px; border-radius: 6px; color: {TEXT}; }}
QTreeWidget::item:hover {{ background: {SURFACE_HI}; }}
QTreeWidget::item:selected {{ background: {ACCENT_SOFT}; color: {ACCENT}; }}
QTreeView::branch {{ background: transparent; }}
QHeaderView::section {{
    background: {BG_DEEP};
    color: {TEXT_DIM};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 7px 8px;
}}

/* ---------- 滚动条 ---------- */
QScrollBar:vertical {{ background: transparent; width: 11px; margin: 3px; }}
QScrollBar::handle:vertical {{
    background: {BORDER_HI};
    min-height: 30px;
    border-radius: 5px;
}}
QScrollBar::handle:vertical:hover {{ background: {ACCENT}; }}
QScrollBar:horizontal {{ background: transparent; height: 11px; margin: 3px; }}
QScrollBar::handle:horizontal {{
    background: {BORDER_HI};
    min-width: 30px;
    border-radius: 5px;
}}
QScrollBar::handle:horizontal:hover {{ background: {ACCENT}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; background: none; border: none; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QScrollBar::corner {{ background: transparent; }}

/* ---------- 状态栏 ---------- */
QStatusBar {{
    background: {BG_DEEP};
    color: {TEXT_DIM};
    border-top: 1px solid {BORDER};
}}
QStatusBar::item {{ border: none; }}

/* ---------- 提示 / 其它 ---------- */
QToolTip {{
    background: {PANEL};
    color: {TEXT};
    border: 1px solid {BORDER_HI};
    border-radius: 6px;
    padding: 5px 8px;
}}
QDialog QLabel {{ color: {TEXT}; }}
"""


def apply_theme(app) -> None:
    """把主题应用到 QApplication。"""
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)
