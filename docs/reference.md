---
layout: default
title: API reference
---

# API reference

## Python surface

Import `Client`, `Session`, `OAuthAttempt`, `AuthClient`, `CreatorsTasks`,
`HttpTransport`, `UploadTarget`, transfer helpers and exception types from
`spotify_creators`. `Client` bundles the operation catalogue and exposes task
methods through `client.tasks`. `SpotifyClient` is the lower-level constructor
for callers supplying a transport and catalogue explicitly.

Convenience reads: `client.get_show(show_id)`, `get_episode(episode_id)`,
`list_episodes(show_id)` and `all_shows()`. `client.update_episode(...)` resolves
its Spotify ID before the caller-admitted write.

## Task methods

All methods below are available on `client.tasks`.
Parameters named `web_station_id` and `web_episode_id` use legacy web IDs.
Use `legacy_show`, `resolve_episode` and `spotify_creators.protocol` conversions.
Every `before_dispatch` argument is required for the corresponding side effect.

### `all_episodes`

```python
all_episodes(show_id, *, max_pages=500)
```

### `artwork_status`

```python
artwork_status(web_station_id, request_uuid, *, web_episode_id=None)
```

### `categories`

```python
categories(locale='en-US')
```

### `clip`

```python
clip(clip_uri)
```

### `clips`

```python
clips(value)
```

### `complete_thumbnail`

```python
complete_thumbnail(value, thumbnail_uuid, *, before_dispatch)
```

### `create_clip`

```python
create_clip(value, show_id, details, *, before_dispatch)
```

### `create_episode`

```python
create_episode(web_station_id, *, title, description, hour_offset, before_dispatch, metadata=None, audios=None)
```

### `create_show`

```python
create_show(metadata, *, before_dispatch, migrated)
```

### `delete_episode`

```python
delete_episode(web_episode_id, *, before_dispatch)
```

### `distribution`

```python
distribution(web_station_id)
```

### `episode`

```python
episode(web_episode_id)
```

### `episode_page`

```python
episode_page(web_station_id, *, limit=100, page_token=None, order_by='publishOn', search_title=None, published_only=False, subscriptions_filter=None)
```

### `episodes`

```python
episodes(show_id, *, page=1, page_size=50, filter_type=None, analytics_window='WINDOW_LAST_SEVEN_DAYS')
```

### `experimental_media_status`

```python
experimental_media_status(value, request_uuid)
```

### `generate_transcript_upload`

```python
generate_transcript_upload(value, *, before_dispatch)
```

### `legacy_show`

```python
legacy_show(show_id)
```

### `media_status`

```python
media_status(request_uuid)
```

### `metadata`

```python
metadata(web_station_id)
```

### `process_artwork`

```python
process_artwork(web_station_id, request_uuid, *, before_dispatch, web_episode_id=None)
```

### `process_media`

```python
process_media(request_uuid, *, user_id, web_station_id, web_episode_id, filename, video, before_dispatch, parts=None, upload_id=None)
```

### `publish_transcript_upload`

```python
publish_transcript_upload(value, upload_id, *, before_dispatch)
```

### `replace_clip`

```python
replace_clip(details, *, before_dispatch)
```

### `request_show_deletion`

```python
request_show_deletion(web_station_id, user_id, *, before_dispatch)
```

### `resolve_episode`

```python
resolve_episode(value)
```

### `sign_artwork`

```python
sign_artwork(web_station_id, *, content_type, before_dispatch, web_episode_id=None)
```

### `sign_experimental_media`

```python
sign_experimental_media(value, *, filename, content_type, num_parts, video, before_dispatch)
```

### `sign_media`

```python
sign_media(*, filename, content_type, before_dispatch, web_episode_id=None, num_parts=None)
```

### `sign_thumbnail`

```python
sign_thumbnail(value, *, filename, content_type, before_dispatch)
```

### `thumbnail`

```python
thumbnail(value)
```

