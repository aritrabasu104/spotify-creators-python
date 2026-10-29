"""Data-only request construction recovered from Spotify's public frontend.

Preparing a request does not send it. Callers verify account access and reserve
side effects before dispatch.
"""

from dataclasses import dataclass, field
import re
from typing import Any
from urllib.parse import urlencode

REST_ORIGIN = "https://api-v5.anchor.fm"
GRAPH_URL = "https://creators-graph.spotify.com/v2/graph-pq"
ACCOUNTS_ORIGIN = "https://accounts.spotify.com"
CREATORS_SCOPES = ("streaming", "ugc-image-upload", "user-read-email",
                   "user-read-private", "profile", "openid")


def web_station_id(station_id: int) -> str:
    if isinstance(station_id, bool) or not isinstance(station_id, int) or station_id < 0:
        raise ValueError("Expected the original decimal station ID")
    return format((station_id + 100000) * 100, "x")


def web_episode_id(episode_id: int) -> str:
    if isinstance(episode_id, bool) or not isinstance(episode_id, int) or episode_id < 0:
        raise ValueError("Expected the original decimal episode ID")
    value, encoded = episode_id + 1000000, ""
    while value:
        value, digit = divmod(value, 32)
        encoded = "0123456789abcdefghijklmnopqrstuv"[digit] + encoded
    return "e" + encoded


def legacy_station_id(web_station_id: str) -> int:
    if not re.fullmatch(r"[0-9a-f]+", web_station_id):
        raise ValueError("Expected the native hexadecimal web station ID")
    raw = int(web_station_id, 16)
    if raw % 100 or raw // 100 < 100000:
        raise ValueError("Invalid web station ID representation")
    return raw // 100 - 100000


def legacy_episode_id(web_episode_id: str) -> int:
    if not re.fullmatch(r"e[0-9a-v]+", web_episode_id):
        raise ValueError("Expected the native e-prefixed base32 web episode ID")
    value = int(web_episode_id[1:], 32) - 1000000
    if value < 0:
        raise ValueError("Invalid web episode ID representation")
    return value


def legacy_audio_id(web_audio_id: str) -> int:
    if not re.fullmatch(r"[a-z][0-9a-v]+", web_audio_id):
        raise ValueError("Expected the native prefixed base32 audio ID")
    value = int(web_audio_id[1:], 32) - 1000000
    if value < 0:
        raise ValueError("Invalid native audio identity")
    return value


def _nested_native_ids(value, depth=1):
    if depth > 2:
        return value
    if isinstance(value, list):
        return [_nested_native_ids(v, depth + 1) for v in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key == "webAudioId":
            result["audioId"] = legacy_audio_id(item)
        elif key in {"webEpisodeId", "webStationId", "webAdCampaignId"}:
            result[key] = item
        else:
            result[key] = _nested_native_ids(item, depth + 1)
    return result


def rest_payload(value):
    """Convert top-level and supported nested legacy REST identifiers."""
    if not isinstance(value, dict):
        raise ValueError("The native REST payload must be an object")
    result = {}
    decoders = {"webEpisodeId": ("episodeId", legacy_episode_id),
                "webStationId": ("stationId", legacy_station_id),
                "webAudioId": ("audioId", legacy_audio_id)}
    for key, item in value.items():
        if key in decoders:
            name, decode = decoders[key]
            result[name] = decode(item)
        else:
            result[key] = _nested_native_ids(item)
    return result


def rest_query(value):
    def scalar(item):
        if item is True:
            return "true"
        if item is False:
            return "false"
        if item is None:
            return "null"
        if isinstance(item, (str, int, float)):
            return str(item)
        raise ValueError("Native query values must have explicit scalar semantics")
    return urlencode({key: scalar(item) for key, item in rest_payload(value).items()})


def rest_path(path: str) -> str:
    """Match frontend module 84104's path alias conversion, including slashes.

    Spotify base62 show/episode IDs are separate. Never feed them to this legacy
    encoding or guess identity from a display title.
    """
    if not path.startswith("/v3/") or any(c in path for c in "?#{}\\\r\n"):
        raise ValueError("Expected one concrete recovered v3 path without a query")
    for name, decoder in (("webStationId", legacy_station_id), ("webEpisodeId", legacy_episode_id)):
        path = re.sub(r"/" + name + r":([^/]+)/?",
                      lambda m: f"/{decoder(m[1])}/", path)
    return path


@dataclass(frozen=True)
class PreparedRequest:
    method: str
    url: str
    body: dict[str, Any] = field(repr=False)
    headers: dict[str, str] = field(repr=False)
    verification: str = "source_derived_not_dispatched"


def persisted_query(operation: dict, variables: dict, *, creator_client: str) -> PreparedRequest:
    name, digest = operation.get("name"), operation.get("sha256")
    if (not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_]\w*", name)
            or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or operation.get("kind") not in {"query", "mutation"}):
        raise ValueError("An exact recovered operation name/hash/kind is required")
    if not isinstance(variables, dict):
        raise ValueError("Explicit original variables are required")
    if "variables" in operation:
        declared = operation["variables"]
        if set(variables) - set(declared):
            raise ValueError("Undeclared Spotify GraphQL variables")
        for key, kind in declared.items():
            if kind.endswith("!") and key not in operation.get("defaulted_variables", []):
                if key not in variables or variables[key] is None:
                    raise ValueError("Missing required Spotify GraphQL variable: " + key)
            value = variables.get(key)
            if value is not None:
                base = kind.rstrip("!")
                if base == "Boolean" and not isinstance(value, bool):
                    raise ValueError("Expected a genuine GraphQL Boolean: " + key)
                if base == "Int" and (isinstance(value, bool) or not isinstance(value, int)):
                    raise ValueError("Expected a genuine GraphQL integer: " + key)
    if (creator_client not in {"public-website", "microfrontend-merch-tools",
                               "microfrontend-dynamic-home", "podcasters-shell-app"}
            or operation.get("creator_clients") and creator_client not in operation["creator_clients"]):
        raise ValueError("Select the original operation's recovered creator client")
    return PreparedRequest("POST", GRAPH_URL, {
        "operationName": name, "variables": variables,
        "extensions": {"persistedQuery": {"version": 1, "sha256Hash": digest}},
    }, {"Content-Type": "application/json", "x-creator-client": creator_client})
