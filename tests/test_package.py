"""Portable import, configuration, public document and convenience-API tests."""

import contextlib
import io
import json
import time
import unittest

from spotify_creators import Client, OAuthAttempt, Session
from spotify_creators.cli import main
from spotify_creators.http import Response
from spotify_creators.protocol import web_episode_id
from spotify_creators.public import feed_catalogue


class Transport:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = []

    def execute(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return Response(200, next(self.replies))


class PackageTests(unittest.TestCase):
    def test_import_facade_resolves_episode_before_one_reserved_update(self):
        replies = [{"id": "example-account", "email": "member@example.test"},
                   {"episodeId": 1}, {"webEpisodeId": web_episode_id(1), "userId": 2}, {}]
        transport = Transport(replies)
        client = Client(Session("synthetic", time.time() + 600),
                        expected_email="member@example.test", transport=transport)
        client.verify_account()
        reserved = []
        client.update_episode("a" * 22, {"title": "Example"}, before_dispatch=reserved.append)
        self.assertEqual(len(reserved), 1)
        self.assertEqual(transport.calls[-1][1]["body"], {"userId": 2, "title": "Example"})
        self.assertEqual(len(transport.calls), 4)

    def test_pkce_has_explicit_caller_configuration_and_exact_callback_path(self):
        with self.assertRaises(TypeError):
            OAuthAttempt.prepare()
        for callback in ("http://example.test/callback", "https://user:pass@example.test/callback",
                         "https://example.test/callback#fragment"):
            with self.assertRaises(ValueError):
                OAuthAttempt.prepare(client_id="example-client", redirect_uri=callback)
        attempt = OAuthAttempt.prepare(client_id="example-client", redirect_uri="http://127.0.0.1:8765/callback")
        wrong = "http://127.0.0.1:8765/callback/?code=example&state=" + attempt.state
        with self.assertRaises(ValueError):
            attempt.callback_code(wrong)

    def test_public_feed_parser_is_independent_and_rejects_entities_and_duplicates(self):
        item = ('<item><guid>example-guid</guid><title>Example</title>'
                '<enclosure url="https://example.test/episode.mp3" length="42" type="audio/mpeg"/>'
                '</item>')
        feed = ('<rss><channel><title>Example show</title><language>en</language>' + item + '</channel></rss>').encode()
        result = feed_catalogue(feed)
        self.assertEqual(result["episodes"][0]["guid"], "example-guid")
        with self.assertRaises(ValueError):
            feed_catalogue(feed.replace(b'</channel>', item.encode() + b'</channel>'))
        with self.assertRaises(ValueError):
            feed_catalogue(b'<!DOCTYPE rss [<!ENTITY x "value">]><rss/>')
        empty = b'<rss><channel><title>Example</title></channel></rss>'
        self.assertEqual(feed_catalogue(empty, require_episodes=False)["episodes"], [])

    def test_cli_lists_contracts_without_credentials(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(["list-apis"]), 0)
        result = json.loads(output.getvalue())
        self.assertEqual(len(result["rest"]), 51)
        self.assertEqual(len(result["graphql"]), 37)


if __name__ == "__main__":
    unittest.main()
