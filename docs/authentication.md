---
layout: default
title: Authentication
---

# Authentication

Use an authorized application and an account permitted to access Creators.
The library bundles no client credentials, account tokens or login sessions.
Supplying a standard Web API application alone may not grant Creators access.

## PKCE

```python
import os
from spotify_creators import AuthClient, OAuthAttempt

attempt = OAuthAttempt.prepare(
    client_id=os.environ["SPOTIFY_CLIENT_ID"],
    redirect_uri=os.environ["SPOTIFY_REDIRECT_URI"],
    scopes=("user-read-email", "user-read-private"),
)
authorization_url = attempt.authorize_url
# Direct the user to this URL through your application's login flow.
# Keep attempt private until the matching callback returns.
```

Use the exact redirect URI registered for your application. HTTPS and explicit
HTTP loopback addresses are supported. The state and code verifier are generated
randomly; callback destination and state are checked before code exchange.

```python
auth = AuthClient(expected_email=expected_email)
session = auth.exchange(
    attempt,
    actual_callback_url,
    before_dispatch=reserve_oauth_exchange,
)
profile = auth.verify(session)
secure_store.save(session)
```

`reserve_oauth_exchange` is your callable that records the exchange before it is
sent. Authorization codes are single use. A lost response requires reconciliation
of that exchange rather than an automatic replay. The package never opens a
browser, collects passwords, solves challenges or changes account security.

For an application explicitly registered for the Accounts SDK route, pass
`authorization_endpoint="https://accounts.spotify.com/oauth2/v2/auth"` to
`OAuthAttempt.prepare`. The default is the standard `/authorize` endpoint.

Spotify's [PKCE guide](https://developer.spotify.com/documentation/web-api/tutorials/code-pkce-flow)
describes the standard authorization mechanism. Creators endpoint compatibility
and application permissions are separate concerns.

## Refresh

```python
with secure_store.locked():
    current = secure_store.load()
    renewed = auth.renew(current, before_dispatch=reserve_refresh)
    secure_store.save(renewed)
    profile = auth.verify(renewed)
```

The session must contain the original client ID and refresh credential. If the
response omits a replacement refresh token, the existing one is retained. Save
any rotated pair before later work can fail. Serialize renewal through your
application's credential owner, and preserve an unresolved dispatched refresh.

`secure_store`, its lock and reservation callbacks above are application
interfaces, not storage implementations supplied by this package. Use your
platform's secure credential store. Do not commit tokens, authorization callbacks
or issued upload URLs to a repository.

A `Client` can receive `session_provider(current_session)` to load or renew a
session before each request. The callable should reuse this same locked refresh
flow and verify the expected account before returning a replacement session.
