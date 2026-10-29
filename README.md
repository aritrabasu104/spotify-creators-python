# Spotify Creators Client for Python

[Documentation](https://aritrabasu104.github.io/spotify-creators-python/) ·
[Quick start](docs/quickstart.md) · [Authentication](docs/authentication.md) ·
[API reference](docs/reference.md) · [Concurrency](docs/concurrency.md) · [Examples](examples/)

A small, independent Python client for Spotify Creators: account verification,
shows, episodes, publishing and scheduling, media transfers, artwork, clips and
hosted RSS settings. Python 3.11+, with **no third-party runtime dependencies**.

This is an **unofficial client** for Creators endpoints, including undocumented
interfaces. It is not affiliated with Spotify. Creators access depends on your
account and application permissions; ordinary Web API access does not guarantee
access to these interfaces. Endpoint compatibility may change.

## Install

```sh
python -m pip install "spotify-creators-client @ git+https://github.com/aritrabasu104/spotify-creators-python.git@v0.2.0"
```

This installs from GitHub. The project is not currently published on PyPI.

## Import and read

Supply a token obtained through an authorized application. Environment variables
below are supplied by your own shell or secret manager; no credentials are
included with the package.

```python
import os
from spotify_creators import Client, Session

session = Session(
    access_token=os.environ["SPOTIFY_ACCESS_TOKEN"],
    expires_at=float(os.environ["SPOTIFY_TOKEN_EXPIRES_AT"]),
)
client = Client(session, expected_email=os.environ["SPOTIFY_ACCOUNT_EMAIL"])
profile = client.verify_account()

for show in client.all_shows()["showsForUser"]["shows"]:
    print(show["uri"], show["name"])

# When you already have an episode ID:
# episode = client.get_episode(os.environ["SPOTIFY_EPISODE_ID"])
```

`expires_at` is the token's actual Unix expiry, not an assumed lifetime.
See the [OAuth guide](docs/authentication.md) for PKCE and refresh.

## Make a change

Writes and upload signing require an authenticated account check and a
`before_dispatch` callback. The callback receives a credential-free intent
containing the operation and request digest. Use it to reserve that exact write
in your application before HTTP begins.

```python
def reserve(intent):
    operation_store.reserve_once(intent)  # Your application's durable store.

client.update_episode(
    episode_id,
    {"title": "Updated episode title"},
    before_dispatch=reserve,
)
saved = client.get_episode(episode_id)
assert saved["title"] == "Updated episode title"
```

The complete [SQLite example](examples/guarded_update.py) implements a reservation
callback. The package itself creates no credential files, database or worker.
It does not silently retry writes, follow redirects, or forward account
credentials to issued upload URLs.

## What's included

Independent uploads run **10 at a time by default** through
`client.run_uploads(operation, items)`. `SessionManager` reuses a valid session
and serializes login/refresh independently of transfers. See the
[concurrency guide](docs/concurrency.md) for examples and cross-process ownership.

| Area | Entry points |
| --- | --- |
| Authentication | `OAuthAttempt`, `AuthClient`, `Session` |
| Convenient reads | `Client.all_shows`, `get_show`, `get_episode`, `list_episodes` |
| Episode editing | `Client.update_episode`, `client.tasks.update_episode` |
| Detailed operations | `client.tasks`: show setup, drafts, schedules, media processing, artwork, clips and RSS |
| Low-level access | `client.rest`, `client.graphql`, bundled route/query contracts |
| Exact byte transfers | `UploadTarget`, `upload_exact`, `upload_multipart` |
| Public metadata | `spotify_creators.public.read_feed`, `read_public_episode` |
| Discovery | `python -m spotify_creators list-apis` |

The [reference](docs/reference.md) lists all task methods and 51 REST/auth route
contracts plus 37 persisted GraphQL versions. Authentication discovery routes
are documented separately from callable OAuth helpers.

## Develop

```sh
git clone https://github.com/aritrabasu104/spotify-creators-python.git
cd spotify-creators-python
python -m venv .venv
# Activate the environment for your shell, then:
python -m pip install -e ".[dev]"
python -m unittest discover -s tests -v
python -m build
python -m twine check dist/*
```

Tests use synthetic sessions and mocked HTTP. They do not require a Spotify
account and do not make live account changes. [MIT license](LICENSE).
