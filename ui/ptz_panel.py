"""PTZ 云台控制面板：预置位 / 巡航 / 绝对·相对·连续转动。"""
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.camera import Camera
from core.onvif_device import OnvifDevice
from core.cruise import (
    CruisePoint,
    CruiseTrack,
    add_cruise_track,
    delete_cruise_track,
    get_cruise_controller,
    list_cruise_tracks,
)
from PyQt6.QtWidgets import QInputDialog, QLineEdit


class PTZPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.camera: Camera | None = None
        self.device: OnvifDevice | None = None
        self.cruise_controller = None
        self._build()
        self._build_native_cruise()

    def _build(self):
        lay = QVBoxLayout(self)

        self.status = QLabel("未选择摄像机")
        lay.addWidget(self.status)

        # 方向键盘
        pad = QGroupBox("方向 / 变倍")
        grid = QVBoxLayout()
        row1 = QHBoxLayout()
        row2 = QHBoxLayout()
        row3 = QHBoxLayout()
        self.b_up = self._dir("↑", 0, 1)
        self.b_down = self._dir("↓", 0, -1)
        self.b_left = self._dir("←", -1, 0)
        self.b_right = self._dir("→", 1, 0)
        self.b_zin = self._dir("变倍+", 0, 0, 1)
        self.b_zout = self._dir("变倍-", 0, 0, -1)
        self.b_stop = QPushButton("停止"); self.b_stop.clicked.connect(lambda: self._stop())
        row1.addWidget(self.b_up); row1.addStretch(1); row1.addWidget(self.b_zin)
        row2.addWidget(self.b_left); row2.addWidget(self.b_stop); row2.addWidget(self.b_right)
        row3.addWidget(self.b_down); row3.addStretch(1); row3.addWidget(self.b_zout)
        grid.addLayout(row1); grid.addLayout(row2); grid.addLayout(row3)
        pad.setLayout(grid)
        lay.addWidget(pad)

        # 模式与步长
        opt = QHBoxLayout()
        self.mode = QComboBox()
        self.mode.addItems(["连续", "相对", "绝对"])
        self.step = QDoubleSpinBox()
        self.step.setRange(0.01, 1.0)
        self.step.setSingleStep(0.05)
        self.step.setValue(0.2)
        opt.addWidget(QLabel("模式")); opt.addWidget(self.mode)
        opt.addWidget(QLabel("步长")); opt.addWidget(self.step)
        opt.addStretch(1)
        lay.addLayout(opt)

        # 预置位
        pre = QGroupBox("预置位")
        pv = QVBoxLayout()
        self.preset_list = QListWidget()
        self.preset_list.itemDoubleClicked.connect(lambda _: self._goto_preset())
        ph = QHBoxLayout()
        self.btn_preset_add = QPushButton("保存到预置位")
        self.btn_preset_add.clicked.connect(self._add_preset)
        self.btn_preset_del = QPushButton("删除")
        self.btn_preset_del.clicked.connect(self._del_preset)
        self.btn_preset_goto = QPushButton("跳转")
        self.btn_preset_goto.clicked.connect(self._goto_preset)
        ph.addWidget(self.btn_preset_add); ph.addWidget(self.btn_preset_goto); ph.addWidget(self.btn_preset_del)
        pv.addWidget(self.preset_list); pv.addLayout(ph)
        pre.setLayout(pv)
        lay.addWidget(pre)

        # 巡航
        cr = QHBoxLayout()
        self.cruise_interval = QSpinBox(); self.cruise_interval.setRange(1, 60); self.cruise_interval.setValue(5)
        self.btn_cruise_start = QPushButton("开始巡航")
        self.btn_cruise_start.clicked.connect(self._start_cruise)
        self.btn_cruise_stop = QPushButton("停止巡航")
        self.btn_cruise_stop.clicked.connect(self._stop_cruise)
        cr.addWidget(QLabel("间隔(s)")); cr.addWidget(self.cruise_interval)
        cr.addWidget(self.btn_cruise_start); cr.addWidget(self.btn_cruise_stop)
        lay.addLayout(cr)

    def _dir(self, label, vx, vy, vz=0):
        btn = QPushButton(label)
        btn.clicked.connect(lambda: self._move(vx, vy, vz))
        return btn

    # ---------------- 设备绑定 ----------------
    def set_camera(self, cam: Camera | None):
        self._stop_cruise()
        self.camera = cam
        self.device = None
        self.preset_list.clear()
        if cam is None:
            self.status.setText("未选择摄像机")
            return
        try:
            self.device = OnvifDevice(cam.ip, cam.port, cam.username, cam.password)
            if self.device.ptz_supported():
                self.status.setText(f"PTZ 就绪：{cam.name}")
                self._refresh_presets()
            else:
                self.status.setText(f"该设备不支持 PTZ：{cam.name}")
        except Exception as e:
            self.status.setText(f"PTZ 连接失败：{e}")
        # 原生巡航（厂商 SDK / ONVIF 兜底）
        self._init_cruise(cam)

    def _ensure(self) -> OnvifDevice | None:
        if self.device is None and self.camera is not None:
            try:
                self.device = OnvifDevice(self.camera.ip, self.camera.port, self.camera.username, self.camera.password)
            except Exception as e:
                self.status.setText(f"PTZ 连接失败：{e}")
                return None
        return self.device

    # ---------------- 转动 ----------------
    def _move(self, vx, vy, vz=0):
        dev = self._ensure()
        if dev is None:
            return
        step = self.step.value()
        mode = self.mode.currentText()
        try:
            if mode == "连续":
                dev.move_continuous(vx * step, vy * step, vz * step, timeout=0.4)
            elif mode == "相对":
                dev.move_relative(vx * step, vy * step, vz * step)
            else:  # 绝对
                st = dev.connect().ptz.GetStatus({"ProfileToken": dev._ensure_profile()})
                cur = st.Position.PanTilt
                cz = st.Position.Zoom.x if hasattr(st.Position, "Zoom") else 0.0
                dev.move_absolute(cur.x + vx * step, cur.y + vy * step, cz + vz * step)
        except Exception as e:
            self.status.setText(f"转动失败：{e}")

    def _stop(self):
        dev = self._ensure()
        if dev:
            dev.stop()

    # ---------------- 预置位 ----------------
    def _refresh_presets(self):
        self.preset_list.clear()
        dev = self._ensure()
        if not dev:
            return
        for p in dev.get_presets():
            self.preset_list.addItem(f"{p['name']}  [{p['token']}]")

    def _selected_preset_token(self):
        item = self.preset_list.currentItem()
        if not item:
            return None
        return item.text().split("[")[-1].rstrip("]")

    def _add_preset(self):
        dev = self._ensure()
        if not dev:
            return
        name = f"P{self.preset_list.count() + 1}"
        dev.set_preset(name)
        self._refresh_presets()

    def _goto_preset(self):
        dev = self._ensure()
        tok = self._selected_preset_token()
        if dev and tok:
            dev.goto_preset(tok)

    def _del_preset(self):
        dev = self._ensure()
        tok = self._selected_preset_token()
        if dev and tok:
            dev.remove_preset(tok)
            self._refresh_presets()

    # ---------------- 巡航 ----------------
    def _start_cruise(self):
        dev = self._ensure()
        if not dev:
            return
        tokens = [self._token_of(i) for i in range(self.preset_list.count())]
        if not tokens:
            self.status.setText("请先添加至少一个预置位再巡航")
            return
        dev.start_cruise(tokens, interval=self.cruise_interval.value())
        self.status.setText("巡航中…")

    def _token_of(self, idx):
        txt = self.preset_list.item(idx).text()
        return txt.split("[")[-1].rstrip("]")

    def _stop_cruise(self):
        if self.device:
            self.device.stop_cruise()

    # ---------------- 设备原生巡航轨迹 ----------------
    def _build_native_cruise(self):
        box = QGroupBox("原生巡航轨迹（设备 SDK）")
        v = QVBoxLayout()

        self.cruise_sdk_status = QLabel("SDK 状态：未初始化")
        v.addWidget(self.cruise_sdk_status)

        hdr = QHBoxLayout()
        self.track_no = QSpinBox(); self.track_no.setRange(1, 16); self.track_no.setValue(1)
        self.track_name = QLineEdit(); self.track_name.setPlaceholderText("轨迹名称")
        hdr.addWidget(QLabel("路线#")); hdr.addWidget(self.track_no)
        hdr.addWidget(QLabel("名称")); hdr.addWidget(self.track_name)
        v.addLayout(hdr)

        self.cruise_points = QListWidget()
        self.cruise_points.itemDoubleClicked.connect(lambda _: self._del_cruise_point())
        v.addWidget(self.cruise_points)

        ph = QHBoxLayout()
        self.btn_cruise_add_pt = QPushButton("加预置点")
        self.btn_cruise_add_pt.clicked.connect(self._add_cruise_point)
        self.btn_cruise_del_pt = QPushButton("删预置点")
        self.btn_cruise_del_pt.clicked.connect(self._del_cruise_point)
        ph.addWidget(self.btn_cruise_add_pt); ph.addWidget(self.btn_cruise_del_pt)
        v.addLayout(ph)

        run = QHBoxLayout()
        self.btn_cruise_upload = QPushButton("上传到设备")
        self.btn_cruise_upload.clicked.connect(self._upload_track)
        self.btn_cruise_run = QPushButton("运行")
        self.btn_cruise_run.clicked.connect(self._run_track)
        self.btn_cruise_stop = QPushButton("停止")
        self.btn_cruise_stop.clicked.connect(self._stop_track)
        self.btn_cruise_clear = QPushButton("清除")
        self.btn_cruise_clear.clicked.connect(self._clear_track)
        run.addWidget(self.btn_cruise_upload); run.addWidget(self.btn_cruise_run)
        run.addWidget(self.btn_cruise_stop); run.addWidget(self.btn_cruise_clear)
        v.addLayout(run)

        cfg = QHBoxLayout()
        self.btn_cruise_save = QPushButton("保存配置")
        self.btn_cruise_save.clicked.connect(self._save_track)
        self.btn_cruise_load = QPushButton("加载配置")
        self.btn_cruise_load.clicked.connect(self._load_track)
        self.btn_cruise_delcfg = QPushButton("删除配置")
        self.btn_cruise_delcfg.clicked.connect(self._del_track_cfg)
        cfg.addWidget(self.btn_cruise_save); cfg.addWidget(self.btn_cruise_load); cfg.addWidget(self.btn_cruise_delcfg)
        v.addLayout(cfg)

        self.track_list = QListWidget()
        self.track_list.itemDoubleClicked.connect(self._apply_track_cfg)
        v.addWidget(self.track_list)

        box.setLayout(v)
        self.layout().addWidget(box)

    def _init_cruise(self, cam: Camera):
        self.cruise_controller = None
        self._pts = []
        self.cruise_points.clear()
        self.track_list.clear()
        if cam is None:
            self.cruise_sdk_status.setText("SDK 状态：未选择设备")
            return
        try:
            self.cruise_controller = get_cruise_controller(cam)
            backend = self.cruise_controller.backend
            avail = self.cruise_controller.available()
            self.cruise_sdk_status.setText(
                f"SDK 状态：{backend} 后端，{'可用' if avail else '不可用（回退 ONVIF 轮巡）'}"
            )
        except Exception as e:
            self.cruise_sdk_status.setText(f"SDK 状态：初始化失败 {e}")
        self._refresh_track_list()

    def _refresh_cruise_points(self):
        self.cruise_points.clear()
        for i, p in enumerate(self._cur_points()):
            self.cruise_points.addItem(f"#{i+1} 预置位{p.preset_no}  停留{p.dwell}s  速度{p.speed}")
            self.cruise_points.item(self.cruise_points.count() - 1).setData(1, i)

    def _cur_points(self) -> list:
        if not hasattr(self, "_pts"):
            self._pts = []
        return self._pts

    def _add_cruise_point(self):
        preset_no, ok1 = QInputDialog.getInt(self, "预置位号", "设备原生预置位编号:", 1, 1, 255)
        if not ok1:
            return
        dwell, ok2 = QInputDialog.getInt(self, "停留时间", "该点停留秒数:", 5, 1, 600)
        if not ok2:
            return
        speed, ok3 = QInputDialog.getInt(self, "速度", "转动速度档(1..8):", 4, 1, 8)
        if not ok3:
            return
        self._cur_points().append(CruisePoint(preset_no=preset_no, dwell=dwell, speed=speed))
        self._refresh_cruise_points()

    def _del_cruise_point(self):
        item = self.cruise_points.currentItem()
        if not item:
            return
        idx = item.data(1)
        pts = self._cur_points()
        if 0 <= idx < len(pts):
            pts.pop(idx)
            self._refresh_cruise_points()

    def _upload_track(self):
        if self.cruise_controller is None:
            self.status.setText("未初始化巡航控制器")
            return
        pts = list(self._cur_points())
        if not pts:
            self.status.setText("请先添加至少一个预置位")
            return
        route = self.track_no.value()
        try:
            self.cruise_controller.login()
            self.cruise_controller.fill_cruise_track(route, pts)
            self.status.setText(f"已上传路线 {route} 到设备（{self.cruise_controller.backend}）")
        except Exception as e:
            self.status.setText(f"上传失败：{e}")

    def _run_track(self):
        if self.cruise_controller is None:
            return
        try:
            self.cruise_controller.run_cruise(self.track_no.value())
            self.status.setText("原生巡航运行中…")
        except Exception as e:
            self.status.setText(f"运行失败：{e}")

    def _stop_track(self):
        if self.cruise_controller is None:
            return
        try:
            self.cruise_controller.stop_cruise(self.track_no.value())
            self.status.setText("已停止原生巡航")
        except Exception as e:
            self.status.setText(f"停止失败：{e}")

    def _clear_track(self):
        if self.cruise_controller is None:
            return
        try:
            self.cruise_controller.clear_cruise(self.track_no.value())
            self.status.setText(f"已清除设备路线 {self.track_no.value()}")
        except Exception as e:
            self.status.setText(f"清除失败：{e}")

    def _save_track(self):
        if self.camera is None:
            return
        track = CruiseTrack(
            camera_id=self.camera.id, track_no=self.track_no.value(),
            name=self.track_name.text().strip(),
            points=list(self._cur_points()),
        )
        add_cruise_track(track)
        self._refresh_track_list()

    def _refresh_track_list(self):
        self.track_list.clear()
        if self.camera is None:
            return
        for t in list_cruise_tracks(self.camera.id):
            self.track_list.addItem(f"路线{t.track_no} {t.name}（{len(t.points)}点）")
            self.track_list.item(self.track_list.count() - 1).setData(1, t.id)

    def _apply_track_cfg(self, item):
        tid = item.data(1)
        if tid is None:
            return
        from core.cruise import get_cruise_track_by_id

        t = get_cruise_track_by_id(tid)
        if not t:
            return
        self.track_no.setValue(t.track_no)
        self.track_name.setText(t.name)
        self._pts = list(t.points)
        self._refresh_cruise_points()

    def _load_track(self):
        if self.track_list.currentItem():
            self._apply_track_cfg(self.track_list.currentItem())

    def _del_track_cfg(self):
        item = self.track_list.currentItem()
        if not item:
            return
        tid = item.data(1)
        if tid is not None:
            delete_cruise_track(tid)
            self._refresh_track_list()
