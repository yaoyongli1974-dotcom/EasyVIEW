# EasyVIEW v1.0

PyQt6 + LibVLC 桌面监控客户端（类海康 IVMS-4200），面向 Windows / Linux 跨平台 RTSP 预览。

## 核心功能
- **多画面网格预览**：1 / 4 / 9 画面；网格间隙绘制分隔线，单击选中窗口、点设备即可上墙
- **摄像头管理**：增删改、连接测试、凭据加密存储（keyring，无后端时回退为权限受限密钥文件）
- **ONVIF WS-Discovery** 局域网设备自动发现
- **PTZ 控制**：预置位 / 巡航 / 绝对 / 相对 / 持续
- **本地录像**：分段存储与回放、抓拍、录像计划
- **多厂商 RTSP URL 模板**：Hikvision / Dahua / Uniview
- **VLC 黑屏修复**：`--vout=wingdi` + 去黑样式表；设置对话框可切换解码模式与视频输出

## 界面
v1.0 采用优雅的「石板灰分隔线 + 品牌蓝选中高亮」设计（2px 中性灰分隔、选中窗整圈 3px 蓝框）。
点击捕获层修复了原生视频窗口吞掉鼠标事件导致「点不中窗口」的问题。

## 安装
- **Windows**：下载附件 `EasyVIEW-Setup.exe`（已含 VLC 运行时，开箱即用），默认安装到 `C:\Program Files\EasyVIEW\`
- **从源码构建**：见 `docs/BUILD.md`（PyInstaller onedir + NSIS 安装包；附 Docker / Linux deb/rpm/AppImage 脚本）

## 仓库结构
- `main.py` 入口
- `core/` 业务逻辑（camera / config / database / onvif / ptz / recorder / vault 等）
- `ui/` Qt 界面（main_window / video_grid / preview_widget / camera_list / settings_dialog 等）
- `build/` `packaging/` 打包脚本（已纳入版本控制，构建产物不入库）
- 凭证库 `data/`、打包产物 `dist_*`、VLC 包 `_vlc*`、`_nsis`、`*.venv` 等均通过 `.gitignore` 排除

## 已知限制
- 选中态蓝框在「播放中」由网格间隙的绘制保证可见（不依赖原生视频窗口之上的覆盖层）
- macOS 未做适配测试
