#!/usr/bin/env python3
"""模拟摄像机：把两路本地测试图案循环转成 HLS 直播流，供 EasyVIEW 预览测试。

两路模拟摄像机（无需真实设备）：
  模拟摄像机-1  http://127.0.0.1:8080/cam1/index.m3u8   testsrc2 彩条 + 实时时钟
  模拟摄像机-2  http://127.0.0.1:8080/cam2/index.m3u8   SMPTE 彩条 + 实时时钟

实现：ffmpeg 生成测试视频 -> ffmpeg 循环转 HLS（分片）-> 内置 http.server 提供访问。
说明：真实摄像机走 RTSP；此处模拟流用 HLS 是因为本机没有支持 RTP-over-TCP 的 RTSP
服务端（VLC 自带 RTSP 服务端只支持 UDP），而 EasyVIEW 为弱网稳定会强制 `rtsp-tcp`。
HLS 走 HTTP，不受该选项影响，且支持 `test_connection` 的 TCP 探测。

用法（在项目根目录执行）::

    python tools/mock_cameras.py start      # 生成素材、启动两路流并注册到 EasyVIEW
    python tools/mock_cameras.py stop       # 停止两路流
    python tools/mock_cameras.py status     # 查看运行状态
    python tools/mock_cameras.py regen      # 重新生成测试素材

启动后运行 `python main.py`，双击左侧「模拟摄像机-1 / 模拟摄像机-2」即可看到画面。
"""
import argparse
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MEDIA = ROOT / "tools" / "mock_media"
HLS_ROOT = MEDIA / "hls"
HTTP_PORT = 8080

CAMERAS = [
    {
        "idx": 1, "name": "模拟摄像机-1", "path": "cam1",
        "label": "CAMERA 1", "src": "testsrc2=size=640x360:rate=12",
        "box": "red@0.65",
    },
    {
        "idx": 2, "name": "模拟摄像机-2", "path": "cam2",
        "label": "CAMERA 2", "src": "smptebars=size=640x360:rate=12",
        "box": "blue@0.65",
    },
]

FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def _font() -> str:
    for f in FONTS:
        if Path(f).exists():
            return f
    return ""


def media_path(cam) -> Path:
    return MEDIA / f"{cam['path']}.mp4"


def hls_dir(cam) -> Path:
    return HLS_ROOT / cam["path"]


def hls_playlist(cam) -> Path:
    return hls_dir(cam) / "index.m3u8"


def pid_path(cam) -> Path:
    return MEDIA / f"{cam['path']}.pid"


def log_path(cam) -> Path:
    return MEDIA / f"{cam['path']}.log"


def server_pid_path() -> Path:
    return MEDIA / "http.pid"


def stream_uri(cam) -> str:
    return f"http://127.0.0.1:{HTTP_PORT}/{cam['path']}/index.m3u8"


def read_pid(path: Path):
    if not path.exists():
        return None
    try:
        return int(path.read_text().strip())
    except ValueError:
        return None


def _alive(pid) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def is_running(cam) -> bool:
    return _alive(read_pid(pid_path(cam)))


def port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def generate(cam):
    MEDIA.mkdir(parents=True, exist_ok=True)
    font = _font()
    label = f"drawtext=text='{cam['label']}':x=20:y=20:fontsize=34:fontcolor=white:box=1:boxcolor={cam['box']}"
    clock = "drawtext=text='%{localtime\\:%X}':x=20:y=h-56:fontsize=30:fontcolor=yellow:box=1:boxcolor=black@0.5"
    if font:
        label += f":fontfile={font}"
        clock += f":fontfile={font}"
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", cam["src"], "-t", "12",
        "-vf", f"{label},{clock}",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-g", "12",
        str(media_path(cam)),
    ]
    print(f"[gen]   {media_path(cam).name} ...")
    subprocess.run(cmd, check=True)


def start_server():
    if port_open(HTTP_PORT):
        print(f"[srv]   HTTP 服务已在 {HTTP_PORT} 运行")
        return
    HLS_ROOT.mkdir(parents=True, exist_ok=True)
    log = open(MEDIA / "http.log", "w")
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(HTTP_PORT), "--directory", str(HLS_ROOT)],
        stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    server_pid_path().write_text(str(proc.pid))
    print(f"[srv]   HTTP 服务 -> http://127.0.0.1:{HTTP_PORT}/ (pid {proc.pid})")


