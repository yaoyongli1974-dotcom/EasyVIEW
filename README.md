# EasyVIEW

极简视频监控预览客户端（PyQt6 + LibVLC）。聚焦一件事：**把 RTSP / HTTP-HLS 摄像头上墙预览**。

## 功能

- **摄像机管理**：手动添加/编辑/删除，密码加密持久化（密钥存于 OS 凭据库，不落明文）
- **实时预览**：1~64 路；双击窗格单路全屏，`F11` / 「视窗全屏」整墙全屏，`Esc` 退出
- **自动分屏**：按窗口数量排版——完美平方等分，其余优先「1 大(2×2) + N 小」（如 6 = 1 大 + 5 小）
- **多厂商 RTSP 模板**：海康 / 大华 / 宇视 / 乐橙，也可直接填完整 `stream_uri`
- **HTTP / HLS / MJPEG**：协议选 HTTP 并填完整地址即可
- **连接诊断分类**：区分「网络超时 / 连接被拒绝 / 密码错误 / 地址错误 / 无法解析 / 无视频流」
- **窗口记忆**：退出保存窗口大小/位置/最大化状态与窗口数量，下次恢复

## 运行环境

1. 安装 Python 3.10+。
2. 安装 VLC 播放器（提供 libvlc 运行时）：
   - Windows：安装 VLC，确保 `vlc.exe` 所在目录在 PATH（或设 `PYTHON_VLC_LIB_PATH`）。
   - Linux：`sudo apt install vlc`。
3. 安装依赖并运行：
   ```bash
   pip install -r requirements.txt
   python main.py
   ```

> **Linux 桌面（重要）**：程序用 LibVLC 的 `set_xwindow` 把视频嵌入自制窗口，需要
> **X11(xcb) 平台**。`main.py` 在检测到 `DISPLAY`（含 Wayland 下的 XWayland）时会自动把
> `QT_QPA_PLATFORM` 设为 `xcb`，避免「视频窗口与界面错位/重叠」。若需强制其它平台，设置
> `EASYVIEW_QT_PLATFORM`。纯 Wayland 会话请先启用 XWayland。
>
> 加密凭据依赖 `keyring` 后端（Windows=凭据管理器，Linux=Secret Service）。无后端时回退为
> 权限受限的密钥文件（`~/.easyview/vault.key`，chmod 600）。

## 使用要点

- 添加摄像机：菜单「文件 → 添加摄像机…」，填 IP/端口/用户名/密码；协议 RTSP 时按厂商模板生成地址，
  或填完整「流地址」。
- 预览：左侧列表双击上墙到当前选中窗格。
- 分屏：顶部输入窗口数量（1~64）或点预设按钮；「添加/删除窗口」动态增减。
- 全屏：双击窗格单路全屏；「视窗全屏」/ `F11` 整墙全屏；`Esc` 退出。
- 右键预览窗格：清空、切换画面比例（自动/16:9/4:3/1:1）。
- 连接测试：左侧列表右键「连接测试」。

## 模拟摄像机（无设备测试图像）

没有真实摄像机时，可用内置脚本起两路模拟流并自动注册（需系统安装 `ffmpeg`）：

```bash
python tools/mock_cameras.py start   # 生成素材、启动两路 HLS 流并注册
python main.py                        # 双击左侧「模拟摄像机-1/2」预览
python tools/mock_cameras.py stop     # 停止
```

模拟地址：`http://127.0.0.1:8080/cam1/index.m3u8`、`.../cam2/index.m3u8`。

## 测试

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
QT_QPA_PLATFORM=offscreen pytest tests -v   # GUI 测试用 Qt offscreen 后端
```

## 目录结构

```
main.py   入口（Linux 自动切 xcb）
core/     config / crypto / database / camera / rtsp_templates / net_probe
ui/       main_window / camera_list / camera_dialog / video_grid / preview_widget / layouts
tests/    pytest 用例（RTSP 模板 / 加密 / 连接诊断 / 布局 / GUI 冒烟）
tools/    mock_cameras.py（模拟 HLS 摄像机）
docs/     技术方案.md
```

## 打包

```bash
pyinstaller -F -w main.py   # Windows
pyinstaller -F main.py      # Linux
```

分发时建议把目标机的 VLC 目录随包附带，并设置 `VLC_PLUGIN_PATH`。
