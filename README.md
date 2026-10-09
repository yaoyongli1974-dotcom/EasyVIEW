# EasyVIEW

轻量级视频监控预览客户端（参照海康威视 IVMS-4200 布局风格），聚焦视频实时预览，并具备以下扩展能力：

- 摄像机管理：IP/端口/账号/密码手动添加，**凭据加密持久化（密钥存于 OS 凭据库，不落明文）**
- **独立「设备管理」窗口**：表格化增删改查 + 连接测试；接入协议（RTSP/ONVIF/HTTP-HLS）、用户名/密码、通道数可改；**多通道设备（NVR）一键批量上墙**
- **连接诊断分类**：区分「网络超时 / 连接被拒绝 / 密码错误 / 地址错误 / 无法解析 / 无视频流」
- **ONVIF 自动发现（WS-Discovery）+ 配网**
- **PTZ 云台控制**：预置位、巡航、绝对/相对/连续转动
- **本地录像**：启停、分段存储、回放检索
- **多厂商 RTSP 模板**（海康/大华/宇视等）并自动匹配
- **截图抓拍**：手动（按钮 / 快捷键 `S`）与定时触发，JPG/PNG 落盘并建索引
- **设备原生巡航轨迹**：经厂商 SDK（海康 HCNetSDK / 大华 dhnetsdk）调用设备自带预置巡航路线；无 SDK 时回退 ONVIF 预置位轮巡
- **录像计划**：按定时时间段自动录像；移动侦测（帧差）触发录像，带预录/后录缓冲
- 画面布局：最多 64 路预览；双击单画面全屏；「视窗全屏」整墙全屏；按窗口数量自动分配大小
- **窗口自适应**：首次启动按可用屏幕区域居中自适应；退出记忆窗口大小/位置/最大化状态与窗口数量，下次恢复
- **窗口控制**：菜单栏右上角常驻「最小化 / 最大化(还原) / 关闭」按钮，另有「窗口」菜单与快捷键
- **灵活分屏**：输入窗口数量（1~64）自动排版：完美平方数等分网格，其余优先「1 大(2×2) + N 小」，如 6 路 = 1 大 + 5 小；另提供 1/4/6/9/16/25/36/64 预设
- **独立浮出窗口**：预览右键菜单可把某路画面弹出为可自由移动/缩放的单独窗口；可切换画面比例(自动/16:9/4:3/1:1)
- 跨平台：Windows / Linux（PyQt6 + LibVLC）

## 运行环境

1. 安装 Python 3.10+。
2. 安装 VLC 播放器（提供 libvlc 运行时）：
   - Windows：安装 VLC，并确保 `vlc.exe` 所在目录在 PATH（或设置 `PYTHON_VLC_LIB_PATH`）。
   - Linux：`sudo apt install vlc libvlc-dev`。
3. 安装 Python 依赖：
   ```bash
   pip install -r requirements.txt
   ```
4. 运行：
   ```bash
   python main.py
   ```

> **Linux 桌面环境（重要）**：本程序用 LibVLC 的 `set_xwindow` 把视频嵌入自制窗口，需要
> **X11(xcb) 平台**。`main.py` 在检测到 `DISPLAY`（含 Wayland 下的 XWayland）时会自动把
> `QT_QPA_PLATFORM` 设为 `xcb`，避免出现「视频窗口与界面错位/重叠」。若需强制其它平台，
> 设置环境变量 `EASYVIEW_QT_PLATFORM`（如 `EASYVIEW_QT_PLATFORM=wayland`）。若在无 XWayland
> 的纯 Wayland 会话下，请先启用 XWayland。
> Linux 若 `libvlc` 不在标准路径，设置环境变量 `PYTHON_VLC_LIB_PATH=/usr/lib/.../libvlc.so`。
> 加密凭据依赖 `keyring` 后端：Windows=Credential Manager，Linux=Secret Service（GNOME/KDE 钥匙环）。无后端时回退为权限受限的密钥文件（`~/.easyview/vault.key`，chmod 600）。

