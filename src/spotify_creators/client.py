"""Standalone Creators client. Callers admit every side effect once."""

import hashlib
import json
import re
from urllib.parse import quote

from .auth import AuthClient
from .http import require_success
from .endpoints import ENDPOINTS
from .protocol import REST_ORIGIN, persisted_query, rest_path, rest_payload, rest_query


class GraphError(RuntimeError):
    def __init__(self, codes, data=None, errors=None):
        self.codes, self.partial_data, self.errors = tuple(codes), data, errors
        super().__init__("Spotify GraphQL returned application errors: " + ", ".join(sorted(set(codes))))


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, allow_nan=False,
                                     sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class SpotifyClient:
    def __init__(self, transport, session, inventory, *, expected_email, session_provider=None):
        self.transport, self.session, self.inventory = transport, session, inventory
        self.auth = AuthClient(transport, expected_email=expected_email)
        self._verified = False
        self.session_provider = session_provider

    def _ensure_session(self):
        if self.session_provider is not None:
            self.session = self.session_provider(self.session)

    def verify_account(self):
        self._ensure_session()
        profile = self.auth.verify(self.session)
        self._verified = True
        return profile

    def _admit(self, intent, callback):
        if not self._verified:
            raise ValueError("Verify the actual original Spotify account before any mutation")
        if not callable(callback):
            raise ValueError("The caller must reserve this exact side effect")
        callback(intent)

    def rest(self, identity, *values, query=None, body=None, before_dispatch=None):
        specs = [row for row in ENDPOINTS if row[0] == identity and not identity.startswith("auth.")]
        if len(specs) != 1:
            raise ValueError("Select one recovered Creators REST operation")
        _, method, template, _, _ = specs[0]
        if template.count("{value}") != len(values):
            raise ValueError("Supply each original path identity in its actual source order")
        parts = iter(values)
        def segment(_):
            value = next(parts)
            if not isinstance(value, (str, int)) or any(c in str(value) for c in "/?#\\\r\n"):
                raise ValueError("Unsafe original Spotify path identity")
            return quote(str(value), safe=":")
        path = re.sub(r"\{value\}", segment, template)
        path, _, retained_query = path.partition("?")
        path = rest_path(path)
        url = REST_ORIGIN + path
        encoded = rest_query(query) if query is not None else ""
        combined = "&".join(part for part in (retained_query, encoded) if part)
        if combined:
            url += "?" + combined
        payload = rest_payload(body) if body is not None else None
        self._ensure_session()
        authorization = self.session.bearer()
        mutation = method not in {"GET", "HEAD"} or ".sign" in identity
        if mutation:
            self._admit({"operation": identity, "method": method, "request_sha256": fingerprint({
                "url": url, "body": payload})}, before_dispatch)
        response = self.transport.execute(method, url, body=payload,
                                         headers={**authorization, "Anchor-API-Version": "3.8.3",
                                                  "Anchor-Client-Type": "web"}, mutation=mutation)
        return require_success(response)

    def graphql(self, name, variables, *, creator_client, operation_hash=None, before_dispatch=None):
        rows = [row for row in self.inventory["graphql_operations"] if row["name"] == name
                and creator_client in row["creator_clients"]
                and (operation_hash is None or row["sha256"] == operation_hash)]
        if len(rows) != 1:
            raise ValueError("Select the exact recovered GraphQL operation version and client")
        row = rows[0]
        request = persisted_query(row, variables, creator_client=creator_client)
        self._ensure_session()
        authorization = self.session.bearer()
        mutation = row["kind"] == "mutation"
        if mutation:
            self._admit({"operation": name, "method": "POST", "request_sha256": fingerprint(request.body),
                         "operation_hash": row["sha256"], "creator_client": creator_client}, before_dispatch)
        response = self.transport.execute(request.method, request.url, body=request.body,
                                         headers={**request.headers, **authorization}, mutation=mutation)
        value = require_success(response)
        if not isinstance(value, dict):
            raise ValueError("Spotify GraphQL returned a malformed response")
        if value.get("errors"):
            codes = []
            for error in value["errors"]:
                code = (error.get("extensions") or {}).get("code", "application_error")
                codes.append(code if isinstance(code, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,96}", code)
                             else "application_error")
            raise GraphError(codes, value.get("data"), value['errors'])
        return value.get("data")

    def all_shows(self):
        return self.graphql("getShowsForUser", {}, creator_client="microfrontend-dynamic-home")

    def show_context(self, show_id):
        if not re.fullmatch(r"[A-Za-z0-9]{22}", show_id):
            raise ValueError("Original Spotify show ID required")
        return self.graphql("WebGetUserAndCurrentShow", {"showUri": "spotify:show:" + show_id},
                            creator_client="podcasters-shell-app")
