# ==============================================================================
# IVMS4200-Lite Linux 构建镜像（可复现、不污染本机）
# 基于 Ubuntu 22.04，预装 Python/PyQt6 构建依赖、libvlc、dpkg-dev、rpmbuild。
#
# 构建镜像：
#   docker build -t ivms4200-lite-builder .
# 取出安装包（写入当前目录 out/）：
#   docker run --rm -v "$PWD/out:/out" ivms4200-lite-builder
#
# 镜像内已执行：PyInstaller onedir + deb + rpm + AppImage，结果在 /app/dist，
# 容器启动时复制到挂载的 /out 卷。
# ==============================================================================
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl build-essential patch \
        python3 python3-venv python3-pip \
        libvlc5 libvlc-dev \
        libgl1 libxkbcommon0 libdbus-1-3 libxcb-xinerama0 \
        libfontconfig1 libglib2.0-0 \
        dpkg-dev rpm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

# 构建 onedir 包 + 全部安装包（结果位于 /app/dist）
RUN bash build/build_linux.sh && bash build/build_linux_all.sh deb rpm appimage

CMD ["bash", "-c", "cp -r /app/dist/* /out/ 2>/dev/null; echo 'packages ready in /out'"]
