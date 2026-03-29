"""
rp5.py -- WeeWX RESTful service for uploading data to rp5.ru via the sgate API.

API reference: https://rp5.ru/docs/sgate/ru

Supported fields (METRICWX unit system -> API parameter):
  outTemp      -> t      (degrees C, 1 decimal)
  outHumidity  -> u      (%, integer)
  windSpeed    -> ff     (m/s, 1 decimal)
  windDir      -> dd     (degrees, integer)
  windGust     -> ff10   (m/s, 1 decimal)
  barometer    -> p0     (hPa, 1 decimal)
  rain         -> rr     (mm per interval, 1 decimal)
  dateTime     -> updated (Unix timestamp, integer)
"""

import logging
import queue
import sys

import urllib.error
import urllib.request

import weewx.manager
import weewx.restx
import weewx.units

log = logging.getLogger(__name__)

# ============================================================================
#                            class StdRP5
# ============================================================================


class StdRP5(weewx.restx.StdRESTful):
    """RESTful service that uploads archive records to rp5.ru."""

    api_url = 'https://sgate.rp5.ru'
    protocol_name = 'RP5-API'

    def __init__(self, engine, config_dict):
        super(StdRP5, self).__init__(engine, config_dict)

        _rp5_dict = weewx.restx.get_site_dict(config_dict, 'RP5', 'api_key')
        if _rp5_dict is None:
            return

        _rp5_dict.setdefault('server_url', StdRP5.api_url)

        _manager_dict = weewx.manager.get_manager_dict_from_config(
            config_dict, 'wx_binding'
        )

        self.archive_queue = queue.Queue()
        self.archive_thread = RP5Thread(
            self.archive_queue,
            _manager_dict,
            protocol_name=StdRP5.protocol_name,
            **_rp5_dict,
        )
        self.archive_thread.start()
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)

        log.info(
            "rp5: %s: Data for api_key %s will be uploaded to %s",
            StdRP5.protocol_name,
            _rp5_dict['api_key'],
            _rp5_dict['server_url'],
        )

    def new_archive_record(self, event):
        self.archive_queue.put(event.record)


# ============================================================================
#                           class RP5Thread
# ============================================================================


class RP5Thread(weewx.restx.RESTThread):
    """Thread that formats and posts records to the RP5 sgate API."""

    # Map WeeWX field names to (api_param, format_string) pairs.
    # All values are expressed in the METRICWX unit system before formatting.
    _FORMATS = {
        'dateTime':    ('updated', '%i'),
        'outTemp':     ('t',       '%.1f'),
        'outHumidity': ('u',       '%.0f'),
        'windSpeed':   ('ff',      '%.1f'),
        'windDir':     ('dd',      '%.0f'),
        'windGust':    ('ff10',    '%.1f'),
        'barometer':   ('p0',      '%.1f'),
        'rain':        ('rr',      '%.1f'),
    }

    def __init__(self, q, manager_dict, api_key, server_url,
                 protocol_name='Unknown-RESTful', post_interval=2,
                 max_backlog=sys.maxsize, stale=None, log_success=True,
                 log_failure=True, timeout=10, max_tries=3, retry_wait=5,
                 skip_upload=False):

        super(RP5Thread, self).__init__(
            q,
            protocol_name=protocol_name,
            manager_dict=manager_dict,
            post_interval=post_interval,
            max_backlog=max_backlog,
            stale=stale,
            log_success=log_success,
            log_failure=log_failure,
            timeout=timeout,
            max_tries=max_tries,
            retry_wait=retry_wait,
            skip_upload=skip_upload,
        )
        self.api_key = api_key
        self.server_url = server_url

    def format_url(self, incoming_record):
        """Build the sgate API URL for a single archive record."""
        record = weewx.units.to_METRICWX(incoming_record)

        params = ['api_key=%s' % self.api_key]
        for field, (param, fmt) in self._FORMATS.items():
            value = record.get(field)
            if value is not None:
                params.append('%s=%s' % (param, fmt % value))

        url = '%s/?%s' % (self.server_url, '&'.join(params))

        if weewx.debug >= 2:
            log.debug('restx: %s: url: %s', self.protocol_name, url)

        return url

    def post_request(self, request, data=None):
        """Execute the HTTP request, mapping API error codes to FailedPost."""
        try:
            return urllib.request.urlopen(request, timeout=self.timeout)
        except urllib.error.HTTPError as e:
            # Wrap all HTTP errors as FailedPost so the base-class retry and
            # backoff logic applies uniformly.  The caller already logs the
            # failure; the message here is for debug context only.
            raise weewx.restx.FailedPost(
                "Server returned HTTP %d (%s)" % (e.code, e.reason)
            ) from e