### `transcript_upload_status`

```python
transcript_upload_status(value, upload_id)
```

### `update_clip`

```python
update_clip(details, *, before_dispatch)
```

### `update_distribution`

```python
update_distribution(web_station_id, fields, *, before_dispatch)
```

### `update_episode`

```python
update_episode(web_episode_id, user_id, fields, *, before_dispatch)
```

### `update_show`

```python
update_show(web_station_id, user_id, metadata, *, before_dispatch)
```

## REST and authentication contracts

Named REST operations are dispatched with `client.rest(name, ...)`.
Authentication rows describe Accounts routes; `AuthClient` implements PKCE code
exchange and refresh. Other login/challenge routes are discovery references,
not implemented password or authenticator clients. The transport restricts
API origins; route discovery does not grant application permissions.

| Name | Method | Path | Fields |
| --- | --- | --- | --- |
| `auth.gateway` | GET | `/api/shell/gateway` | returnTo |
| `auth.authorize` | GET | `/oauth2/v2/auth` | response_type client_id scope redirect_uri code_challenge code_challenge_method state response_mode prompt acr_values |
| `auth.exchange` | POST | `/api/token` | grant_type client_id code redirect_uri code_verifier |
| `auth.refresh` | POST | `/api/token` | grant_type client_id refresh_token serverUrl |
| `auth.keys` | GET | `/oidc/certs/v1` |  |
| `auth.password` | POST | `/login/password` | username password remember automationKey recaptchaToken continue flowCtx client_id |
| `auth.passwordless` | POST | `/login/otc/start` | username password remember automationKey recaptchaToken continue flowCtx client_id |
| `auth.code.send` | POST | `/login/code/send?` |  |
| `auth.code.resend` | POST | `/login/code/resend?` |  |
| `auth.code.verify` | POST | `/login/code/verify?` |  |
| `auth.phone.request` | POST | `/login/phone/code/request` |  |
| `auth.phone.resend` | POST | `/login/phone/code/resend` |  |
| `auth.phone.verify` | POST | `/login/phone/code/verify` |  |
| `auth.passkey.start` | POST | `/login/assertion/start` |  |
| `auth.passkey.finish` | POST | `/login/assertion/finalize` | sealed_assertion continue_uri |
| `auth.webauthn.start` | POST | `/v1/authenticate/start` | signals.flowId |
| `auth.webauthn.finish` | POST | `/v1/authenticate/finish` |  |
| `auth.logout` | GET | `/logout?continue=` | continue |
| `auth.google` | GET | `/login/google` |  |
| `auth.apple` | GET | `/login/apple` |  |
| `auth.facebook` | GET | `/login/facebook` |  |
| `auth.naver` | GET | `/login/naver` |  |
| `account.settings` | GET | `/v3/settings/user` | userId webStationId isMumsCompatible |
| `account.verification` | GET | `/v3/users/verification` | isMumsCompatible |
| `show.legacy_ids` | GET | `/v3/shows/{value}/legacyIds` |  |
| `show.create` | POST | `/v3/users/multishow` | stationMetadata |
| `show.create.migrated` | POST | `/v3/shows/multiShow` | stationMetadata |
| `show.delete.request` | POST | `/v3/stations/webStationId:{value}/requestDeletion` | userId |
| `show.metadata.read` | GET | `/v3/stations/webStationId:{value}/metadata` | isMumsCompatible |
| `show.metadata.write` | POST | `/v3/stations/webStationId:{value}/metadata` | userId webStationId podcastIsExplicit podcastName podcastDescription podcastAuthorName podcastLanguage podcastCategory |
| `show.settings.write` | POST | `/v3/settings` |  |
| `show.categories` | GET | `/v3/settings/podcast-category/options?locale={value}` | locale |
| `show.distribution` | GET | `/v3/stations/webStationId:{value}/distribution` | isMumsCompatible |
| `show.distribution.write` | PUT | `/v3/stations/webStationId:{value}/distribution` | podcastExternalSource podcastExternalSourceRedirected podcastItunesOwnerCode podcastRedirectDestination externalLinks isUserEmailInRss isRssFeedEnabled podcastAuthorEmail |
| `show.art.sign` | GET | `/v3/stations/{value}/images/upload/signed_url` | webStationId contentType |
| `show.art.process` | POST | `/v3/stations/webStationId:{value}/images/upload/{value}/process_upload` | webStationId isMumsCompatible |
| `show.art.status` | GET | `/v3/stations/webStationId:{value}/images/upload/{value}` | isMumsCompatible |
| `episode.list` | GET | `/v3/stations/webStationId:{value}/episodePage` | orderBy subscriptionsFilter searchTitle limit pageToken isMumsCompatible publishedOnly |
| `episode.create` | POST | `/v3/stations/webStationId:{value}/episodes` | title description hourOffset metadata audios |
| `episode.overview` | GET | `/v3/episodes/webEpisodeId:{value}/overview` | returnWebIds isMumsCompatible |
| `episode.resolve` | GET | `/v3/episodes/spotify:episode:{value}/episodeId` | isMumsCompatible |
| `episode.update` | POST | `/v3/episodes/webEpisodeId:{value}/update` | userId title description seasonNumber episodeNumber episodeType episodeAudiosWithAudioTypes isPublished isPW podcastEpisodeIsExplicit isVideoEighteenPlus publishOn wizardDraftedToPublishOn |
| `episode.delete` | POST | `/v3/episodes/webEpisodeId:{value}/delete` | isMumsCompatible |
| `media.sign` | GET | `/v3/upload/signed_url` | filename type isMumsCompatible isMultipartUpload numParts uploadType |
| `media.sign.episode` | GET | `/v3/episodes/webEpisodeId:{value}/upload/signedUrl` | filename type isMumsCompatible isMultipartUpload numParts uploadType |
| `media.process` | POST | `/v3/upload/{value}/process_upload` | userId uploadType origin caption isExtractedFromVideo isMultipartUpload parts uploadId webEpisodeId webStationId |
| `media.audio.status` | GET | `/v3/upload/{value}` |  |
| `media.status` | GET | `/v3/upload/media/{value}` | isMumsCompatible includeMediaValidation |
| `episode.art.sign` | GET | `/v3/episodes/webEpisodeId:{value}/images/upload/signed_url` | contentType |
| `episode.art.process` | POST | `/v3/episodes/webEpisodeId:{value}/images/upload/{value}/process_upload` | uploadType webEpisodeId |
| `episode.art.status` | GET | `/v3/episodes/webEpisodeId:{value}/images/upload/{value}` | isMumsCompatible |

