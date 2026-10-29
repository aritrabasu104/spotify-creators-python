---
layout: default
title: Writes and transfers
---

# Writes and transfers

## Reserve before sending

Verify the authenticated account with `client.verify_account()`. Every mutation
and upload-signing request requires `before_dispatch(intent)`. If it raises, no
HTTP request is sent. The intent includes operation identifiers and a request
digest, without bearer tokens or issued URL values.

```python
client.update_episode(
    episode_id,
    {"title": "Updated title"},
    before_dispatch=reserve_once,
)
saved = client.get_episode(episode_id)
assert saved["title"] == "Updated title"
```

See the complete [SQLite reservation example](https://github.com/aritrabasu104/spotify-creators-python/blob/main/examples/guarded_update.py).
The library does not create a database or choose an application's retry policy.

## Scheduling and metadata

```python
client.update_episode(
    episode_id,
    {"isPublished": True, "publishOn": approved_release_time,
     "episodeType": "full", "title": approved_title, "description": approved_description},
    before_dispatch=reserve_once,
)
```

`approved_release_time` must include its timezone. Release fields are serialized
as JavaScript-compatible UTC timestamps with milliseconds. Verify the saved
episode and its original release instant after a write. `episodeType` supports
the server's full/trailer values. A draft update does not itself verify a public
publication, and a successful HTTP response alone is not a delivery readback.

## Media and artwork

`client.tasks` exposes separate signing, processing and status operations.
Signing can allocate server state, even when its HTTP method is GET.

```python
from spotify_creators import UploadTarget, upload_exact

# artifact contains an absolute path, frozen byte length and SHA-256 digest.
# target comes from the specific authorized signing response.
result = upload_exact(
    UploadTarget(issued_url, "PUT", {"Content-Type": content_type}),
    artifact,
    before_dispatch=reserve_transfer,
)
```

Only the returned method, headers and target are used. Account bearer tokens and
cookies cannot be forwarded to storage. Exact bytes and source-file identity
are checked before and during transfer. `upload_multipart` supports sequential
parts, per-part receipt callbacks and resumption from acknowledged original
ranges. It never silently retries an uncertain part.

Show covers, episode covers and thumbnails use distinct methods. Thumbnail
completion and media processing must be followed by their actual status reads.
The alternate Creators Upload Service has its own status path; do not append
legacy finalization calls to it. Transcript-upload methods are separate from
episode media uploads.

## Failure handling

- `ProviderError`: HTTP failure; `status`, `code` and numeric `retry_after`
  expose safe summary fields. A 429 response is not automatically retried.
- `GraphError`: GraphQL application errors, even when HTTP returned 200.
- `OutcomeUnknown`: a mutation or transfer may have been accepted; reconcile
  its original identifier and intent before any replacement or retry.
- `ValueError`: invalid input, identity mismatch or incomplete reconciliation.

Responses and exception detail objects can contain private provider data. Do not
log token-bearing request headers or unfiltered provider responses. There is no
automatic endpoint fallback, object deletion, publication replay or retry loop.
