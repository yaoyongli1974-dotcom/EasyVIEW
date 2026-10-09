"""录像计划面板：定时 / 移动侦测计划的增删改与计划引擎启停。"""
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from PyQt6.QtCore import QTime, pyqtSignal

from core.camera import Camera
from core.recording_plan import (
    WEEKDAY_NAMES,
    RecordingPlan,
    add_plan,
    delete_plan,
    get_plan,
    list_plans,
    update_plan,
)


class PlanDialog(QDialog):
    """新增/编辑录像计划。"""

    def __init__(self, camera: Camera, plan: RecordingPlan = None, parent=None):
        super().__init__(parent)
        self.camera = camera
        self.plan = plan or RecordingPlan(camera_id=camera.id)
        self.setWindowTitle("编辑计划" if plan else "新建计划")
        self._build()
        if plan:
            self._load(plan)

    def _build(self):
        lay = QFormLayout(self)

        self.name = QLineEdit(); self.name.setPlaceholderText("计划名称（可选）")
        self.mode = QComboBox(); self.mode.addItems(["定时(schedule)", "移动侦测(motion)"])
        self.mode.currentTextChanged.connect(self._on_mode)
        lay.addRow("名称", self.name)
        lay.addRow("模式", self.mode)

        # ---- 定时参数 ----
        self.g_schedule = QGroupBox("定时参数")
        sv = QVBoxLayout()
        self.wd = [QCheckBox(n) for n in WEEKDAY_NAMES]
        wdh = QHBoxLayout()
        for c in self.wd:
            wdh.addWidget(c)
        sv.addLayout(wdh)
        th = QHBoxLayout()
        self.start_t = QTimeEdit(); self.start_t.setDisplayFormat("HH:mm")
        self.end_t = QTimeEdit(); self.end_t.setDisplayFormat("HH:mm")
        th.addWidget(QLabel("起")); th.addWidget(self.start_t)
        th.addWidget(QLabel("止")); th.addWidget(self.end_t)
        sv.addLayout(th)
        self.seg_s = QSpinBox(); self.seg_s.setRange(0, 3600); self.seg_s.setValue(0); self.seg_s.setSuffix(" s")
        sv.addWidget(QLabel("分段(秒,0=不分段)"))
        sv.addWidget(self.seg_s)
        self.g_schedule.setLayout(sv)
        lay.addRow(self.g_schedule)

        # ---- 移动侦测参数 ----
        self.g_motion = QGroupBox("移动侦测参数")
        mv = QVBoxLayout()
        self.sens = QSpinBox(); self.sens.setRange(1, 10); self.sens.setValue(5)
        self.mcon = QSpinBox(); self.mcon.setRange(1, 30); self.mcon.setValue(3)
        self.pre = QSpinBox(); self.pre.setRange(0, 60); self.pre.setValue(3); self.pre.setSuffix(" s")
        self.post = QSpinBox(); self.post.setRange(0, 120); self.post.setValue(10); self.post.setSuffix(" s")
        self.mind = QSpinBox(); self.mind.setRange(1, 600); self.mind.setValue(15); self.mind.setSuffix(" s")
        self.mseg = QSpinBox(); self.mseg.setRange(0, 3600); self.mseg.setValue(0); self.mseg.setSuffix(" s")
        for label, w in [
            ("灵敏度(1-10)", self.sens), ("连续帧数", self.mcon), ("预录(s)", self.pre),
            ("后录(s)", self.post), ("最短时长(s)", self.mind), ("分段(s)", self.mseg),
        ]:
            row = QHBoxLayout(); row.addWidget(QLabel(label)); row.addWidget(w); mv.addLayout(row)
        self.g_motion.setLayout(mv)
        lay.addRow(self.g_motion)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addRow(btns)
        self._on_mode(self.mode.currentText())

    def _on_mode(self, text):
        is_sched = text.startswith("定时")
        self.g_schedule.setVisible(is_sched)
        self.g_motion.setVisible(not is_sched)

    def _load(self, p: RecordingPlan):
        self.name.setText(p.name)
        self.mode.setCurrentText("定时(schedule)" if p.mode == "schedule" else "移动侦测(motion)")
        for i, c in enumerate(self.wd):
            c.setChecked(bool((p.weekdays >> i) & 1))
        h, m = divmod(p.start_min, 60)
        self.start_t.setTime(QTime(h, m))
        h, m = divmod(p.end_min, 60)
        self.end_t.setTime(QTime(h, m))
        self.seg_s.setValue(p.segment_seconds)
        self.sens.setValue(p.sensitivity)
        self.mcon.setValue(p.min_consecutive)
        self.pre.setValue(p.pre_seconds)
        self.post.setValue(p.post_seconds)
        self.mind.setValue(p.min_duration)
        self.mseg.setValue(p.segment_seconds)

    def get_plan(self) -> RecordingPlan:
        p = RecordingPlan(camera_id=self.camera.id)
        if self.plan and self.plan.id:
            p.id = self.plan.id
        p.name = self.name.text().strip()
        p.mode = "schedule" if self.mode.currentText().startswith("定时") else "motion"
        wd = 0
        for i, c in enumerate(self.wd):
            if c.isChecked():
                wd |= (1 << i)
        p.weekdays = wd
        p.start_min = self.start_t.time().hour() * 60 + self.start_t.time().minute()
        p.end_min = self.end_t.time().hour() * 60 + self.end_t.time().minute()
        # 分段时长按当前模式取对应控件（定时用 seg_s，移动侦测用 mseg）
        p.segment_seconds = self.seg_s.value() if p.mode == "schedule" else self.mseg.value()
        p.sensitivity = self.sens.value()
        p.min_consecutive = self.mcon.value()
        p.pre_seconds = self.pre.value()
        p.post_seconds = self.post.value()
        p.min_duration = self.mind.value()
        return p


