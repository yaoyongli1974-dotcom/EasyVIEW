"""WS-Discovery ProbeMatch 解析。"""
from core.onvif_discovery import _parse_match

SAMPLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
 xmlns:a="http://schemas.xmlsoap.org/ws/2004/08/addressing"
 xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery">
 <s:Body>
  <d:ProbeMatches>
   <d:ProbeMatch>
    <a:EndpointReference><a:Address>urn:uuid:1234</a:Address></a:EndpointReference>
    <d:Types>dn:NetworkVideoTransmitter</d:Types>
    <d:Scopes>onvif://www.onvif.org/manufacturer/Hikvision onvif://www.onvif.org/model/DS-2CD</d:Scopes>
    <d:XAddrs>http://192.168.1.10/onvif/device_service</d:XAddrs>
   </d:ProbeMatch>
  </d:ProbeMatches>
 </s:Body>
</s:Envelope>"""


def test_parse_match():
    dev = _parse_match(SAMPLE, ("192.168.1.10", 0))
    assert dev is not None
    assert dev["address"] == "192.168.1.10"
    assert dev["endpoint"] == "urn:uuid:1234"
    assert dev["manufacturer"] == "Hikvision"
    assert dev["model"] == "DS-2CD"
    assert dev["xaddrs"] == ["http://192.168.1.10/onvif/device_service"]


def test_parse_match_bad_xml():
    assert _parse_match(b"not xml", ("1.2.3.4", 0)) is None


def test_parse_match_no_probe():
    assert _parse_match(b"<Envelope/>", ("1.2.3.4", 0)) is None
