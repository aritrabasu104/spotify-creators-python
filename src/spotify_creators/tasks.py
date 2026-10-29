"""Task requests; callers retain allocation, transfer and publication intents.

Each side effect is a separate method. Nothing silently retries, publishes after
upload, switches an experimental branch, or replaces an accepted operation.
"""

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from .protocol import legacy_station_id

HOSTED = 'public-website'
TOOLS = 'microfrontend-merch-tools'
COMPAT = {'isMumsCompatible': True}


def native_hour_offset(timezone_name, instant=None):
    """The native JS Date.getTimezoneOffset()/60 sign, including actual DST."""
    instant = instant or datetime.now(ZoneInfo(timezone_name))
    if instant.tzinfo is None:
        raise ValueError('An original timezone-aware instant is required')
    return -instant.astimezone(ZoneInfo(timezone_name)).utcoffset().total_seconds() / 3600


def confirmed(value):
    return value is True or isinstance(value, str) and value == 'true'


def episode_uri(value):
    value = value.removeprefix('spotify:episode:')
    if not re.fullmatch(r'[A-Za-z0-9]{22}', value):
        raise ValueError('Original Spotify episode identity required')
    return 'spotify:episode:' + value


def show_uri(value):
    value = value.removeprefix('spotify:show:')
    if not re.fullmatch(r'[A-Za-z0-9]{22}', value):
        raise ValueError('Original Spotify show identity required')
    return 'spotify:show:' + value


