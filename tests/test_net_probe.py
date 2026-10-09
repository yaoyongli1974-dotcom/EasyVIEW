"""连接诊断分类测试：用本地假 RTSP 服务端覆盖状态码分支。"""
import socket
import threading

import pytest


def _serve(responses):
    """起一个本地 TCP 服务端，按顺序对每次请求返回一个响应；返回端口。"""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]

    def run():
        conn, _ = srv.accept()
        try:
            for resp in responses:
                conn.recv(4096)
                conn.sendall(resp)
        except OSError:
            pass
        finally:
            conn.close()
            srv.close()

    threading.Thread(target=run, daemon=True).start()
    return port


def test_probe_rtsp_ok():
    from core.net_probe import probe_rtsp

    port = _serve([b"RTSP/1.0 200 OK\r\nCSeq: 1\r\n\r\n"])
    code, msg = probe_rtsp(f"rtsp://127.0.0.1:{port}/s", timeout=3)
    assert code == "ok"


def test_probe_rtsp_basic_auth_ok():
    from core.net_probe import probe_rtsp

    challenge = (b"RTSP/1.0 401 Unauthorized\r\nCSeq: 1\r\n"
                 b'WWW-Authenticate: Basic realm="cam"\r\n\r\n')
    port = _serve([challenge, b"RTSP/1.0 200 OK\r\nCSeq: 2\r\n\r\n"])
    code, msg = probe_rtsp(f"rtsp://admin:pw@127.0.0.1:{port}/s", timeout=3)
    assert code == "ok"


def test_probe_rtsp_auth_failed():
    from core.net_probe import probe_rtsp

    challenge = (b"RTSP/1.0 401 Unauthorized\r\nCSeq: 1\r\n"
                 b'WWW-Authenticate: Basic realm="cam"\r\n\r\n')
    port = _serve([challenge, challenge])
    code, msg = probe_rtsp(f"rtsp://admin:bad@127.0.0.1:{port}/s", timeout=3)
    assert code == "auth"


def test_probe_rtsp_not_found():
    from core.net_probe import probe_rtsp

    port = _serve([b"RTSP/1.0 404 Not Found\r\nCSeq: 1\r\n\r\n"])
    code, msg = probe_rtsp(f"rtsp://127.0.0.1:{port}/s", timeout=3)
    assert code == "bad_url"


def test_probe_refused():
    from core.net_probe import probe_rtsp

    # 绑定后立即关闭，得到一个几乎必然被拒绝的端口
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    code, msg = probe_rtsp(f"rtsp://127.0.0.1:{port}/s", timeout=2)
    assert code in ("refused", "timeout")


def test_diagnose_bad_config():
    from core.camera import Camera
    from core.net_probe import diagnose_connection

    code, msg = diagnose_connection(Camera(name="x", ip=""))
    assert code == "bad_config"
