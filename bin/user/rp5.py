"""
weewx-rp5 — WeeWX extension to upload weather data to rp5.ru via sgate API.

Targeting WeeWX 5.x (stable) with fallback to 4.10+.
Python 3.8+.

API documentation: https://rp5.ru/docs/sgate/ru

Original work © 2018-2019 Sapegin Oleg <sapegin.o@gmail.com>
Python 3 / WeeWX 5.x rewrite © 2026 Vasilii Zakharov
License: MIT
"""
from __future__ import annotations

import math
import queue
import sys
import urllib.error
import urllib.request
from typing import Optional

import weewx
import weewx.manager
import weewx.restx
import weewx.units

# Logger — WeeWX 5.x uses Python logging via weeutil.logger
try:
    import weeutil.logger
    import logging
    log = logging.getLogger(__name__)
except ImportError:
    # WeeWX 4.x fallback
    import syslog

    class _SyslogShim:
        def info(self, msg: str) -> None:
            syslog.syslog(syslog.LOG_INFO, "rp5: " + msg)

        def warning(self, msg: str) -> None:
            syslog.syslog(syslog.LOG_WARNING, "rp5: " + msg)

        def error(self, msg: str) -> None:
            syslog.syslog(syslog.LOG_ERR, "rp5: " + msg)

        def debug(self, msg: str) -> None:
            syslog.syslog(syslog.LOG_DEBUG, "rp5: " + msg)

    log = _SyslogShim()  # type: ignore[assignment]


VERSION = "1.0.0"
PROTOCOL_NAME = "RP5-API"
DEFAULT_SERVER_URL = "https://sgate.rp5.ru"

# Field mapping — WeeWX field → (sgate API param, format string, validator)
# Per https://rp5.ru/docs/sgate/ru — params are UPPERCASE per spec.
FIELD_MAP = {
    # WeeWX key       sgate    fmt      validator (returns True if valid)
    "dateTime":     ("updated", "%d",   lambda v: v is not None),
    "outTemp":      ("T",      "%.1f",  lambda v: -99.9 <= v <= 99.9),
    "outHumidity":  ("U",      "%.0f",  lambda v: 0 <= v <= 100),
    "windSpeed":    ("FF",     "%.1f",  lambda v: v >= 0),
    "windDir":      ("DD",     "%.0f",  lambda v: 0 <= v <= 359),
    "windGust":     ("ff10",   "%.1f",  lambda v: v >= 0),
}


# ============================================================================
#                            class StdRP5
# ============================================================================

class StdRP5(weewx.restx.StdRESTful):
    """RESTful service for uploading archive records to rp5.ru sgate API."""

    def __init__(self, engine, config_dict: dict) -> None:
        super().__init__(engine, config_dict)

        site_dict = weewx.restx.get_site_dict(config_dict, "RP5", "api_key")
        if site_dict is None:
            log.info("RP5 not configured (missing api_key); skipping")
            return

        site_dict.setdefault("server_url", DEFAULT_SERVER_URL)

        manager_dict = weewx.manager.get_manager_dict_from_config(
            config_dict, "wx_binding"
        )

        self.archive_queue: queue.Queue = queue.Queue()
        self.archive_thread = RP5Thread(
            self.archive_queue,
            manager_dict,
            protocol_name=PROTOCOL_NAME,
            **site_dict,
        )
        self.archive_thread.start()
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)

        api_key_redacted = (site_dict["api_key"][:6] + "***"
                            if len(site_dict["api_key"]) > 6 else "***")
        log.info(
            "RP5 v%s: data will be uploaded to %s (api_key %s)"
            % (VERSION, site_dict["server_url"], api_key_redacted)
        )

    def new_archive_record(self, event) -> None:
        self.archive_queue.put(event.record)


# ============================================================================
#                            class RP5Thread
# ============================================================================

class RP5Thread(weewx.restx.RESTThread):
    """Thread that posts archive records to rp5.ru sgate API."""

    def __init__(
        self,
        archive_queue: queue.Queue,
        manager_dict: dict,
        api_key: str,
        server_url: str = DEFAULT_SERVER_URL,
        protocol_name: str = PROTOCOL_NAME,
        post_interval: int = 60,        # rp5 limit: 60 req/min
        max_backlog: int = sys.maxsize,
        stale: Optional[int] = None,
        log_success: bool = True,
        log_failure: bool = True,
        timeout: int = 10,
        max_tries: int = 3,
        retry_wait: int = 5,
        skip_upload: bool = False,
    ) -> None:
        super().__init__(
            archive_queue,
            protocol_name=protocol_name,
            manager_dict=manager_dict,
            post_interval=int(post_interval),
            max_backlog=int(max_backlog),
            stale=stale,
            log_success=log_success,
            log_failure=log_failure,
            timeout=int(timeout),
            max_tries=int(max_tries),
            retry_wait=int(retry_wait),
            skip_upload=skip_upload,
        )

        self.api_key = api_key
        self.server_url = server_url.rstrip("/")

    @staticmethod
    def _is_valid(value) -> bool:
        """True if value is not None and not NaN."""
        if value is None:
            return False
        try:
            return not math.isnan(float(value))
        except (TypeError, ValueError):
            return False

    def format_url(self, incoming_record: dict) -> str:
        """Build URL with sgate query parameters from a WeeWX archive record."""
        # WeeWX records may come in different unit systems; normalize.
        record = weewx.units.to_METRICWX(incoming_record)

        parts = ["api_key=%s" % self.api_key]
        for weewx_key, (api_key, fmt, validator) in FIELD_MAP.items():
            value = record.get(weewx_key)
            if not self._is_valid(value):
                continue
            try:
                if not validator(value):
                    log.warning(
                        "field %s value %r out of range, skipping"
                        % (weewx_key, value)
                    )
                    continue
            except (TypeError, ValueError):
                continue
            parts.append("%s=" % api_key + (fmt % value))

        url = "%s/?%s" % (self.server_url, "&".join(parts))
        if weewx.debug >= 2:
            # Don't log the api_key in plaintext
            redacted = url.replace(self.api_key, "***")
            log.debug("URL: %s" % redacted)
        return url

    def post_request(self, request, data=None):
        """Execute the HTTP request. Differentiates 4xx (no retry) vs 5xx (retry)."""
        try:
            if data is None:
                response = urllib.request.urlopen(request, timeout=self.timeout)
            else:
                response = urllib.request.urlopen(request, data=data, timeout=self.timeout)
            return response
        except urllib.error.HTTPError as exc:
            # 400 — bad request (wrong key/values), 429 — rate limit; don't retry
            if exc.code in (400, 429):
                raise weewx.restx.FailedPost(
                    "server returned HTTP %d %s" % (exc.code, exc.reason)
                ) from exc
            raise
        except urllib.error.URLError as exc:
            raise weewx.restx.FailedPost("connection error: %s" % exc.reason) from exc
