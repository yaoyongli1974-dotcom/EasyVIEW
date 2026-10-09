"""RTSP 模板与厂商匹配。"""
from core.rtsp_templates import build_rtsp, match_vendor


def test_hikvision_main_sub():
    assert build_rtsp("hikvision", "1.2.3.4", 554, "admin", "pw", 1, "main") == (
        "rtsp://admin:pw@1.2.3.4:554/Streaming/Channels/101"
    )
    assert build_rtsp("hikvision", "1.2.3.4", 554, "admin", "pw", 1, "sub") == (
        "rtsp://admin:pw@1.2.3.4:554/Streaming/Channels/102"
    )


def test_dahua_main_sub():
    assert build_rtsp("dahua", "1.2.3.4", 554, "a", "b", 2, "main") == (
        "rtsp://a:b@1.2.3.4:554/cam/realmonitor?channel=2&subtype=0"
    )
    assert build_rtsp("dahua", "1.2.3.4", 554, "a", "b", 2, "sub") == (
        "rtsp://a:b@1.2.3.4:554/cam/realmonitor?channel=2&subtype=1"
    )


def test_special_chars_are_percent_encoded():
    url = build_rtsp("hikvision", "1.2.3.4", 554, "a b", "p@ss:1/2", 1, "main")
    assert "a%20b" in url
    assert "p%40ss%3A1%2F2" in url


def test_unknown_vendor_falls_back_to_onvif():
    url = build_rtsp("nope", "1.2.3.4", 554, "a", "b", 1, "main")
    assert url == "rtsp://a:b@1.2.3.4:554/onvif/stream/1"


def test_match_vendor():
    assert match_vendor("Hikvision") == "hikvision"
    assert match_vendor("Dahua Technology") == "dahua"
    assert match_vendor("Some Uniview cam") == "uniview"
    assert match_vendor("") == "onvif"