class CreatorsTasks:
    def __init__(self, client):
        self.api = client

    def legacy_show(self, show_id):
        return self.api.rest('show.legacy_ids', show_uri(show_id).split(':')[-1])

    def resolve_episode(self, value):
        return self.api.rest('episode.resolve', episode_uri(value).split(':')[-1], query=COMPAT)

    def metadata(self, web_station_id):
        return self.api.rest('show.metadata.read', web_station_id, query=COMPAT)

    def categories(self, locale='en-US'):
        return self.api.rest('show.categories', locale)

    def create_show(self, metadata, *, before_dispatch, migrated):
        # The original feature selection chooses the branch, never a retry.
        return self.api.rest('show.create.migrated' if migrated else 'show.create',
                             query=None if migrated else COMPAT, body={'stationMetadata': metadata},
                             before_dispatch=before_dispatch)

    def update_show(self, web_station_id, user_id, metadata, *, before_dispatch):
        if not isinstance(metadata, dict) or {'userId', 'webStationId', 'stationId'} & metadata.keys():
            raise ValueError('Metadata cannot replace its original account/show identity')
        if not isinstance(metadata.get('podcastIsExplicit'), bool):
            raise ValueError('Retain the original approved show explicitness as a Boolean')
        body = {**metadata, 'userId': user_id, 'webStationId': web_station_id,
                'podcastIsExplicit': 'true' if metadata['podcastIsExplicit'] else 'false'}
        result = self.api.rest('show.metadata.write', web_station_id, query=COMPAT,
                               body=body, before_dispatch=before_dispatch)
        if isinstance(result, dict) and result.get('errors'):
            raise ValueError('Spotify rejected the original show metadata')
        return result

    def request_show_deletion(self, web_station_id, user_id, *, before_dispatch):
        return self.api.rest('show.delete.request', web_station_id, body={'userId':user_id},
                             before_dispatch=before_dispatch)

    def distribution(self, web_station_id):
        return self.api.rest('show.distribution', web_station_id, query=COMPAT)

    def update_distribution(self, web_station_id, fields, *, before_dispatch):
        allowed = {'podcastExternalSource', 'podcastExternalSourceRedirected', 'podcastItunesOwnerCode',
                   'podcastRedirectDestination', 'externalLinks', 'isUserEmailInRss',
                   'isRssFeedEnabled', 'podcastAuthorEmail'}
        if not isinstance(fields, dict) or set(fields) - allowed:
            raise ValueError('Use the exact native distribution fields')
        return self.api.rest('show.distribution.write', web_station_id,
                             query={**COMPAT, 'webStationId': web_station_id},
                             body=fields, before_dispatch=before_dispatch)

    def episodes(self, show_id, *, page=1, page_size=50, filter_type=None,
                 analytics_window='WINDOW_LAST_SEVEN_DAYS'):
        if not isinstance(page, int) or page < 1 or not 1 <= page_size <= 100:
            raise ValueError('Bound the original episode page')
        variables = {'showUri': show_uri(show_id), 'pageSize': page_size,
                     'currentPage': page, 'includeMembershipTiers': False}
        if filter_type is not None:
            variables['filter'] = filter_type
        if analytics_window is not None:
            variables['analyticsWindow'] = analytics_window
        return self.api.graphql('WebGetIndexedEpisodeList', variables, creator_client=HOSTED)

    def all_episodes(self, show_id, *, max_pages=500):
        if not isinstance(max_pages, int) or not 1 <= max_pages <= 500:
            raise ValueError('Bound the complete original episode reconciliation')
        items, identities, original = [], set(), None
        for page in range(1, max_pages+1):
            result = self.episodes(show_id, page=page, page_size=100)
            value = result['showByShowUri']['episodesV2']
            pagination = value['pagination']
            if value.get('indexStatus') != 'COMPLETED':
                raise ValueError('The original Spotify episode index is not complete')
            if (page == 1 and pagination['totalItems'] == 0 and pagination['totalPages'] == 0
                    and pagination['currentPage'] in {0,1} and not value['items']):
                return {'items':[], 'pagination':pagination, 'indexStatus':value['indexStatus']}
            if pagination['currentPage'] != page:
                raise ValueError('Spotify returned a different original episode page')
            census = (pagination['totalItems'], pagination['totalPages'])
            if original is not None and original != census:
                raise ValueError('The episode census changed during reconciliation')
            original = census
            for item in value['items']:
                identity = episode_uri(item['uri'])
                if identity in identities:
                    raise ValueError('An original episode repeated across pages')
                identities.add(identity); items.append(item)
            if page >= pagination['totalPages']:
                if len(items) != pagination['totalItems']:
                    raise ValueError('The complete episode census is missing identities')
                return {'items':items, 'pagination':pagination, 'indexStatus':value.get('indexStatus')}
        raise ValueError('The episode census exceeded its original page budget')

    def episode_page(self, web_station_id, *, limit=100, page_token=None, order_by='publishOn',
                     search_title=None, published_only=False, subscriptions_filter=None):
        if not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError('Bound the native REST episode page')
        query = {**COMPAT, 'limit':limit, 'orderBy':order_by}
        for key, value in [('pageToken',page_token), ('searchTitle',search_title),
                           ('subscriptionsFilter',subscriptions_filter)]:
            if value is not None:
                query[key] = value
        if published_only:
            query['publishedOnly'] = True
        return self.api.rest('episode.list', web_station_id, query=query)

    def create_episode(self, web_station_id, *, title, description, hour_offset,
                       before_dispatch, metadata=None, audios=None):
        body = {'title': title, 'description': description, 'hourOffset': hour_offset}
        if metadata is not None:
            body['metadata'] = metadata
        if audios is not None:
            body['audios'] = [{k: v for k, v in item.items() if k != 'webAudioId'} for item in audios]
        return self.api.rest('episode.create', web_station_id,
                             query={**COMPAT, 'returnWebIds': True}, body=body,
                             before_dispatch=before_dispatch)

    def episode(self, web_episode_id):
        return self.api.rest('episode.overview', web_episode_id, query={**COMPAT, 'returnWebIds': True})

    def update_episode(self, web_episode_id, user_id, fields, *, before_dispatch):
        allowed = {'title', 'description', 'seasonNumber', 'episodeNumber', 'episodeType',
                   'episodeAudiosWithAudioTypes', 'isPublished', 'isPW', 'podcastEpisodeIsExplicit',
                   'isVideoEighteenPlus', 'publishOn', 'wizardDraftedToPublishOn'}
        if not isinstance(fields, dict) or set(fields) - allowed:
            raise ValueError('Use only original episode-update fields')
        from datetime import datetime,timezone
        fields=dict(fields)
        for key in ('publishOn','wizardDraftedToPublishOn'):
            if fields.get(key) is not None:
                instant=datetime.fromisoformat(fields[key].replace('Z','+00:00'))
                if instant.tzinfo is None:raise ValueError('Original release time needs its timezone')
                # The native SDK uses Date.toISOString(); this endpoint rejects
                # an otherwise valid ISO value without its millisecond field.
                fields[key]=instant.astimezone(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')
        return self.api.rest('episode.update', web_episode_id, query=COMPAT,
                             body={'userId': user_id, **fields}, before_dispatch=before_dispatch)

    def delete_episode(self, web_episode_id, *, before_dispatch):
        return self.api.rest('episode.delete', web_episode_id, query=COMPAT, before_dispatch=before_dispatch)

    def sign_media(self, *, filename, content_type, before_dispatch, web_episode_id=None,
                   num_parts=None):
        query = {**COMPAT, 'filename': filename, 'type': content_type}
        if num_parts is not None:
            if not isinstance(num_parts, int) or not 1 <= num_parts <= 10000:
                raise ValueError('Invalid original multipart count')
            query.update(isMultipartUpload=True, numParts=num_parts,
                         uploadType='video' if 'video' in content_type else 'audio')
        args = ('media.sign.episode', web_episode_id) if web_episode_id else ('media.sign',)
        return self.api.rest(*args, query=query, before_dispatch=before_dispatch)

    def process_media(self, request_uuid, *, user_id, web_station_id, web_episode_id,
                      filename, video, before_dispatch, parts=None, upload_id=None):
        body = {'userId': user_id, 'uploadType': 'video' if video else 'default',
                'origin': 'episode-media:upload', 'caption': filename,
                'isExtractedFromVideo': bool(video), 'webEpisodeId': web_episode_id,
                'webStationId': web_station_id}
        if parts is not None:
            if not upload_id:
                raise ValueError('Retain the original multipart upload identity')
            body.update(isMultipartUpload=True, parts=parts, uploadId=upload_id)
        return self.api.rest('media.process', request_uuid, query=COMPAT, body=body,
                             before_dispatch=before_dispatch)

    def media_status(self, request_uuid):
        return self.api.rest('media.status', request_uuid,
                             query={**COMPAT, 'includeMediaValidation': True})

    def sign_experimental_media(self, value, *, filename, content_type, num_parts, video,
                                before_dispatch):
        return self.api.graphql('experimental_s4cGetSignedUploadUrls', {
            'episodeUri': episode_uri(value), 'mimeType': content_type, 'chunkCount': num_parts,
            'mediaType': 'MEDIA_TYPE_VIDEO' if video else 'MEDIA_TYPE_AUDIO',
            'fileName': filename, 'uploadOrigin': 'episode-media:upload'},
            creator_client=HOSTED, before_dispatch=before_dispatch)

    def experimental_media_status(self, value, request_uuid):
        return self.api.graphql('getCusMediaUploadStatus', {'episodeUri': episode_uri(value),
                                'getMediaUploadRequest': {'requestUuid':request_uuid}}, creator_client=HOSTED)

    def sign_artwork(self, web_station_id, *, content_type, before_dispatch, web_episode_id=None):
        operation, values = ('episode.art.sign', (web_episode_id,)) if web_episode_id else (
            'show.art.sign', (legacy_station_id(web_station_id),))
        return self.api.rest(operation, *values,
                             query={**COMPAT, 'webStationId': web_station_id, 'contentType': content_type},
                             before_dispatch=before_dispatch)

    def process_artwork(self, web_station_id, request_uuid, *, before_dispatch, web_episode_id=None):
        if web_episode_id:
            return self.api.rest('episode.art.process', web_episode_id, request_uuid, query=COMPAT,
                                 body={'uploadType': 'episode_image', 'webEpisodeId': web_episode_id},
                                 before_dispatch=before_dispatch)
        # The show-image path has NO JSON body in the actual native source.
        return self.api.rest('show.art.process', web_station_id, request_uuid,
                             query={**COMPAT, 'webStationId': web_station_id}, before_dispatch=before_dispatch)

    def artwork_status(self, web_station_id, request_uuid, *, web_episode_id=None):
        return self.api.rest('episode.art.status' if web_episode_id else 'show.art.status',
                             web_episode_id or web_station_id, request_uuid, query=COMPAT)

    def thumbnail(self, value):
        return self.api.graphql('getEpisodeThumbnail', {'episodeUri': episode_uri(value)}, creator_client=HOSTED)

    def sign_thumbnail(self, value, *, filename, content_type, before_dispatch):
        return self.api.graphql('getThumbnailSignedUrl', {
            'episodeUriV2': episode_uri(value), 'fileName': filename, 'contentType': content_type,
            'platformType': 'S4C_HOSTED', 'thumbnailType': 'USER_UPLOADED_THUMBNAIL'},
            creator_client=HOSTED, before_dispatch=before_dispatch)

    def complete_thumbnail(self, value, thumbnail_uuid, *, before_dispatch):
        result = self.api.graphql('uploadThumbnailComplete', {'episodeUri': episode_uri(value),
                                 'thumbnailUuid': thumbnail_uuid}, creator_client=HOSTED,
                                 before_dispatch=before_dispatch)
        if not confirmed((result or {}).get('completeThumbnailUpload',{}).get('success')):
            raise ValueError('Spotify did not confirm the original thumbnail completion')
        return result

    def clips(self, value):
        return self.api.graphql('getEpisodeClips', {'episodeUri': episode_uri(value)}, creator_client=HOSTED)

    def clip(self, clip_uri):
        return self.api.graphql('getClipByUri', {'expressionUri': clip_uri}, creator_client=TOOLS)

    def create_clip(self, value, show_id, details, *, before_dispatch):
        required = {'description', 'is18Plus', 'isExplicit', 'parentUri', 'uploadContentType', 'uploadOrigin'}
        if not isinstance(details, dict) or set(details) != required or details['parentUri'] != show_uri(show_id):
            raise ValueError('Retain every native clip field and the original parent show')
        return self.api.graphql('createClipForEpisode', {'request': {'episodeUri': episode_uri(value),
                                'details': details}}, creator_client=TOOLS, before_dispatch=before_dispatch)

    def update_clip(self, details, *, before_dispatch):
        result = self.api.graphql('updateClip', {'request': details}, creator_client=TOOLS,
                                 before_dispatch=before_dispatch)
        if not confirmed((result or {}).get('updateClip',{}).get('success')):
            raise ValueError('Spotify did not confirm the original clip update')
        return result

    def replace_clip(self, details, *, before_dispatch):
        return self.api.graphql('replaceClip', {'request': details}, creator_client=TOOLS,
                                before_dispatch=before_dispatch)

    def generate_transcript_upload(self, value, *, before_dispatch):
        return self.api.graphql('generateMediaUpload', {'episodeUri': episode_uri(value),
                                'uploadType': 'UPLOAD_TYPE_TRANSCRIPT'}, creator_client=TOOLS,
                                before_dispatch=before_dispatch)

    def transcript_upload_status(self, value, upload_id):
        return self.api.graphql('getMediaUploadStatus', {'episodeUri': episode_uri(value),
                                'uploadId': upload_id}, creator_client=TOOLS)

    def publish_transcript_upload(self, value, upload_id, *, before_dispatch):
        return self.api.graphql('publishMediaUpload', {'episodeUri': episode_uri(value),
                                'uploadId': upload_id}, creator_client=TOOLS, before_dispatch=before_dispatch)