class SchedulePanel(QWidget):
    statusChanged = pyqtSignal(str)

    def __init__(self, plan_engine, parent=None):
        super().__init__(parent)
        self.engine = plan_engine
        self.camera: Camera | None = None
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        self.state = QLabel("未选择摄像机")
        lay.addWidget(self.state)

        ctl = QHBoxLayout()
        self.btn_add = QPushButton("新建计划")
        self.btn_add.clicked.connect(self._add)
        self.btn_edit = QPushButton("编辑")
        self.btn_edit.clicked.connect(self._edit)
        self.btn_del = QPushButton("删除")
        self.btn_del.clicked.connect(self._del)
        self.btn_enable = QPushButton("启用/停用")
        self.btn_enable.clicked.connect(self._toggle)
        ctl.addWidget(self.btn_add); ctl.addWidget(self.btn_edit)
        ctl.addWidget(self.btn_del); ctl.addWidget(self.btn_enable)
        lay.addLayout(ctl)

        self.plan_list = QListWidget()
        self.plan_list.itemDoubleClicked.connect(self._edit)
        lay.addWidget(self.plan_list, 1)

        eng = QHBoxLayout()
        self.btn_engine = QPushButton("启动计划引擎")
        self.btn_engine.clicked.connect(self._toggle_engine)
        eng.addWidget(self.btn_engine)
        lay.addLayout(eng)
        self._sync_engine_btn()

    def set_camera(self, cam: Camera | None):
        self.camera = cam
        self._update_state()
        self._refresh()

    def _update_state(self):
        if self.camera is None:
            self.state.setText("未选择摄像机")
        else:
            self.state.setText(f"{self.camera.name}：{len(list_plans(self.camera.id))} 个计划")

    def _refresh(self):
        self.plan_list.clear()
        if not self.camera:
            return
        for p in list_plans(self.camera.id):
            tag = "定时" if p.mode == "schedule" else "移动"
            en = "启用" if p.enabled else "停用"
            label = f"[{en}] {p.name or p.id}  {tag}"
            if p.mode == "schedule":
                sh, sm = divmod(p.start_min, 60)
                eh, em = divmod(p.end_min, 60)
                label += f"  {sh:02d}:{sm:02d}-{eh:02d}:{em:02d}  wd={p.weekdays}"
            else:
                label += f"  灵敏{p.sensitivity} 后录{p.post_seconds}s"
            self.plan_list.addItem(label)
            self.plan_list.item(self.plan_list.count() - 1).setData(1, p.id)

    def _current_id(self) -> int | None:
        item = self.plan_list.currentItem()
        return item.data(1) if item else None

    def _add(self):
        if not self.camera:
            return
        dlg = PlanDialog(self.camera)
        if dlg.exec():
            add_plan(dlg.get_plan())
            self._refresh()

    def _edit(self):
        pid = self._current_id()
        if pid is None:
            return
        p = get_plan(pid)
        if p is None:
            return
        dlg = PlanDialog(self.camera, p)
        if dlg.exec():
            update_plan(dlg.get_plan())
            self._refresh()

    def _del(self):
        pid = self._current_id()
        if pid is not None:
            delete_plan(pid)
            self._refresh()

    def _toggle(self):
        pid = self._current_id()
        if pid is None:
            return
        p = get_plan(pid)
        if p is None:
            return
        p.enabled = not p.enabled
        update_plan(p)
        self._refresh()

    def _toggle_engine(self):
        if self.engine.running:
            self.engine.stop()
            self.statusChanged.emit("计划引擎已停止")
        else:
            self.engine.start()
            self.statusChanged.emit("计划引擎已启动")
        self._sync_engine_btn()

    def _sync_engine_btn(self):
        self.btn_engine.setText("停止计划引擎" if self.engine.running else "启动计划引擎")