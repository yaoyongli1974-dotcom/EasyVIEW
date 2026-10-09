"""基于 WS-Discovery 的 ONVIF 设备自动发现（手写多播探测，无需额外依赖）。

原理：向 239.255.255.250:3702 发送 SOAP Probe，设备以单播回 ProbeMatch，
解析出 EndpointReference / XAddrs / Types / Scopes / Manufacturer。
"""
import socket
import struct
import time
import uuid
from xml.etree import ElementTree as ET

DISCOVERY_ADDR = "239.255.255.250"
DISCOVERY_PORT = 3702

# 厂商名(小写包含匹配) -> rtsp_templates 的 key
ONVIF_MANUFACTURERS = {
    "hikvision": "hikvision",
    "dahua": "dahua",
    "uniview": "uniview",
    "imou": "imou",
    "axis": "onvif",
    "tiandy": "onvif",
    "hanbang": "onvif",
}

_NS = {
    "s": "http://www.w3.org/2003/05/soap-envelope",
    "a": "http://schemas.xmlsoap.org/ws/2004/08/addressing",
    "d": "http://schemas.xmlsoap.org/ws/2005/04/discovery",
    "dn": "http://www.onvif.org/ver10/network/wsdl",
}


def _probe_message() -> str:
    mid = f"urn:uuid:{uuid.uuid4()}"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
  xmlns:a="http://schemas.xmlsoap.org/ws/2004/08/addressing"
  xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery">
  <s:Header>
    <a:MessageID>{mid}</a:MessageID>
    <a:Action s:mustUnderstand="1">http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</a:Action>
    <a:To s:mustUnderstand="1">urn:schemas-xmlsoap-org:ws:2005:04:discovery</a:To>
  </s:Header>
  <s:Body>
    <d:Probe>
      <d:Types>dn:NetworkVideoTransmitter</d:Types>
      <d:Scopes></d:Scopes>
    </d:Probe>
  </s:Body>
</s:Envelope>"""


def _scope_value(scope: str) -> str:
    """从 ONVIF scope URI 中取值。

    兼容两种写法：
      onvif://www.onvif.org/manufacturer/Hikvision   （以 / 分隔）
      onvif://host/manufacturer:Hikvision            （以 : 分隔）
    """
    return scope.rstrip("/").replace(":", "/").split("/")[-1]


def _parse_match(xml_bytes: bytes, src_addr: tuple) -> dict | None:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None
    matches = root.findall(".//d:ProbeMatch", _NS)
    if not matches:
        return None
    out = {
        "address": src_addr[0],
        "endpoint": None,
        "xaddrs": [],
        "types": "",
        "scopes": "",
        "manufacturer": "",
        "model": "",
    }
    for m in matches:
        ep = m.find("a:EndpointReference/a:Address", _NS)
        if ep is not None and out["endpoint"] is None:
            out["endpoint"] = ep.text
        xa = m.find("d:XAddrs", _NS)
        if xa is not None and xa.text:
            out["xaddrs"] = [x.strip() for x in xa.text.split() if x.strip()]
        types = m.find("d:Types", _NS)
        if types is not None:
            out["types"] = types.text or ""
        scopes = m.find("d:Scopes", _NS)
        if scopes is not None and scopes.text:
            out["scopes"] = scopes.text
            for tok in scopes.text.split():
                low = tok.lower()
                if "manufacturer" in low:
                    out["manufacturer"] = _scope_value(tok)
                elif "model" in low:
                    out["model"] = _scope_value(tok)
    return out


def discover(timeout: float = 3.0) -> list[dict]:
    """返回发现的设备列表（已按 endpoint 去重）。"""
    msg = _probe_message().encode("utf-8")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("", 0))
        mreq = struct.pack("4s4s", socket.inet_aton(DISCOVERY_ADDR), socket.inet_aton("0.0.0.0"))
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    except OSError:
        pass
    sock.settimeout(timeout)
    try:
        sock.sendto(msg, (DISCOVERY_ADDR, DISCOVERY_PORT))
    except OSError as e:
        sock.close()
        raise RuntimeError(f"WS-Discovery 发送失败：{e}")

    found: dict[str, dict] = {}
    deadline = time.time() + timeout
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        sock.settimeout(min(remaining, timeout))
        try:
            data, addr = sock.recvfrom(65535)
        except socket.timeout:
            break
        dev = _parse_match(data, addr)
        if dev and dev["endpoint"] and dev["endpoint"] not in found:
            found[dev["endpoint"]] = dev
    sock.close()
    return list(found.values())
