# IVMS4200-Lite · Linux 打包说明

把现有 Windows 工程编译为 Linux 可用的可执行程序，并产出常见安装包格式：
**`.deb`（Debian/Ubuntu）、`.rpm`（Fedora/RHEL/openSUSE）、`AppImage`（跨发行版单文件）**。

> 说明：PyInstaller 与 `dpkg-deb`/`rpmbuild`/`appimagetool` 都**必须在本机/容器内的
> Linux 环境运行**。本目录提供的是在 Linux 上一条命令完成构建的完整套件；Windows 沙箱
> 无法产出 Linux 二进制。下面三种方式任选其一。

---

## 一、前置依赖

PyInstaller 会把 Python + PyQt6 打包进 onedir 包，因此**无需系统 Python**；但运行期需要
系统图形库与 VLC 运行时。

### Debian / Ubuntu
```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip \
    libvlc5 libgl1 libxkbcommon0 libdbus-1-3 \
    libxcb-xinerama0 libfontconfig1 libglib2.0-0 \
    dpkg-dev rpm curl patch
# 仅构建 .rpm 需要 rpmbuild（Ubuntu 也提供）
```

### Fedora / RHEL
```bash
sudo dnf install -y python3 python3-pip \
    vlc-core mesa-libGL libxkbcommon dbus-libs \
    libxcb xcb-util-image fontconfig glib2 \
    rpm-build dpkg-dev curl patch
```

### openSUSE
```bash
sudo zypper install -y python3 python3-pip python3-virtualenv \
    libvlc5 libGL1 libxkbcommon0 libdbus-1-3 libxcb-xinerama0 \
    libfontconfig1 libglib-2_0-0 rpm dpkg curl
```

---

## 二、构建方式

### 方式 A：本机一键构建（推荐有 Linux 桌面/服务器）

```bash
# 1) 生成 PyInstaller onedir 包
bash build/build_linux.sh

# 2) 生成全部安装包（deb + rpm + AppImage）
bash build/build_linux_all.sh

# 仅生成某一种：
bash build/build_linux_all.sh deb
bash build/build_linux_all.sh rpm
bash build/build_linux_all.sh appimage
```

### 方式 B：Docker 容器构建（不污染本机、可复现）

需本机装好 Docker。镜像内已预装全部依赖并完成 `PyInstaller + deb + rpm + AppImage`，
产物直接导出到 `./out`：

```bash
bash build/build_linux_docker.sh
ls -lh out/
```

### 方式 C：仅本地运行（不要安装包）

只要 onedir 包即可直接跑（需系统已装 libvlc 等运行时）：

```bash
bash build/build_linux.sh
dist/IVMS4200-Lite/IVMS4200-Lite
```

---

## 三、产物位置

| 格式 | 默认路径 | 说明 |
|---|---|---|
| onedir 包 | `dist/IVMS4200-Lite/` | 含主程序与 `_internal/`，可直接运行 |
| `.deb` | `dist/ivms4200-lite_1.0.0_amd64.deb` | 安装到 `/opt/ivms4200-lite`，命令 `ivms4200-lite` |
| `.rpm` | `~/rpmbuild/RPMS/x86_64/ivms4200-lite-1.0.0-1.*.x86_64.rpm` | 同上 |
| AppImage | `dist/IVMS4200-Lite-1.0.0-x86_64.AppImage` | `chmod +x` 后直接运行，跨发行版 |

> Docker 方式下产物在 `out/` 目录。

---

## 四、安装与运行

```bash
# deb
sudo apt install ./ivms4200-lite_1.0.0_amd64.deb
ivms4200-lite

# rpm
sudo dnf install ./ivms4200-lite-1.0.0-1.fc*.x86_64.rpm
ivms4200-lite

# AppImage
chmod +x IVMS4200-Lite-1.0.0-x86_64.AppImage
./IVMS4200-Lite-1.0.0-x86_64.AppImage
```

**运行要求**：图形会话（X11 或 Wayland）、系统已安装 libvlc（视频解码内核）。
若提示找不到 libvlc，先 `sudo apt install libvlc5` / `sudo dnf install vlc-core`。

---

## 五、离线捆绑 VLC（可选，完全自包含）

若不依赖系统 VLC，可把 VLC 运行时放进 onedir 包的同目录 `vlc/` 子目录：

- 把 `libvlc.so` 与 `plugins/` 放到 `dist/IVMS4200-Lite/vlc/`
- `core/config.py` 会在启动 import vlc 前自动注入 `LD_LIBRARY_PATH` 与 `VLC_PLUGIN_PATH`

> 注意：`.deb`/`.rpm` 的 `Depends/Requires` 已声明 libvlc，普通用户走系统 VLC 即可，
> 无需手动捆绑；仅「纯离线 / AppImage 内嵌」场景才需要。

---

## 六、跨平台关键点（已写入 `core/config.py`）

- 数据目录：Linux 落到 `$XDG_DATA_HOME` 或 `~/.local/share/IVMS4200-Lite`
  （Windows 为 `%LOCALAPPDATA%`，macOS 为 `~/Library/Application Support`）。
- VLC 定位：优先 exe 同目录 `vlc/`，回退系统已装 VLC（Linux 走动态链接器，Windows 走注册表）。
- 凭据保险库：优先 OS 凭据库（Linux=SecretService/DBus），不可用时回退 `~/.ivms4200-lite/vault.key`。

---

## 七、FAQ

**Q：Docker 方式里 `docker build` 很慢？**
A：首次会下载 Ubuntu 基镜像与 pip 依赖，属正常；可加 `--no-cache` 之外无需特殊处理。

**Q：AppImage 运行时报 FUSE 相关错误？**
A：安装 `fuse` 后重试；或用 `./xxx.AppImage --appimage-extract` 解包运行。

**Q：国产发行版（统信 UOS / 麒麟）能装吗？**
A：均为 Debian 系，`.deb` 通用；若依赖版本略差异，优先用 AppImage（自带 Qt/Python）。

**Q：能打 ARM64（aarch64）包吗？**
A：可以。在 ARM64 机器（或 Docker `--platform linux/arm64`）上重跑同一套脚本即可，
   `.deb`/`.rpm` 的 Architecture 字段需相应改为 `arm64`/`aarch64`。

**Q：代码签名？**
A：`.deb`/`.rpm` 可用 GPG 签名（`dpkg-sig` / `rpmsign`）；AppImage 可用 `gpg --detach-sign`。
   企业内部分发建议加签名以消除校验告警。
