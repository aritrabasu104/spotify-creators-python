"""Bounded standalone Spotify HTTP; no browser, hidden retry or redirect."""

from dataclasses import dataclass, field
from http.client import HTTPException
import json
import math
import re
import threading
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

API_HOSTS = frozenset({
    "accounts.spotify.com",
    "api.spotify.com",
    "api-v5.anchor.fm",
    "creators-graph.spotify.com",
})


@dataclass(frozen=True)
class Response:
    status: int
    data: object = field(repr=False)
    headers: dict = field(default_factory=dict, repr=False)


class ProviderError(RuntimeError):
    def __init__(self, status, code, details=None, *, retry_after=None):
        self.status, self.code = status, code
        self.details=details
        self.retry_after = retry_after
        super().__init__(f"Spotify HTTP {status}: {code}")


class OutcomeUnknown(RuntimeError):
    """An admitted mutation was dispatched but its result is unresolved."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class HttpTransport:
    def __init__(self, *, timeout=30, max_response=16 * 1024 * 1024):
        if not 0 < timeout <= 60 or not 0 < max_response <= 16 * 1024 * 1024:
            raise ValueError("Invalid Spotify network budget")
        self.timeout, self.max_response = timeout, max_response
        self._local = threading.local()

    @property
    def opener(self):
        if not hasattr(self._local, "opener"):
            self._local.opener = build_opener(ProxyHandler({}), NoRedirect())
        return self._local.opener

    @opener.setter
    def opener(self, value):
        self._local.opener = value

    def execute(self, method, url, *, body=None, form=None, headers=None, mutation=False):
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.hostname not in API_HOSTS or parsed.username
                or parsed.password or parsed.port not in {None, 443} or parsed.fragment):
            raise ValueError("Request left the recovered Spotify HTTPS API origins")
        if body is not None and form is not None:
            raise ValueError("Select one actual body encoding")
        selected = {"User-Agent": "spotify-creators-client/0.2.0", "Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
            selected["Content-Type"] = "application/json"
        elif form is not None:
            data = urlencode(form).encode()
            selected["Content-Type"] = "application/x-www-form-urlencoded"
        selected.update(headers or {})
        request = Request(url, data=data, headers=selected, method=method)
        try:
            try:
                response = self.opener.open(request, timeout=self.timeout)
            except HTTPError as exc:
                response = exc
            with response:
                raw = response.read(self.max_response + 1)
                if len(raw) > self.max_response:
                    if mutation:
                        raise OutcomeUnknown("Mutation returned an oversized response; reconcile its original intent")
                    raise ProviderError(response.code, "response_limit")
                try:
                    value = json.loads(raw)
                except (ValueError, UnicodeError):
                    # Preserve the native short error identifiers, never an
                    # arbitrary provider page, credential or issued URL.
                    value = ({"error": raw.decode('ascii')} if not 200 <= response.code < 300
                             and re.fullmatch(rb'[A-Za-z0-9_.:-]{1,96}', raw) else
                             {'message':raw[:4096].decode('utf-8',errors='replace')}
                             if not 200<=response.code<300 else None)
                return Response(response.code, value, {k.lower(): v for k, v in response.headers.items()
                                                       if k.lower() in {"content-type", "retry-after"}})
        except (URLError, TimeoutError, ConnectionError, OSError, HTTPException) as exc:
            if mutation:
                raise OutcomeUnknown("Original Spotify mutation needs reconciliation; no replay was made") from exc
            raise


def require_success(response):
    if not 200 <= response.status < 300:
        data = response.data if isinstance(response.data, dict) else {}
        value = data.get("error")
        code = value.get("code") if isinstance(value, dict) else value
        if not isinstance(code, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,96}", code):
            code = "provider_error"
        retry_after = None
        try:
            seconds = float(response.headers.get('retry-after', ''))
            if math.isfinite(seconds) and seconds >= 0:
                retry_after = seconds
        except (TypeError, ValueError):
            pass
        raise ProviderError(response.status, code, data, retry_after=retry_after)
    return response.data