## 打包

```bash
# Windows
pyinstaller -F -w main.py
# Linux
pyinstaller -F main.py
```

分发时建议把目标机的 VLC 目录随包附带，并在代码中指定 `VLC_PLUGIN_PATH`。

## 测试

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
# GUI 测试需无显示环境，采用 Qt offscreen 后端
QT_QPA_PLATFORM=offscreen pytest tests -v
```

覆盖 RTSP 模板/凭据加解密/录像计划时间窗/ONVIF scope 解析，以及 offscreen 下的
主窗口与各对话框构造冒烟测试（含历史崩溃点回归）。

## 模拟摄像机（无设备测试图像）

没有真实摄像机时，可用内置脚本起两路模拟流（VLC/ffmpeg 生成的彩条 + 实时时钟），
并自动注册到 EasyVIEW：

```bash
python tools/mock_cameras.py start   # 生成素材、启动两路 HLS 流并注册
python main.py                        # 双击左侧「模拟摄像机-1/2」预览
python tools/mock_cameras.py stop    # 停止
```

模拟地址：`http://127.0.0.1:8080/cam1/index.m3u8`、`.../cam2/index.m3u8`。
依赖系统已安装 `ffmpeg`（HLS 转码）；HTTP 服务用 Python 标准库 `http.server`。

## 目录结构

```
core/   config / database / camera / crypto / rtsp_templates / onvif_discovery / onvif_device / recorder / playback
ui/     main_window / camera_list / camera_dialog / discovery_dialog / ptz_panel / recording_panel / preview_widget / video_grid / floating_preview
tests/  pytest 用例（RTSP/加密/计划窗口/网格/ONVIF 解析/GUI 冒烟）
docs/   技术方案.md（基础） + 技术方案_扩展.md（本扩展）
```

## 使用要点

- 添加摄像机：工具栏「添加摄像机」手动填写；或「发现设备」经 WS-Discovery 自动搜出局域网 ONVIF 设备，填入账号密码后「获取流地址」自动拉取 RTSP。
- 预览：左侧列表双击播放；顶部输入窗口数量（1~64）或点预设按钮自动排版；双击窗格进入单路全屏；「视窗全屏」按钮 / `F11` 整墙全屏；`Esc` 退出。
- 窗口/分屏：菜单栏右上角「最小化/最大化/关闭」；「添加窗口/删除窗口」增减分屏路数；预览窗口右键菜单可清空、浮出为独立窗口、切换画面比例。功能入口集中在顶部菜单（文件/视图/工具/窗口）。
- PTZ：选中某路预览后点「云台」，方向键/变倍、预置位增删与跳转、巡航启停。
- 录像：选中摄像机后点「录像」，设分段时长（0=不分段），启停；回放列表双击某段即在该窗格播放文件。
- 抓拍：选中摄像机后点「抓拍」或按 `S` 抓取当前画面；「截图抓拍」停靠窗可设格式/质量与定时抓拍间隔，历史快照双击用系统查看器打开。
- 原生巡航：选中支持厂商 SDK 的设备，在「云台」面板的「原生巡航轨迹」组配置路线号、预置位点（停留/速度），「上传到设备」下发，「运行/停止/清除」控制设备端轨迹；轨迹配置可存本地库供复用。
- 录像计划：选中摄像机后点「计划」，新建「定时」或「移动侦测」计划并配置参数；点「启动计划引擎」后后台按配置自动录像（离开窗口/静止后自动停止）。`recordings` 表以 `trigger`(schedule/motion/manual) 与 `plan_id` 溯源。

> 设备原生巡航依赖海康/大华 SDK 动态库（非 pip 包），需自行部署到运行环境；未部署时自动回退 ONVIF 轮巡。
> 移动侦测默认采用快照帧差启发式（`core/recording_plan.py`），生产环境建议替换为 OpenCV 帧差或设备原生移动告警（ONVIF 事件 / 厂商 SDK 告警回调）。
