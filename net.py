"""Single HTTP transport. Exit codes: 0 when run directly; callers map ConfigError to 2.

Importing this module performs no I/O. Redirects are not followed, so a bearer
header is never forwarded across hosts. Only public GET/HEAD responses are
cached; authenticated and modifying requests bypass the cache. POSTs are never
retried. Everything leaves through one paced function.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

OFFICIAL_API_BASE = "https://api.clashofclans.com/v1"
CLASHKING_API_BASE = "https://api.clashk.ing/v2"
SCID_API_BASE = "https://ingame.id.supercell.com/api"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
RETRY_STATUSES = frozenset({0, 429, 502, 503, 504, 520, 521, 522, 523, 524})
MIN_SPACING = 0.4
MAX_BODY = 8 * 1024 * 1024
CK_COOLDOWN = 90.0
_ck_slots = threading.BoundedSemaphore(2)
_ck_until = [0.0]
_ck_lock = threading.Lock()
_request_lock = None
_last_request_at = None


class ConfigError(ValueError):
    """A required configuration value is missing or malformed."""


@dataclass
class Response:
    status: int
    body: str
    ok: bool
    verdict: str
    elapsed: float
    url: str
    cached: bool


def validate_url(url: str) -> str:
    parts = urllib.parse.urlsplit(str(url))
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ConfigError("Source must be an absolute HTTP(S) URL")
    if parts.username or parts.password or parts.fragment:
        raise ConfigError("Credentials and fragments are not allowed in source URLs")
    return str(url)


def raise_for_config() -> None:
    """Require explicitly configured API base and token, without exposing either."""
    missing = [key for key in ("COC_API_BASE", "COC_API_TOKEN")
               if not os.environ.get(key, "").strip()]
    if missing:
        raise ConfigError("Unset configuration: " + ", ".join(missing))
    base = validate_url(os.environ["COC_API_BASE"].strip())
    parts = urllib.parse.urlsplit(base)
    if parts.scheme != "https" or parts.query:
        raise ConfigError("COC_API_BASE must use HTTPS without a query")


def quote(value: object) -> str:
    return urllib.parse.quote(str(value), safe="")


def add_query(url: str, values: dict) -> str:
    filtered = [(key, value) for key, value in values.items() if value is not None]
    if not filtered:
        return url
    return url + ("&" if "?" in url else "?") + urllib.parse.urlencode(filtered, doseq=True)


def _encode(data) -> Optional[bytes]:
    if data is None:
        return None
    if isinstance(data, bytes):
        return data
    if isinstance(data, str):
        return data.encode("utf-8")
    return json.dumps(data, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _cache_path() -> Path:
    configured = os.environ.get("COC_CACHE_PATH")
    return (Path(configured).expanduser() if configured else
            Path.home() / ".cache" / "coc-recover" / "cache.sqlite3")


def _cache_connection():
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), timeout=5)
    connection.execute("CREATE TABLE IF NOT EXISTS responses ("
                       "method TEXT, url TEXT, body_key TEXT, status INTEGER, "
                       "body TEXT, final_url TEXT, created REAL, "
                       "PRIMARY KEY(method,url,body_key))")
    return connection


def _cached(key, ttl):
    try:
        connection = _cache_connection()
        try:
            row = connection.execute(
                "SELECT status,body,final_url,created FROM responses "
                "WHERE method=? AND url=? AND body_key=?", key).fetchone()
        finally:
            connection.close()
        if row and 0 <= time.time() - row[3] < ttl:
            return row[:3]
    except (OSError, sqlite3.Error):
        pass
    return None


def _save_cache(key, status, body, final_url):
    try:
        connection = _cache_connection()
        try:
            with connection:
                connection.execute("INSERT OR REPLACE INTO responses VALUES(?,?,?,?,?,?,?)",
                                   (*key, status, body, final_url, time.time()))
        finally:
            connection.close()
    except (OSError, sqlite3.Error):
        pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _request_once(url, method, headers, data, timeout):
    """The only actual HTTP operation; return status, text and final URL."""
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(MAX_BODY + 1)
            if len(raw) > MAX_BODY:
                return 413, "Response exceeded the local size limit", url
            charset = response.headers.get_content_charset() or "utf-8"
            try:
                text = raw.decode(charset, errors="replace")
            except LookupError:
                text = raw.decode("utf-8", errors="replace")
            return response.status, text, response.geturl()
    except urllib.error.HTTPError as error:
        try:
            try:
                body = error.read(MAX_BODY).decode("utf-8", errors="replace")
            except (OSError, http.client.HTTPException):
                # Preserve a known status: even a truncated 404 must never retry.
                body = ""
        finally:
            error.close()
        return error.code, body, url
    except (urllib.error.URLError, OSError, TimeoutError, http.client.HTTPException):
        return 0, "", url


def _paced_request(url, method, headers, data, timeout):
    global _request_lock, _last_request_at
    if _request_lock is None:
        _request_lock = threading.Lock()
    with _request_lock:
        now = time.monotonic()
        if _last_request_at is not None:
            wait = MIN_SPACING - (now - _last_request_at)
            if wait > 0:
                time.sleep(wait)
        _last_request_at = time.monotonic()
        return _request_once(url, method, headers, data, timeout)


def classify(src, resp) -> str:
    """Return one of the nine public-source classification labels.

    The `auth` flag marks a route that needs a token; it does not turn every 2xx
    into an `auth` result. On 2xx the body decides, so a reachable payload counts
    as `ok` and survives --write-sources. The flag only stands in for a gated page
    that answered without a password form or a marker.
    """
    if resp.status == 0:
        return "unreachable"
    if resp.status in {403, 429}:
        return "blocked"
    if resp.status in {404, 410}:
        return "gone"
    if resp.status == 401:
        return "auth"
    low = (resp.body or "").lower()
    if not 200 <= resp.status < 300 or not low.strip():
        return "empty"
    gated = "auth" if src.get("auth") else "unmarked"
    if src.get("json"):
        try:
            json.loads(resp.body)
        except (TypeError, ValueError):
            return "badjson"
        return "ok"
    password_input = re.search(r"<input\b[^>]*\btype\s*=\s*(?:['\"]password['\"]|password\b)", low)
    if password_input and any(text in low for text in ("login", "log in", "sign in")):
        return "auth"
    markers = src.get("markers") or []
    hit = any(str(marker).lower() in low for marker in markers if str(marker))
    if src.get("js"):
        return "ok-js" if hit or "javascript" in low else gated
    return "ok" if hit else gated


def fetch(url, *, method="GET", headers=None, data=None, ttl=900,
          timeout=20, retries=3) -> Response:
    """Fetch through one paced path; retries counts additional safe attempts."""
    started = time.monotonic()
    url = validate_url(url)
    method = str(method).upper()
    if method not in {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}:
        raise ValueError("Unsupported HTTP method")
    if timeout <= 0 or type(retries) is not int or retries < 0:
        raise ValueError("timeout must be positive and retries must be a non-negative integer")
    supplied = {str(key): str(value) for key, value in (headers or {}).items()}
    lowered = {key.lower(): value for key, value in supplied.items()}
    outgoing = {"User-Agent": UA, "Accept": "application/json,text/html;q=0.9",
                "Accept-Language": "en-US,en;q=0.8"}
    outgoing.update(supplied)
    payload = _encode(data)
    if data is not None and not isinstance(data, (bytes, str)) and "content-type" not in lowered:
        outgoing["Content-Type"] = "application/json"
    query_keys = {key.lower() for key, _ in urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query)}
    secret_keys = {"token", "code", "email", "password", "key", "api_key", "receipt-data"}
    cacheable = (method in {"GET", "HEAD"} and ttl > 0 and
                 not ({"authorization", "cookie", "proxy-authorization"} & set(lowered)) and
                 not (secret_keys & query_keys))
    key = (method, url, hashlib.sha256(payload or b"").hexdigest())
    if cacheable:
        row = _cached(key, ttl)
        if row:
            status, body, final_url = row
            response = Response(status, body, True, "ok", time.monotonic() - started,
                                final_url, True)
            return response
    count = int(retries) if method in {"GET", "HEAD"} else 0
    status, body, final_url = 0, "", url
    for attempt in range(count + 1):
        status, body, final_url = _paced_request(url, method, outgoing, payload, timeout)
        if status not in RETRY_STATUSES or attempt == count:
            break
        time.sleep(2 ** attempt)
    ok = 200 <= status < 300
    response = Response(int(status), str(body), ok, "ok" if ok else "empty",
                        max(0.0, time.monotonic() - started), str(final_url), False)
    if not ok:
        response.verdict = classify({}, response)
    if cacheable and ok:
        _save_cache(key, status, body, final_url)
    return response


def _json_or(response) -> dict:
    try:
        value = json.loads(response.body or "{}")
    except (TypeError, ValueError):
        return {"ok": False, "error": "http_%s" % response.status}
    if not isinstance(value, dict):
        return {"ok": False, "error": "http_%s" % response.status}
    return value


def _ck_up() -> bool:
    with _ck_lock:
        return time.time() >= _ck_until[0]


def _ck_trip() -> None:
    with _ck_lock:
        _ck_until[0] = time.time() + CK_COOLDOWN


def _official_equivalent(path: str) -> Optional[str]:
    """Translate the one ClashKing player route that also exists officially."""
    head, separator, tail = path.partition("?")
    parts = head.strip("/").split("/")
    if len(parts) == 2 and parts[0] == "player":
        return "/players/" + parts[1] + (separator + tail if separator else "")
    return None


def api_get(path, token, base=CLASHKING_API_BASE, allow_official=True):
    """Authenticated GET with ClashKing-first failover; return (status, payload).

    A retryable or unreachable ClashKing result trips a local cooldown. Only the
    routes with an official equivalent are repeated on the official API; the rest
    return a local error object instead of a fabricated status. ClashKing answers
    of 401/403/404 are treated as real answers, not as outages.
    """
    headers = {"Authorization": "Bearer " + token} if token else {}
    if _ck_up():
        with _ck_slots:
            response = fetch(base.rstrip("/") + path, headers=headers, ttl=0, retries=2)
        if response.ok or response.status in {401, 403, 404}:
            return response.status, _json_or(response)
        _ck_trip()
        if not allow_official:
            raise RuntimeError("clashking unavailable, failover disabled")
        equivalent = _official_equivalent(path)
        if equivalent is None:
            return response.status, {"ok": False, "error": "clashking_unavailable"}
        fallback = fetch(OFFICIAL_API_BASE + equivalent, headers=headers, ttl=0, retries=2)
        return fallback.status, _json_or(fallback)
    if not allow_official:
        raise RuntimeError("clashking cooling down, failover disabled")
    equivalent = _official_equivalent(path) or path
    fallback = fetch(OFFICIAL_API_BASE + equivalent, headers=headers, ttl=0, retries=2)
    return fallback.status, _json_or(fallback)


def scid_post(path, form, token=None, timeout=25) -> dict:
    """POST form data to the unsupported SCID helper base; return the JSON object.

    Gap G17: the route set is undocumented, so a non-JSON or non-object body
    becomes a local error object rather than an exception.
    """
    headers = {"Accept": "application/json",
               "Content-Type": "application/x-www-form-urlencoded"}
    if token:
        headers["Authorization"] = "Bearer " + token
    body = urllib.parse.urlencode(
        {key: value for key, value in form.items() if value is not None}).encode("utf-8")
    status, text, _ = _paced_request(validate_url(SCID_API_BASE + path), "POST",
                                     headers, body, timeout)
    if status == 0:
        return {"ok": False, "error": "transport"}
    try:
        value = json.loads(text or "{}")
    except (TypeError, ValueError):
        return {"ok": False, "error": "http_%s" % status}
    if not isinstance(value, dict):
        return {"ok": False, "error": "http_%s" % status}
    value.setdefault("ok", 200 <= status < 300)
    return value
