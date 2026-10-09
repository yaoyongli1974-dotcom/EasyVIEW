"""连接诊断：区分「网络超时 / 连接被拒绝 / 密码错误 / 地址错误 / 无视频流」等。

RTSP 用 DESCRIBE 探测（支持 Basic / Digest 鉴权），HTTP/HLS 用 HTTP GET 探测。
返回 ``(code, message)``，code 取值：
  ok / dns / refused / timeout / unreachable / auth / bad_url / error / bad_config
"""
import base64
import hashlib
import os
import socket
import time
from urllib.parse import urlsplit, unquote


def _recv_headers(sock: socket.socket, timeout: float) -> bytes:
    sock.settimeout(timeout)
    data = b""
    deadline = time.time() + timeout
    while b"\r\n\r\n" not in data and b"\n\n" not in data:
        if time.time() > deadline:
            break
        try:
            chunk = sock.recv(4096)
        except socket.timeout:
            break
        except OSError:
            break
        if not chunk:
            break
        data += chunk
        if len(data) > 131072:
            break
    return data


def _parse_status(data: bytes):
    """从响应头块解析 (status_code, headers)。"""
    if not data:
        return None, {}
    head = data.split(b"\r\n\r\n", 1)[0].split(b"\n\n", 1)[0]
    lines = head.decode("latin-1", "replace").splitlines()
    code = None
    if lines:
        parts = lines[0].split()
        if len(parts) >= 2 and parts[1].isdigit():
            code = int(parts[1])
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    return code, headers


def _parse_digest(challenge: str) -> dict:
    """解析 WWW-Authenticate 的 Digest 参数（支持引号内逗号）。"""
    out = {}
    i = 0
    n = len(challenge)
    while i < n:
        while i < n and challenge[i] in ", ":
            i += 1
        j = challenge.find("=", i)
        if j < 0:
            break
        key = challenge[i:j].strip().lower()
        i = j + 1
        if i < n and challenge[i] == '"':
            i += 1
            val = ""
            while i < n and challenge[i] != '"':
                if challenge[i] == "\\" and i + 1 < n:
                    i += 1
                val += challenge[i]
                i += 1
            i += 1
        else:
            k = i
            while i < n and challenge[i] not in ",":
                i += 1
            val = challenge[k:i].strip()
        out[key] = val
    return out


def _build_auth(method: str, uri: str, user: str, pwd: str, challenge: str) -> str:
    if not challenge:
        return ""
    scheme, _, rest = challenge.partition(" ")
    scheme = scheme.strip().lower()
    if scheme == "basic":
        token = base64.b64encode(f"{user}:{pwd}".encode()).decode()
        return f"Authorization: Basic {token}"
    if scheme != "digest":
        return ""
    p = _parse_digest(rest)
    realm = p.get("realm", "")
    nonce = p.get("nonce", "")
    qop = p.get("qop", "")
    opaque = p.get("opaque", "")
    algorithm = (p.get("algorithm", "MD5") or "MD5").upper()

    def md5(s: str) -> str:
        return hashlib.md5(s.encode()).hexdigest()

    ha1 = md5(f"{user}:{realm}:{pwd}")
    ha2 = md5(f"{method}:{uri}")
    if qop:
        qop_val = "auth"
        nc = "00000001"
        cnonce = hashlib.md5(os.urandom(8)).hexdigest()[:16]
        response = md5(f"{ha1}:{nonce}:{nc}:{cnonce}:{qop_val}:{ha2}")
    else:
        response = md5(f"{ha1}:{nonce}:{ha2}")
        nc = cnonce = ""
    parts = [
        f'username="{user}"', f'realm="{realm}"', f'nonce="{nonce}"',
        f'uri="{uri}"', f'response="{response}"',
    ]
    if algorithm:
        parts.append(f"algorithm={algorithm}")
    if opaque:
        parts.append(f'opaque="{opaque}"')
    if qop:
        parts += [f"qop={qop_val}", f"nc={nc}", f'cnonce="{cnonce}"']
    return "Authorization: Digest " + ", ".join(parts)


