# Changelog

## v1.0.0 — 2026-05-04

Major rewrite for **Python 3** and **WeeWX 5.x**.

### Changed
- Python 3.8+ required (Python 2 dropped)
- WeeWX 5.x compatibility (with fallback for 4.10+)
- HTTP → HTTPS by default (`https://sgate.rp5.ru`)
- Field names UPPERCASE per API spec (`T`, `U`, `DD`, `FF`) — fixes silent data loss in older versions
- `Queue` → `queue` (Python 3 stdlib)
- `urllib2` → `urllib.request` (Python 3 stdlib)
- `sys.maxint` → `sys.maxsize` (Python 3)
- `syslog` → Python `logging` (works on WeeWX 5.x; falls back to syslog on 4.x)
- `post_interval` default 2 → 60 (rp5 rate limit is 60 req/min)
- `timeout` default 5 → 10 seconds

### Added
- Type hints (PEP 484)
- NaN value filtering (was: only `None`)
- Range validation per field (T -99.9..99.9, U 0..100, DD 0..359, FF/ff10 ≥0)
- API key redaction in logs
- HTTP 4xx (no retry) vs 5xx (retry) differentiation
- `pyproject.toml` for modern packaging
- GitHub Actions CI (pytest + ruff)
- Unit tests (`tests/test_rp5.py`)

### Fixed
- Bug: lowercase field names in URL did not match API spec (silent failure for some servers)
- Bug: NaN values were sent as `nan` causing API rejection

---

## v0.4 — 2019-03-26 (by Sapegin Oleg, original repo)
- Upload rate limit added (60 req/min API limit)

## v0.3 — 2018-12-02
- Wind/wind gust data in m/s

## v0.2 — 2018-11-29
- Temperature bug fixed

## v0.1 — 2018-11-06
- Initial release