## Persisted GraphQL versions

Use `client.graphql(name, variables, creator_client=...)` for the exact
catalogue operation and client. A digest is a public persisted-query identifier,
not an authentication credential. Different versions remain separate entries.

| Operation | Kind | Client | Variables | SHA-256 |
| --- | --- | --- | --- | --- |
| CheckSuspension | query | podcasters-shell-app | — | `30d2adddedd2c81d73a0f0c66bc0756ec8d1bbebcc6f91f3fc1895594e47a06d` |
| WebGetIndexedEpisodeList | query | public-website | showUri: ShowUri!, pageSize: Int!, currentPage: Int!, sortOrder: SortOrder, sortBy: Field, search: String, filter: FilterType, includeMembershipTiers: Boolean!, analyticsWindow: AnalyticsWindow, customDateRange: CustomDateRangeInput | `da95dd0d5c5e3ffed3150f34f1d9674b6cd3548cdf59a49a37e1a65b325c9e98` |
| WebGetNavigationContextForUser | query | podcasters-shell-app | — | `706d07c416a161b70536f3a99bd19401243346296a3cd6c4fc34eb016cbc7467` |
| WebGetShowTypeByUri | query | podcasters-shell-app | showUri: ShowUri! | `aecbba024ed4d62919387f7d45ae102537a0f8c58e9f6d48503cbfe4b1046247` |
| WebGetShowsForUser | query | podcasters-shell-app | showFilter: ShowFilterEnum, currentPage: Int, pageSize: Int, searchQuery: String | `7cda916f4207b72c1986e973a2e1cf794072979cc4e483344f2f33159448f8b4` |
| WebGetUser | query | microfrontend-dynamic-home | — | `a61caddef3932d9a5571eeb30b90d8b9abb9d2e13398034ed75296dfaec796d3` |
| WebGetUserAndCurrentShow | query | podcasters-shell-app | showUri: ShowUri! | `501773d0a1190db7cf97cd38bafdfd34c07e1b8757df8f9b5a25574b734abad7` |
| WebGetUserShows | query | public-website | — | `e5b72190d76dacc4d93ac4c01489f33116e7885890c95241f2f3ede11d9eca11` |
| WebGetUserShowsWithMetadata | query | public-website | — | `ac1347421a01f877ffd50bc33ce7c27dd80bac465f243684d319bf21de3bca81` |
| checkShowPermissions | query | public-website | showUri: ShowUri!, permissionsToCheck: [PermissionKind!]! | `dd416a643a9b9ee35ccaa4381404bb4719c9271caf3775df48dff8af3026a9e1` |
| createClipForEpisode | mutation | microfrontend-merch-tools | request: CreateClipForEpisodeRequestInput | `dc439ddf6a2c0b58d7b1bba1ab99f800cc729b38d80a9652b1c45083142a4b15` |
| deleteClip | mutation | microfrontend-merch-tools, public-website | clipUri: ExpressionUri! | `a9472e82a967dfbec1b90ebfc50938c1a3719cfaf6b2a5ecd155bbaa72e35142` |
| experimental_s4cGetSignedUploadUrls | mutation | public-website | episodeUri: EpisodeUri!, mimeType: String!, chunkCount: Int!, mediaType: MediaType!, fileName: String!, uploadOrigin: String! | `703170a4e53023557e1306ed679160bca0acbdb41dde16c831a8f634b7439ad8` |
| generateMediaUpload | mutation | microfrontend-merch-tools | episodeUri: EpisodeUri!, uploadType: UploadType! | `3a9aa90f4f04c87883fc9fa7f77bda5b4bd9dd0fe1df7c2d5e0573725852b49f` |
| getClipByUri | query | microfrontend-merch-tools | expressionUri: ExpressionUri! | `ae280808885e82e94ca7fbf388a10ee08b12d887354b5812db181c38955aa35f` |
| getClipRelatedContent | query | microfrontend-merch-tools | episodeUri: EpisodeUri!, showUri: ShowUri! | `32dfbf06ed0fdb172da9bb21e3fe86c7402cf4622e679ce4873c5dd4a34a058c` |
| getCusMediaUploadStatus | query | public-website | episodeUri: EpisodeUri!, getMediaUploadRequest: GetMediaUploadRequestInput! | `93e8c125a85be6cb634c384cbbc1c7b63081aebc712072ed70baba4d0b4e05fd` |
| getEpisodeAssetDownloadUrl | query | public-website | episodeUri: EpisodeUri! | `e476b308aac95f6a3f140173110b6061efd0d75a3dd3377c6b5beda897645e04` |
| getEpisodeClipDialogs | query | public-website | episodeUri: EpisodeUri! | `6d59876acf141c4b56dfb3e142bbe46b20f3b6ed8b707cd11773280ef0f12888` |
| getEpisodeClips | query | microfrontend-merch-tools | episodeUri: EpisodeUri! | `25f38ec5d69931a3f3574b7a70afc13e7fbce17fcf7866666cc4d6492bc025bb` |
| getEpisodeClips | query | public-website | episodeUri: EpisodeUri! | `d6585abc958c57f7f34b8d7f54a2943443785c502616ab0702c67b782baf844c` |
| getEpisodeClipsAnalytics | query | public-website | episodeUri: EpisodeUri!, showUri: String | `4a83f5c3d80529324aa2fe624ed38fffac62f63bef40606fb86b72f9b30b18f0` |
| getEpisodeContentMediaUrls | query | public-website | episodeUri: EpisodeUri! | `2766d2e7b71a816778efc4534ab0db6b5376763ee25748cf7c6817e9b2327a8d` |
| getEpisodeMetadata | query | microfrontend-merch-tools | episodeUri: EpisodeUri! | `9b9bb9ae700b38eeb884238c94bdad250dc7efdac2acdd2a0affccd48e5860ca` |
| getEpisodeThumbnail | query | public-website | episodeUri: EpisodeUri! | `bf061fbd2cb87cdbb448e5509efa5e091cd6e2b50ffec8a374a37cee521a6be9` |
| getEpisodeThumbnailImageSpecs | query | public-website | episodeUri: EpisodeUri! | `01cf26d3947f3db39fa4d72ea754ae19d4e5ffaf15d306c42b9638b7300511f9` |
| getMediaUploadStatus | query | microfrontend-merch-tools | episodeUri: EpisodeUri!, uploadId: String! | `94314c180c5bf604e3f52e53d779e1f06b897a48d5e8404c0212e1e71cf4cdfd` |
| getOrgForShow | query | public-website | showUri: ShowUri! | `7c50ceace62c51c9d88f655de9227c62d2a93ce42a659a1af9b59f48e9efb19b` |
| getShowCoverArt | query | public-website | showUri: ShowUri! | `bdc7d5b41bef1f809a3aa6a4cc1f358dac6d6b023d9a8c8be4436708e6e76782` |
| getShowHeader | query | microfrontend-dynamic-home | showUri: ShowUri! | `23b082864b6527f57cfb51b4b691f6f76633a97df5b49be75df29a34043a381c` |
| getShowsForUser | query | microfrontend-dynamic-home | — | `5173d942d10f182e6289cc124a31d831e25cd76af18ed024cca9084aff623567` |
| getThumbnailSignedUrl | mutation | public-website | contentType: String!, episodeUri: String, episodeUriV2: EpisodeUri!, fileName: String, platformType: PlatformType!, thumbnailType: ThumbnailType! | `3621c97566c4cfdffc7ce3fbba1d886441498ac96ca27b4b594546a83d9bf876` |
| getUserMetadata | query | public-website | — | `1f14dd23be60de17813e3e58cd690951366a04e44ac8e9ef858e987a81318ca8` |
| publishMediaUpload | mutation | microfrontend-merch-tools | episodeUri: EpisodeUri!, uploadId: String! | `a5c4b8cc1d4060c7902132d39bd92b17ba802d2f525b78af4621b0363027aad6` |
| replaceClip | mutation | microfrontend-merch-tools | request: ReplaceClipRequestInput | `189ee551e39e94eb5614d50c1758762305f9c1efc8f1694206866451567114d6` |
| updateClip | mutation | microfrontend-merch-tools | request: UpdateClipRequestInput | `5aee39f67f1c8c2cb1dcff3a63a5114a2526dc025cfc0be23266140bc2cfc06b` |
| uploadThumbnailComplete | mutation | public-website | episodeUri: EpisodeUri!, thumbnailUuid: String! | `c43a47136fa24af04869aad730b412789edbfeced6c9aef949a94cb2ca383082` |

## Result and failure contracts

Methods return provider dictionaries without silently dropping fields.
`all_episodes` requires complete pagination; individual-page reads remain available.
`ProviderError`, `GraphError` and `OutcomeUnknown` distinguish HTTP rejection,
application-level errors and uncertain dispatch outcomes. See [Writes](writes)
for reservation, reconciliation and transfer behavior.