def _tcp(host: str, port: int, timeout: float):
    try:
        socket.gethostbyname(host)
    except OSError:
        return None, ("dns", "无法解析主机名/IP")
    try:
        return socket.create_connection((host, port), timeout), None
    except ConnectionRefusedError:
        return None, ("refused", "连接被拒绝（端口未开放）")
    except socket.timeout:
        return None, ("timeout", "网络超时（无法建立连接）")
    except OSError as e:
        return None, ("unreachable", f"网络不可达：{e}")


def _rtsp_request(sock: socket.socket, method: str, url: str, cseq: int, extra=None):
    lines = [f"{method} {url} RTSP/1.0", f"CSeq: {cseq}", "User-Agent: EasyVIEW"]
    for h in (extra or []):
        lines.append(h)
    sock.sendall(("\r\n".join(lines) + "\r\n\r\n").encode())


def probe_rtsp(url: str, timeout: float = 5.0):
    u = urlsplit(url)
    user = unquote(u.username or "")
    pwd = unquote(u.password or "")
    host = u.hostname or ""
    port = u.port or 554
    sock, err = _tcp(host, port, timeout)
    if err:
        return err
    with sock:
        _rtsp_request(sock, "DESCRIBE", url, 1, ["Accept: application/sdp"])
        code, headers = _parse_status(_recv_headers(sock, timeout))
        if code is None:
            return ("timeout", "无响应/网络超时")
        if code == 200:
            return ("ok", "连接成功，视频流可播放")
        if code == 401:
            challenge = headers.get("www-authenticate", "")
            auth = _build_auth("DESCRIBE", url, user, pwd, challenge)
            if not auth:
                return ("auth", "需要认证，但未提供用户名/密码")
            _rtsp_request(sock, "DESCRIBE", url, 2,
                          ["Accept: application/sdp", auth])
            code2, _ = _parse_status(_recv_headers(sock, timeout))
            if code2 == 200:
                return ("ok", "连接成功，视频流可播放")
            return ("auth", "用户名或密码错误")
        if code == 403:
            return ("auth", "无权访问（403）")
        if code == 404:
            return ("bad_url", "地址/通道错误（404 Not Found）")
        if code in (400, 405, 415, 451, 461):
            return ("bad_url", f"请求被拒绝（{code}，可能地址/传输方式不对）")
        return ("error", f"服务器返回 {code}")


def probe_http(url: str, timeout: float = 5.0):
    u = urlsplit(url)
    host = u.hostname or ""
    port = u.port or (443 if u.scheme == "https" else 80)
    sock, err = _tcp(host, port, timeout)
    if err:
        return err
    path = u.path or "/"
    if u.query:
        path += "?" + u.query
    with sock:
        req = (f"GET {path} HTTP/1.0\r\nHost: {host}\r\n"
               f"User-Agent: EasyVIEW\r\n\r\n")
        try:
            sock.sendall(req.encode())
        except OSError as e:
            return ("error", f"发送请求失败：{e}")
        code, _ = _parse_status(_recv_headers(sock, timeout))
        if code is None:
            return ("timeout", "无响应/网络超时")
        if code == 200:
            return ("ok", "连接成功，视频流可播放")
        if code in (401, 403):
            return ("auth", f"需要认证或无权访问（{code}）")
        if code == 404:
            return ("bad_url", "地址错误（404 Not Found）")
        return ("error", f"服务器返回 {code}")


def diagnose_connection(cam, timeout: float = 5.0):
    """诊断连接，返回 (code, message)。cam 为 Camera（鸭子类型）。"""
    if not cam.ip:
        return ("bad_config", "未填写 IP 地址")
    protocol = (getattr(cam, "protocol", "rtsp") or "rtsp").lower()
    url = cam.rtsp_url()
    if protocol == "http" and not getattr(cam, "stream_uri", ""):
        return ("bad_config", "HTTP/HLS 协议需填写完整流地址")
    if protocol == "http":
        return probe_http(url, timeout)
    return probe_rtsp(url, timeout)