def start_stream(cam):
    if is_running(cam):
        print(f"[skip]  {cam['name']} 已在运行 (pid {read_pid(pid_path(cam))})")
        return
    if not media_path(cam).exists():
        generate(cam)
    hls_dir(cam).mkdir(parents=True, exist_ok=True)
    for old in hls_dir(cam).glob("*"):
        old.unlink()
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "warning",
        "-re", "-stream_loop", "-1", "-i", str(media_path(cam)),
        "-c:v", "libx264", "-preset", "ultrafast", "-g", "24", "-sc_threshold", "0",
        "-f", "hls", "-hls_time", "1", "-hls_list_size", "6",
        "-hls_flags", "delete_segments",
        str(hls_playlist(cam)),
    ]
    log = open(log_path(cam), "w")
    proc = subprocess.Popen(
        cmd, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    pid_path(cam).write_text(str(proc.pid))
    print(f"[start] {cam['name']} -> {stream_uri(cam)} (pid {proc.pid})")


def _kill(pid, label):
    if pid and _alive(pid):
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except OSError:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
        print(f"[stop]  {label} (pid {pid})")


def stop_stream(cam):
    pid = read_pid(pid_path(cam))
    _kill(pid, cam["name"])
    pid_path(cam).unlink(missing_ok=True)


def stop_server():
    pid = read_pid(server_pid_path())
    _kill(pid, "HTTP 服务")
    server_pid_path().unlink(missing_ok=True)


def status():
    print(f"HTTP 服务 {HTTP_PORT}: {'listening' if port_open(HTTP_PORT) else 'DOWN'}")
    for cam in CAMERAS:
        pid = read_pid(pid_path(cam))
        fresh = hls_playlist(cam).exists()
        print(
            f"{cam['name']}: pid={pid} alive={is_running(cam)} "
            f"playlist={'ok' if fresh else 'missing'}  {stream_uri(cam)}"
        )


def register():
    sys.path.insert(0, str(ROOT))
    from core.database import init_db
    from core.camera import Camera, add_camera, update_camera, list_cameras

    init_db()
    existing = {c.name: c for c in list_cameras()}
    for cam in CAMERAS:
        uri = stream_uri(cam)
        cur = existing.get(cam["name"])
        if cur is not None:
            cur.ip, cur.port, cur.vendor = "127.0.0.1", HTTP_PORT, "onvif"
            cur.stream_uri = uri
            cur.protocol = "http"
            update_camera(cur)
            print(f"[reg]   已更新：{cam['name']} (id {cur.id})")
            continue
        cid = add_camera(Camera(
            name=cam["name"], ip="127.0.0.1", port=HTTP_PORT,
            vendor="onvif", stream_uri=uri, enabled=True, protocol="http",
        ))
        print(f"[reg]   已注册：{cam['name']} (id {cid})")


def main():
    ap = argparse.ArgumentParser(description="EasyVIEW 模拟摄像机（HLS）")
    ap.add_argument("action", choices=["start", "stop", "status", "regen"])
    ap.add_argument("--no-register", action="store_true", help="只起流，不写入 EasyVIEW 数据库")
    args = ap.parse_args()

    MEDIA.mkdir(parents=True, exist_ok=True)
    if args.action == "regen":
        for cam in CAMERAS:
            generate(cam)
        return
    if args.action == "start":
        start_server()
        for cam in CAMERAS:
            start_stream(cam)
        time.sleep(2.5)  # 等首片生成，避免 test_connection 过早失败
        if not args.no_register:
            register()
        print("\n完成。运行 `python main.py` 后双击左侧模拟摄像机即可预览。")
        print("停止：python tools/mock_cameras.py stop")
    elif args.action == "stop":
        for cam in CAMERAS:
            stop_stream(cam)
        stop_server()
    elif args.action == "status":
        status()


if __name__ == "__main__":
    main()
