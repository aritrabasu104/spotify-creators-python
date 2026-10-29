---
layout: default
title: Concurrent uploads and sessions
---

# Concurrent uploads and sessions

`Client.run_uploads` and `UploadPool` run **10 independent operations in parallel
by default**. They join all started work before returning, preserve input order
and return one `UploadResult` per input. Completed siblings remain available when
one operation fails. There is no automatic mutation or transfer retry.

```python
from spotify_creators import Client, SessionManager

# These callbacks belong to your application and its secure credential owner.
# refresh_and_save must lock, re-read and durably save any rotated token pair.
sessions = SessionManager(
    load=secure_store.load,
    refresh=refresh_and_save,
    login=initial_sign_in_and_save,
)
client = Client(sessions(), session_provider=sessions, expected_email=expected_email)
client.verify_account()

def upload_one(item):
    # Each item retains its own allocation, issued URLs and admission callbacks.
    return upload_authorized_media(client, item)

results = client.run_uploads(upload_one, independent_uploads)
for result in results:
    if result.error is None:
        retain_completed_transfer(result.value)
    else:
        retain_original_failure(result.index, result.error)
```

`upload_authorized_media` represents your existing signing/transfer/processing
sequence; use the methods in the [API reference](reference.md). You can also use
`UploadPool().run(upload_one, items)` independently of a client, or configure
`Client(..., max_parallel_uploads=4)`. Limits accept integers from 1 to 64.

A pool shares its limit across simultaneous `run` calls. The limit applies to
work dispatched through that pool; separate processes require an application
admission boundary. Do not nest batches on the same pool. Multipart ranges for
one upload stay sequential, so ten files do not become a hundred part transfers.
Custom transports and reservation callbacks must support concurrent callers.
The default HTTP transport uses independent openers for each thread.

## Authentication is separate from transfer work

`SessionManager` serializes initial sign-in, credential loading and renewal.
It returns the same valid session without another login or token request. Its
default 60-second refresh margin allows renewal before an in-flight request
could reach expiry; set `refresh_margin=0` to use the precise expiry instead.

Access-token renewal normally uses the refresh-token API and needs no browser.
Only initial authorization or a provider-required reauthentication needs the
application's sign-in flow. See Spotify's [refresh documentation](https://developer.spotify.com/documentation/web-api/tutorials/refreshing-tokens).

The manager re-reads the secure store at a renewal boundary to adopt a rotation
already completed by another owner. For multiple processes, the callbacks must
use the same external lock and re-read inside that lock before issuing a grant.
It retains a failed login/refresh outcome for every waiting caller; after
reconciliation, `replace(valid_session)` adopts the resolved session. It never
automatically replays a lost grant or starts a second sign-in after a failure.

Account verification after a changed session is serialized on a shared client;
ordinary API calls and transfers run concurrently. GET requests through that
client reuse the same session provider too.

Ten is a client concurrency ceiling, not a promise of provider throughput.
Respect Spotify's [rate limits and `Retry-After`](https://developer.spotify.com/documentation/web-api/concepts/rate-limits).
Retain original write intents and resolve uncertain acceptance before retrying.
