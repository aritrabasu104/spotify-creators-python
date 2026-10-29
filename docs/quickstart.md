---
layout: default
title: Quick start
---

# Quick start

## Install and import

Use Python 3.11 or newer and Git:

```sh
python -m pip install "spotify-creators-client @ git+https://github.com/aritrabasu104/spotify-creators-python.git@v0.1.0"
python -m spotify_creators --version
```

```python
import os
from spotify_creators import Client, Session

session = Session(
    access_token=os.environ["SPOTIFY_ACCESS_TOKEN"],
    expires_at=float(os.environ["SPOTIFY_TOKEN_EXPIRES_AT"]),
)
client = Client(session, expected_email=os.environ["SPOTIFY_ACCOUNT_EMAIL"])
profile = client.verify_account()
```

`expires_at` is the real absolute Unix expiry of the token. Use
`Session.from_response(token_response, client_id=client_id)` when you have a
fresh OAuth response containing `expires_in`. Session representations hide
token values; explicitly serializing them is your application's responsibility.

## Read account-owned objects

```python
shows = client.all_shows()["showsForUser"]["shows"]
show_id = shows[0]["uri"].split(":")[-1]
metadata = client.get_show(show_id)
catalogue = client.list_episodes(show_id)
for item in catalogue["items"]:
    print(item["uri"], item["title"])
```

`list_episodes` validates a completed index, page totals and unique identities.
An incomplete index raises an exception rather than presenting partial results
as a complete catalogue. `client.tasks.episodes(...)` provides one bounded page
when complete reconciliation is not needed.

```python
episode = client.get_episode(os.environ["SPOTIFY_EPISODE_ID"])
```

These convenience methods accept Spotify base62 IDs. Detailed task methods use
the identifiers named by their signatures: `legacy_show` and `resolve_episode`
provide the corresponding legacy identifiers. The `spotify_creators.protocol`
module contains explicit ID conversion functions.

## Configure transport and session renewal

```python
from spotify_creators import HttpTransport

client = Client(
    session,
    expected_email=expected_email,
    transport=HttpTransport(timeout=30, max_response=4 * 1024 * 1024),
    session_provider=your_session_provider,
)
```

`session_provider(current_session)` runs before authenticated requests. It must
return a valid `Session`, using your secure store and refresh serialization if
renewal is necessary. See [Authentication](authentication) for the contract.

The transport accepts only the package's Spotify API origins, rejects redirects
and has no implicit retries. No local application, browser extension or operating
system credential backend is required by the library.
