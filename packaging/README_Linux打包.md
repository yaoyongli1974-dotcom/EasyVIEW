# EasyVIEW · Linux 打包说明

把工程编译为 Linux 可执行程序并产出安装包：
**`.deb`（Debian/Ubuntu）、`.rpm`（Fedora/RHEL/openSUSE）、`AppImage`（跨发行版单文件）**，另有源码包。

> PyInstaller 与 `dpkg-deb`/`rpmbuild`/`appimagetool` 都必须在 Linux 环境运行。
> 推荐直接使用仓库自带的 GitHub Actions 工作流（`.github/workflows/release.yml`），
> 打 tag 后自动产出 Windows 与 Linux 全部安装包并发布 Release。

---

## 一、前置依赖

PyInstaller 会把 Python + PyQt6 打进 onedir 包，**无需系统 Python 运行**；运行期需要系统图形库与 VLC。

Debian / Ubuntu：
```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip \
    libvlc5 libgl1 libxkbcommon0 libdbus-1-3 \
    libxcb-xinerama0 libfontconfig1 libglib2.0-0 \
    dpkg-dev rpm curl patchelf
```

---

## 二、构建方式

### 方式 A：本机一键构建
```bash
bash build/build_linux.sh          # 1) PyInstaller onedir -> dist/EasyVIEW/
bash build/build_deb.sh            # 2) .deb
bash build/build_rpm.sh            # 3) .rpm（需 rpmbuild）
bash build/build_appimage.sh       # 4) AppImage（脚本自动下载 appimagetool）
bash build/build_source.sh         # 5) 源码包
# 或：
bash build/build_linux_all.sh      # deb + rpm + appimage
```

### 方式 B：Docker（不污染本机、可复现）
```bash
bash build/build_linux_docker.sh   # 产物导出到 ./out
```

### 方式 C：GitHub Actions（推荐，含 Windows）
推送 tag 即触发：
```bash
git tag v0.1.1 && git push origin v0.1.1
```
工作流会构建 Windows（portable zip + Setup.exe）与 Linux（deb/rpm/AppImage/source）并创建 Release。

---

## 三、产物位置

| 格式 | 路径 | 说明 |
|---|---|---|
| onedir 包 | `dist/EasyVIEW/` | 主程序 + `_internal/`，可直接运行 |
| `.deb` | `dist/easyview_0.1.1_amd64.deb` | 安装到 `/opt/easyview`，命令 `easyview` |
| `.rpm` | `dist/easyview-0.1.1-1.<dist>.x86_64.rpm` | 同上 |
| AppImage | `dist/easyview-0.1.1-x86_64.AppImage` | `chmod +x` 后直接运行 |
| 源码包 | `dist/EasyVIEW-0.1.1-src.tar.gz` | 当前 HEAD 的 git 归档 |

---

## 四、安装与运行

```bash
sudo apt install ./easyview_0.1.1_amd64.deb      # 或
sudo dnf install ./easyview-0.1.1-1.*.x86_64.rpm
easyview

chmod +x easyview-0.1.1-x86_64.AppImage && ./easyview-0.1.1-x86_64.AppImage
```

**运行要求**：图形会话（X11 或 Wayland+XWayland）、系统已安装 libvlc。
缺 libvlc 时：`sudo apt install libvlc5` / `sudo dnf install vlc`.

---

## 五、离线捆绑 VLC（可选）

把 VLC 运行时的 `libvlc.so` 与 `plugins/` 放到 `dist/EasyVIEW/vlc/`，
`core/config.py` 会在 `import vlc` 前自动注入 `LD_LIBRARY_PATH` 与 `VLC_PLUGIN_PATH`。
`.deb`/`.rpm` 已声明依赖，普通用户走系统 VLC 即可。

---

## 六、FAQ

- **AppImage 报 FUSE 错误**：安装 `fuse` 或用 `--appimage-extract-and-run`。
- **国产发行版（UOS/麒麟）**：均为 Debian 系，`.deb` 通用；依赖差异时优先 AppImage。
- **ARM64**：在 ARM64 机器或 `docker --platform linux/arm64` 重跑脚本，调整 Architecture 字段。
- **签名**：`.deb`/`.rpm` 用 `dpkg-sig`/`rpmsign`，AppImage 用 `gpg --detach-sign`。
