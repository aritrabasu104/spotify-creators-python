import unittest
from unittest.mock import Mock
from spotify_creators.auth import AuthClient, OAuthAttempt, Session


class BrowserLoginTests(unittest.TestCase):
    def test_exact_pkce_and_owned_tab_closes_before_return(self):
        attempt = OAuthAttempt.prepare(client_id='test-client', redirect_uri='https://example.test/callback')
        browser = Mock()
        browser.open.return_value.wait_for_callback.return_value = 'private-callback'
        client = AuthClient(expected_email='owner@example.test')
        session = Session('synthetic', 9999999999)
        client.exchange = Mock(return_value=session)
        client.verify = Mock()
        capture, reserve = Mock(), Mock()
        self.assertIs(client.login_with_browser(browser, attempt, before_dispatch=reserve,
                                                on_authenticated=capture), session)
        client.exchange.assert_called_once_with(attempt, 'private-callback', before_dispatch=reserve)
        client.verify.assert_called_once_with(session)
        capture.assert_called_once_with(session)
        browser.open.return_value.close.assert_called_once()

    def test_failure_closes_only_the_owned_login_tab(self):
        attempt = OAuthAttempt.prepare(client_id='test-client', redirect_uri='https://example.test/callback')
        browser = Mock()
        browser.open.return_value.wait_for_callback.side_effect = TimeoutError()
        client = AuthClient()
        client.exchange = Mock()
        with self.assertRaises(TimeoutError):
            client.login_with_browser(browser, attempt, before_dispatch=Mock())
        client.exchange.assert_not_called()
        browser.open.return_value.close.assert_called_once()

    def test_cleanup_failure_preserves_captured_pair_and_cannot_report_ready(self):
        attempt = OAuthAttempt.prepare(client_id='test-client', redirect_uri='https://example.test/callback')
        browser = Mock()
        browser.open.return_value.close.side_effect = RuntimeError('cleanup pending')
        client = AuthClient()
        client.exchange = Mock(return_value=Session('synthetic', 9999999999))
        client.verify = Mock()
        capture = Mock()
        with self.assertRaisesRegex(RuntimeError, 'cleanup pending'):
            client.login_with_browser(browser, attempt, before_dispatch=Mock(), on_authenticated=capture)
        capture.assert_called_once()
