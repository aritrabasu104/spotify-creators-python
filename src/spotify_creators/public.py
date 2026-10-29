"""Bounded, credential-free reads of public Spotify episode pages and RSS."""

from hashlib import sha256
from html.parser import HTMLParser
import re
from urllib.parse import urlsplit
from urllib.request import Request, ProxyHandler, build_opener
from xml.etree import ElementTree as ET

from .http import NoRedirect


def _public_get(url, *, maximum, opener=None):
    route = urlsplit(url)
    if (route.scheme != "https" or route.username or route.password or route.port not in {None, 443}
            or route.query or route.fragment or not (
                route.hostname == "anchor.fm" and re.fullmatch(r"/s/[0-9a-f]+/podcast/rss", route.path)
                or route.hostname == "open.spotify.com" and
                re.fullmatch(r"/episode/[A-Za-z0-9]{22}", route.path))):
        raise ValueError("Use an exact public Spotify episode or hosted RSS URL")
    request = Request(url, headers={"User-Agent": "spotify-creators-client/0.1.0",
                                    "Accept-Encoding": "identity"})
    with (opener or build_opener(ProxyHandler({}), NoRedirect())).open(request, timeout=30) as response:
        if response.code != 200:
            raise ValueError("The public Spotify document is unavailable")
        body = response.read(maximum + 1)
        if len(body) > maximum:
            raise ValueError("Public Spotify document exceeded its size limit")
        return body


def feed_catalogue(raw, *, require_episodes=True):
    """Parse a bounded RSS catalogue; reject entities and ambiguous identities."""
    if len(raw) > 2 * 1024 * 1024 or b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("Unsupported RSS document")
    try:
        channel = ET.fromstring(raw).find("channel")
        if channel is None:
            raise ValueError("Missing channel")
        rows = []
        for item in channel.findall("item"):
            enclosure = item.find("enclosure")
            guid = (item.findtext("guid") or "").strip()
            if enclosure is None or not guid or int(enclosure.get("length", "0")) <= 0:
                raise ValueError("Missing episode or enclosure identity")
            route = urlsplit(enclosure.get("url", ""))
            if route.scheme != "https" or not route.hostname or route.username or route.password:
                raise ValueError("Non-public enclosure route")
            rows.append({"guid": guid, "title": (item.findtext("title") or "").strip(),
                         "enclosure_url": enclosure.get("url"), "enclosure_length": enclosure.get("length"),
                         "enclosure_type": enclosure.get("type")})
        if (require_episodes and not rows) or len({row["guid"] for row in rows}) != len(rows):
            raise ValueError("Empty or duplicate episode identities")
    except (ET.ParseError, TypeError) as exc:
        raise ValueError("RSS document is not a complete catalogue") from exc
    return {"title": (channel.findtext("title") or "").strip(),
            "language": (channel.findtext("language") or "").strip(), "episodes": rows}


def read_feed(url, *, opener=None, require_episodes=True):
    raw = _public_get(url, maximum=2 * 1024 * 1024, opener=opener)
    return {"source_sha256": sha256(raw).hexdigest(),
            "catalogue": feed_catalogue(raw, require_episodes=require_episodes)}


class Metadata(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.values = {}

    def handle_starttag(self, tag, attributes):
        if tag == "meta":
            values = dict(attributes)
            key = values.get("property") or values.get("name")
            if key and "content" in values:
                self.values[key] = values["content"]


def read_public_episode(episode_id, *, opener=None):
    if not re.fullmatch(r"[A-Za-z0-9]{22}", episode_id):
        raise ValueError("Spotify episode ID required")
    url = "https://open.spotify.com/episode/" + episode_id
    raw = _public_get(url, maximum=2 * 1024 * 1024, opener=opener)
    parser = Metadata()
    parser.feed(raw.decode("utf-8"))
    if parser.values.get("og:url") != url or not parser.values.get("og:title"):
        raise ValueError("Public metadata did not identify the requested episode")
    return {"source_sha256": sha256(raw).hexdigest(), "episode_id": episode_id,
            "metadata": parser.values}
