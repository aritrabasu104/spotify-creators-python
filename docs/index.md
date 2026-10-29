---
layout: default
title: Documentation
---

# Spotify Creators Client

An independent Python library for authorized Spotify Creators accounts.
Install it from GitHub and import `Client` from `spotify_creators`.

```sh
python -m pip install "spotify-creators-client @ git+https://github.com/aritrabasu104/spotify-creators-python.git@v0.2.1"
```

```python
from spotify_creators import Client, Session
```

## Guides

- [Quick start](quickstart): installation, account verification and reads.
- [Authentication](authentication): configurable PKCE, session storage and refresh.
- [Writes and transfers](writes): reservation callbacks, failure handling and uploads.
- [Concurrent uploads and sessions](concurrency): ten parallel operations and one login/refresh owner.
- [API reference](reference): Python methods, named REST routes and persisted queries.
- [Runnable examples](https://github.com/aritrabasu104/spotify-creators-python/tree/main/examples).

Python 3.11+; no third-party runtime dependencies. This unofficial client is not
affiliated with Spotify. Creators endpoints may require additional account and
application access and can change independently of the documented Web API.

[Source and issues](https://github.com/aritrabasu104/spotify-creators-python)
· [License](https://github.com/aritrabasu104/spotify-creators-python/blob/main/LICENSE)
