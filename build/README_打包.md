# EasyVIEW 打包与部署指南（Windows）

本文档说明如何将本工程编译为 Windows 可执行程序（`EasyVIEW.exe`），
并进一步制作为安装包（`EasyVIEW-Setup.exe`）。

---

## 1. 前置条件

| 项目 | 说明 |
|---|---|
| Python | 3.11+（建议 3.13）。用于构建，最终产物不依赖 Python 解释器 |
| VLC 播放器 | **运行时必需**。提供 `libvlc.dll` 解码内核。构建机若装了 VLC，脚本会自动把运行时打进 `vlc/` 目录，实现开箱即用 |
| NSIS | 仅制作安装包时需要（https://nsis.sourceforge.io）。生成 exe 不需要 |

> 本工程的视频解码依赖 LibVLC（python-vlc 只是绑定）。**没有 libvlc.dll，exe 无法播放任何视频。**

---

## 2. 一键生成 exe（PyInstaller，单文件夹）

直接双击或命令行运行：

```bat
build\build_exe.bat
```

脚本会：
1. 在当前目录创建 `.venv` 虚拟环境并激活；
2. 安装 `requirements.txt` 与 `pyinstaller`；
3. 用 `build/build.spec` 打包（隐藏控制台、`onedir` 单文件夹模式）；
4. 若本机已装 VLC，自动将其运行时复制到 `dist\EasyVIEW\vlc\`。

产物：`dist\EasyVIEW\EasyVIEW.exe`（连同一堆依赖 dll/pyd）。

**手工打包（等价命令）：**

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt pyinstaller
python -m PyInstaller build\build.spec --noconfirm --clean
```

---

## 3. 让 exe 找到 VLC 运行时（关键）

`core/config.py` 在导入 `vlc` 之前会自动定位 `libvlc.dll`，搜索顺序：

1. exe 同目录的 `vlc\` 子目录（**便携捆绑方案，推荐**）；
2. 系统已安装 VLC（注册表 / `C:\Program Files\VideoLAN\VLC`）。

因此有两种分发方式：

- **方式 A（开箱即用，推荐）**：把 VLC 安装目录整体复制到 `dist\EasyVIEW\vlc\`。
  即保证 `dist\EasyVIEW\vlc\libvlc.dll` 与 `...\vlc\plugins\` 存在。
  构建脚本 `build_exe.bat` 在检测到本机 VLC 时会自动完成这一步。
- **方式 B（体积小，依赖用户）**：不打包 VLC，要求最终用户自行安装 VLC。
  此时 exe 会走搜索顺序第 2 项从系统 VLC 加载。

> 也可改用安装包自动下载 VLC 便携版，但会增加安装包体积与复杂度；
> 对内部/项目分发，方式 A 最省心。

---

## 4. 生成安装包（NSIS）

安装 NSIS 后，在项目根目录执行：

```bat
makensis build\installer.nsi
```

产物：`dist\EasyVIEW-Setup.exe`。

安装包行为：
- 默认安装到 `C:\Program Files\EasyVIEW\`；
- 写入开始菜单与桌面快捷方式；
- 写入标准卸载注册表项，并提供 `Uninstall.exe`；
- 整体打包 `dist\EasyVIEW\*`（含 `vlc\` 运行时，若已存在）。

---

## 5. 数据存放位置

打包后（frozen）数据目录改为用户本地应用数据，避免随 exe 卸载丢失：

```
%LOCALAPPDATA%\EasyVIEW\
├── cameras.db          # 摄像机配置（密码以密文存储）
├── recordings\         # 本地录像分段文件
└── snapshots\          # 截图抓拍
```

开发态（`python main.py`）数据仍在项目内 `data/`，二者互不干扰。

---

## 6. 可选：厂商原生巡航 / SDK 能力

海康 `HCNetSDK.dll`、大华 `dhnetsdk.dll` 是 C 动态库，**不属于 pip 依赖**，
需用户自行部署到运行环境 PATH 或 exe 同目录。未部署时，云台巡航自动回退
ONVIF 预置位轮巡，功能仍可用。`core\vendor_sdk.py` 已做优雅降级。

---

## 7. 常见问题

| 现象 | 原因 / 解决 |
|---|---|
| 启动黑屏或报错 `Cannot find libvlc` | 缺少 VLC 运行时。按第 3 节放置 `vlc\` 目录或安装 VLC |
| 预览无画面但列表正常 | 摄像机 RTSP 地址/账号错误；先用「连接测试」验证 |
| ONVIF 设备发现不到 | 设备与 PC 需同网段；部分设备默认关闭 ONVIF，需在摄像机 Web 管理开启 |
| 杀毒软件误报 | PyInstaller 产物的常见误报，可加白名单或代码签名（见下） |

---

## 8. 代码签名（可选，提升信任）

发布给外部用户建议对 `EasyVIEW.exe` 与 `Setup.exe` 做 Authenticode 签名：

```bat
signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /f cert.pfx /p <密码> dist\EasyVIEW\EasyVIEW.exe
```

未签名时 Windows SmartScreen 可能拦截，用户需点击「仍要运行」。
