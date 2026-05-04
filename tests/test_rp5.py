"""Unit tests for weewx-rp5 driver.

Tests run without WeeWX installed by mocking the parent classes.
"""
from __future__ import annotations

import math
import sys
from unittest.mock import MagicMock, patch

import pytest


# Mock weewx modules before importing rp5
@pytest.fixture(autouse=True)
def mock_weewx(monkeypatch):
    weewx_mock = MagicMock()
    weewx_mock.NEW_ARCHIVE_RECORD = "new_archive_record"
    weewx_mock.debug = 0
    weewx_mock.units.to_METRICWX = lambda r: r
    weewx_mock.restx.StdRESTful = type("StdRESTful", (), {"__init__": lambda *a, **k: None})
    weewx_mock.restx.RESTThread = type("RESTThread", (), {"__init__": lambda *a, **k: None})
    weewx_mock.restx.FailedPost = Exception
    weewx_mock.restx.get_site_dict = lambda *a, **k: None

    monkeypatch.setitem(sys.modules, "weewx", weewx_mock)
    monkeypatch.setitem(sys.modules, "weewx.restx", weewx_mock.restx)
    monkeypatch.setitem(sys.modules, "weewx.units", weewx_mock.units)
    monkeypatch.setitem(sys.modules, "weewx.manager", MagicMock())
    monkeypatch.setitem(sys.modules, "weeutil", MagicMock())
    monkeypatch.setitem(sys.modules, "weeutil.logger", MagicMock())
    yield


def _import_rp5():
    """Import rp5 module after mocks are set up."""
    sys.path.insert(0, "bin/user")
    if "rp5" in sys.modules:
        del sys.modules["rp5"]
    import rp5
    return rp5


def test_field_map_uppercase_per_api_spec():
    """All param names match rp5 API spec — uppercase per docs."""
    rp5 = _import_rp5()
    expected = {
        "dateTime": "updated",
        "outTemp": "T",
        "outHumidity": "U",
        "windSpeed": "FF",
        "windDir": "DD",
        "windGust": "ff10",  # ff10 per spec is lowercase
    }
    for weewx_key, api_key in expected.items():
        assert rp5.FIELD_MAP[weewx_key][0] == api_key


def test_is_valid_filters_none_and_nan():
    rp5 = _import_rp5()
    cls = rp5.RP5Thread
    assert cls._is_valid(0) is True
    assert cls._is_valid(0.0) is True
    assert cls._is_valid(-99.9) is True
    assert cls._is_valid(99.9) is True
    assert cls._is_valid(None) is False
    assert cls._is_valid(float("nan")) is False
    assert cls._is_valid("not a number") is False


def test_validators_outTemp():
    rp5 = _import_rp5()
    validator = rp5.FIELD_MAP["outTemp"][2]
    assert validator(0) is True
    assert validator(99.9) is True
    assert validator(-99.9) is True
    assert validator(150) is False
    assert validator(-200) is False


def test_validators_outHumidity():
    rp5 = _import_rp5()
    validator = rp5.FIELD_MAP["outHumidity"][2]
    assert validator(50) is True
    assert validator(0) is True
    assert validator(100) is True
    assert validator(-1) is False
    assert validator(101) is False


def test_validators_windDir():
    rp5 = _import_rp5()
    validator = rp5.FIELD_MAP["windDir"][2]
    assert validator(0) is True
    assert validator(180) is True
    assert validator(359) is True
    assert validator(360) is False
    assert validator(-1) is False


def test_validators_wind_speeds():
    rp5 = _import_rp5()
    for fld in ("windSpeed", "windGust"):
        v = rp5.FIELD_MAP[fld][2]
        assert v(0) is True
        assert v(50) is True
        assert v(-1) is False


def test_default_server_url_is_https():
    """Security: default endpoint must be HTTPS."""
    rp5 = _import_rp5()
    assert rp5.DEFAULT_SERVER_URL.startswith("https://")


def test_version():
    rp5 = _import_rp5()
    assert rp5.VERSION == "1.0.0"
