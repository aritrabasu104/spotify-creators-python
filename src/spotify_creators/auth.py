"""Configurable OAuth PKCE, token refresh and authenticated account checks."""

from dataclasses import dataclass, field
import base64
import hashlib
import hmac
import math
import secrets
import time
from urllib.parse import parse_qs, urlencode, urlsplit

from .http import HttpTransport, require_success
from .protocol import ACCOUNTS_ORIGIN

DEFAULT_SCOPES = ("user-read-email", "user-read-private")


@dataclass(frozen=True)
class OAuthAttempt:
    """One PKCE authorization request. Keep this object private until exchange."""

    verifier: str = field(repr=False)
    state: str = field(repr=False)
    redirect_uri: str
    client_id: str
    scopes: tuple[str, ...] = DEFAULT_SCOPES
    authorization_endpoint: str = ACCOUNTS_ORIGIN + "/authorize"

    @classmethod
    def prepare(cls, *, client_id, redirect_uri, scopes=DEFAULT_SCOPES,
                authorization_endpoint=ACCOUNTS_ORIGIN + "/authorize"):
        """Prepare a request for the caller's registered application."""
        route = urlsplit(redirect_uri)
        if (not client_id or not isinstance(client_id, str) or not route.hostname
                or route.username or route.password or route.fragment or route.query
                or not (route.scheme == "https" or route.scheme == "http"
                        and route.hostname in {"127.0.0.1", "::1"})):
            raise ValueError("Use a registered HTTPS or loopback callback and a client ID")
        if authorization_endpoint not in {ACCOUNTS_ORIGIN + "/authorize",
                                         ACCOUNTS_ORIGIN + "/oauth2/v2/auth"}:
            raise ValueError("Use a Spotify Accounts authorization endpoint")
        selected = tuple(scopes)
        if any(not isinstance(scope, str) or not scope or any(c.isspace() for c in scope)
               for scope in selected):
            raise ValueError("Supply individual OAuth scope names")
        return cls(secrets.token_urlsafe(64), secrets.token_urlsafe(32), redirect_uri,
                   client_id, selected, authorization_endpoint)

    @property
    def authorize_url(self):
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(self.verifier.encode()).digest()).decode().rstrip("=")
        return self.authorization_endpoint + "?" + urlencode({
            "response_type": "code", "client_id": self.client_id,
            "scope": " ".join(self.scopes), "redirect_uri": self.redirect_uri,
            "code_challenge": challenge, "code_challenge_method": "S256", "state": self.state,
        })

    def callback_code(self, url):
        """Check the exact callback destination and state before returning its code."""
        actual, expected = urlsplit(url), urlsplit(self.redirect_uri)
        if ((actual.scheme, actual.netloc, actual.path or "/") !=
                (expected.scheme, expected.netloc, expected.path or "/") or actual.fragment):
            raise ValueError("Callback left the registered recipient")
        query = parse_qs(actual.query)
        state, code = query.get("state", []), query.get("code", [])
        if len(state) != 1 or not hmac.compare_digest(state[0], self.state):
            raise ValueError("Spotify callback state changed")
        if query.get("error") or len(code) != 1 or not code[0]:
            raise ValueError("Spotify did not return one successful authorization code")
        return code[0]


@dataclass(frozen=True)
class Session:
    """Token pair with an absolute Unix expiry. Token values are hidden in repr."""

    access_token: str = field(repr=False)
    expires_at: float
    client_id: str = ""
    scope: str = ""
    refresh_token: str | None = field(default=None, repr=False)
    id_token: str | None = field(default=None, repr=False)

    @classmethod
    def from_response(cls, data, *, client_id="", prior=None):
        if (not isinstance(data, dict) or not isinstance(data.get("access_token"), str)
                or not data["access_token"] or str(data.get("token_type", "")).lower() != "bearer"
                or isinstance(data.get("expires_in"), bool)
                or not isinstance(data.get("expires_in"), (int, float))
                or not math.isfinite(data["expires_in"]) or data["expires_in"] <= 0):
            raise ValueError("Malformed Spotify token response")
        refresh = data.get("refresh_token", prior.refresh_token if prior else None)
        if refresh is not None and (not isinstance(refresh, str) or not refresh):
            raise ValueError("Invalid Spotify refresh credential")
        return cls(data["access_token"], time.time() + data["expires_in"], client_id,
                   data.get("scope", prior.scope if prior else ""), refresh, data.get("id_token"))

    def bearer(self):
        if time.time() >= self.expires_at:
            raise ValueError("The Spotify session expired; renew it before another request")
        return {"Authorization": "Bearer " + self.access_token}


class AuthClient:
    """OAuth operations with caller-owned admission and secure persistence."""

    def __init__(self, transport=None, *, expected_email=None):
        self.transport = transport or HttpTransport()
        self.expected_email = expected_email

    def login_with_browser(self, browser, attempt, *, before_dispatch,
                           on_authenticated=None, timeout=300):
        """One explicit PKCE login; close only its owned tab before returning.

        The application must first reuse/refresh its existing session. This
        method never reads browser cookies or chooses a browser profile.
        Persist the returned pair through ``on_authenticated`` before cleanup,
        and release it for API use only after this method returns successfully.
        """
        if type(timeout) not in (int, float) or not 0 < timeout <= 1800:
            raise ValueError("Authentication timeout must be between 0 and 1800 seconds")
        tab = browser.open(attempt.authorize_url)
        try:
            callback = tab.wait_for_callback(attempt.redirect_uri, timeout=timeout)
            session = self.exchange(attempt, callback, before_dispatch=before_dispatch)
            if on_authenticated is not None:
                on_authenticated(session)
            self.verify(session)
            return session
        finally:
            tab.close()

    def exchange(self, attempt, callback_url, *, before_dispatch):
        code = attempt.callback_code(callback_url)
        before_dispatch({"kind": "spotify_pkce_exchange", "client_id": attempt.client_id})
        result = self.transport.execute("POST", ACCOUNTS_ORIGIN + "/api/token", form={
            "grant_type": "authorization_code", "client_id": attempt.client_id, "code": code,
            "redirect_uri": attempt.redirect_uri, "code_verifier": attempt.verifier}, mutation=True)
        return Session.from_response(require_success(result), client_id=attempt.client_id)

    def renew(self, session, *, before_dispatch):
        if not session.refresh_token or not session.client_id:
            raise ValueError("Refreshing requires the session's client ID and refresh credential")
        before_dispatch({"kind": "spotify_refresh", "client_id": session.client_id})
        result = self.transport.execute("POST", ACCOUNTS_ORIGIN + "/api/token", form={
            "grant_type": "refresh_token", "client_id": session.client_id,
            "refresh_token": session.refresh_token}, mutation=True)
        return Session.from_response(require_success(result), client_id=session.client_id, prior=session)

    def verify(self, session):
        profile = require_success(self.transport.execute(
            "GET", "https://api.spotify.com/v1/me", headers=session.bearer()))
        if not isinstance(profile, dict) or not (profile.get("id") or profile.get("email")):
            raise ValueError("Spotify did not return an authenticated account identity")
        if (self.expected_email is not None and
                profile.get("email", "").casefold() != self.expected_email.casefold()):
            raise ValueError("Spotify API account does not match the expected account")
        return profile
