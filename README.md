# weewx-rp5

[WeeWX](http://weewx.com/) extension for uploading archive weather data to **[rp5.ru](https://rp5.ru/)** — Russia's largest non-governmental weather archive — via the official [sgate API](https://rp5.ru/docs/sgate/ru).

## Status

- **Python 3.8+** (Python 2 dropped)
- **WeeWX 4.x and 5.x** compatible
- HTTPS support
- Retry with exponential backoff
- Rate-limit aware (60 req/min limit on rp5 API)
- Full Python `logging` integration

## Installation

### Via wee_extension utility

```bash
# 1. Download latest release
wget -P /tmp https://github.com/vasiliizakharov/weewx-rp5/releases/latest/download/weewx-rp5.tar.gz

# 2. Stop WeeWX
sudo systemctl stop weewx

# 3. Install
wee_extension --install=/tmp/weewx-rp5.tar.gz

# 4. Edit config — set api_key
sudo nano /etc/weewx/weewx.conf
# In [StdRESTful][[RP5]]:
#   enable = true
#   api_key = YOUR_API_KEY_FROM_SUPPORT_RP5_RU

# 5. Start WeeWX
sudo systemctl start weewx
```

### Manual installation

```bash
git clone https://github.com/vasiliizakharov/weewx-rp5.git
cd weewx-rp5
sudo cp bin/user/rp5.py /etc/weewx/bin/user/
# Then edit weewx.conf as in step 4 above
```

## Configuration

Add to your `weewx.conf`:

```ini
[StdRESTful]
    [[RP5]]
        enable = true
        api_key = YOUR_API_KEY
        # Optional:
        # server_url = https://sgate.rp5.ru
        # post_interval = 60
        # max_tries = 3
        # timeout = 10

[Engine]
    [[Services]]
        restful_services = ..., user.rp5.StdRP5
```

## Getting an API key

Send an email to **support@rp5.ru** with:
1. Your weather station's address (street, city, region, country) or geographic coordinates (lat/lon)
2. Weather station model/name

You will receive a unique `api_key` that allows your station to upload data.

## Mapped fields (WeeWX → rp5 sgate API)

| WeeWX field | rp5 API param | Unit | Range |
|---|---|---|---|
| `dateTime` | `updated` | UNIX timestamp UTC | — |
| `outTemp` | `T` | °C | -99.9 to 99.9 |
| `outHumidity` | `U` | % | 0 to 100 |
| `windDir` | `DD` | degrees | 0 to 359 |
| `windSpeed` | `FF` | m/s | ≥ 0 |
| `windGust` | `ff10` | m/s | ≥ 0 |

Records are converted to `METRICWX` units automatically by WeeWX.

## Rate limiting

The rp5 API enforces a maximum of **60 requests per minute**. The default `post_interval=60` (seconds) keeps you safely within the limit. If your archive interval is shorter than 60 seconds, increase `post_interval`.

## Troubleshooting

- **Logs:** check `/var/log/syslog` or `journalctl -u weewx`
- **Debug mode:** set `debug = 2` in `weewx.conf` for verbose request/response logs
- **HTTP 400:** server rejected data (check API key, value ranges)
- **HTTP 429:** rate limit exceeded — increase `post_interval`

## What's new in 1.0.0

This is a **Python 3 / WeeWX 5.x** rewrite of the original [sapegin-o1eg/weewx-rp5](https://github.com/sapegin-o1eg/weewx-rp5) (v0.4 from 2019, Python 2 only, no longer maintained):

- ✅ Python 3.8+ support (old `Queue`, `urllib2`, `sys.maxint` removed)
- ✅ WeeWX 4.x and 5.x compatibility (auto-detects logger)
- ✅ HTTPS support (recommended)
- ✅ Field name fix — UPPERCASE per API spec (`T`, `U`, `DD`, `FF`)
- ✅ NaN value filtering (was: only `None`)
- ✅ Type hints
- ✅ Improved error handling (HTTP 4xx/5xx differentiated)
- ✅ Retry with exponential backoff
- ✅ Unit tests via `pytest`
- ✅ GitHub Actions CI

## Credits

Original implementation by **Sapegin Oleg** ([sapegin-o1eg](https://github.com/sapegin-o1eg)) — `weewx-rp5` v0.1–0.4 (2018–2019). This fork modernizes the codebase for Python 3 and WeeWX 5.x. Original repository: https://github.com/sapegin-o1eg/weewx-rp5

## License

[MIT](./LICENSE) — see LICENSE file.
