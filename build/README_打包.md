# EasyVIEW 打包与部署指南（Windows）

把工程编译为 Windows 可执行程序（`EasyVIEW.exe`），并制作安装包（`EasyVIEW-Setup.exe`）。
推荐直接用 GitHub Actions（`.github/workflows/release.yml`）在 `windows-latest` 上自动完成。

---

## 1. 前置条件

| 项目 | 说明 |
|---|---|
| Python | 3.11+（建议 3.12/3.13）。仅构建需要，产物不依赖 Python |
| VLC | **运行时必需**，提供 `libvlc.dll`。构建机若装了 VLC，脚本会把运行时打进 `vlc/` 实现开箱即用 |
| NSIS | 仅制作安装包需要（https://nsis.sourceforge.io） |

> 视频解码依赖 LibVLC（python-vlc 只是绑定）。**没有 libvlc.dll，exe 无法播放任何视频。**

---

## 2. 本地构建

```bat
build\build_exe.bat
```

脚本会：创建 `.venv`、安装依赖与 pyinstaller、用 `build\build.spec` 打 onedir 包，
并在检测到本机 VLC 时复制运行时到 `dist\EasyVIEW\vlc\`。

产物：`dist\EasyVIEW\EasyVIEW.exe`。

**等价手工命令：**
```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt pyinstaller
python -m PyInstaller build\build.spec --noconfirm --clean
```

---

## 3. VLC 运行时

`core/config.py` 在 `import vlc` 前自动定位 `libvlc.dll`，顺序：
1. exe 同目录 `vlc\` 子目录（**便携捆绑，推荐**）；
2. 系统已安装的 VLC（注册表 / `C:\Program Files\VideoLAN\VLC`）。

分发方式：
- **A（开箱即用）**：把 VLC 安装目录整体复制到 `dist\EasyVIEW\vlc\`（`build_exe.bat` 自动完成）。
- **B（体积小）**：不捆绑，要求用户自行安装 VLC。

---

## 4. 安装包（NSIS）

```bat
makensis build\installer.nsi
```

产物：`dist\EasyVIEW-Setup.exe`。行为：默认装到 `C:\Program Files\EasyVIEW\`、
创建开始菜单/桌面快捷方式、写入卸载项并提供 `Uninstall.exe`、整体打包 `dist\EasyVIEW\*`。

---

## 5. GitHub Actions（推荐）

推送 tag 即触发 `.github/workflows/release.yml`：
在 `windows-latest` 上打 onedir 包 → 下载 VLC 3.0.21 便携版并捆绑 →
生成 `EasyVIEW-<ver>-win64-portable.zip`（绿色版）与 `EasyVIEW-<ver>-Setup.exe`（安装包），
`ubuntu-22.04` 上生成 deb/rpm/AppImage/源码包，最后创建 GitHub Release 并上传全部产物。

```bash
git tag v0.1.1 && git push origin v0.1.1
```

---

## 6. 数据存放

打包（frozen）后数据落在用户本地：

```
%LOCALAPPDATA%\EasyVIEW\
├── cameras.db      # 摄像机配置（密码密文）
└── easyview_debug.log
```

开发态（`python main.py`）数据在项目内 `data/`，互不干扰。

---

## 7. FAQ

| 现象 | 解决 |
|---|---|
| 启动黑屏 / `Cannot find libvlc` | 放置 `vlc\` 目录或安装 VLC |
| 预览无画面但列表正常 | 用「连接测试」核对地址/账号 |
| 杀毒误报 | PyInstaller 常见误报；建议代码签名 |
| SmartScreen 拦截 | 未签名时点「仍要运行」，正式发布建议 Authenticode 签名 |
