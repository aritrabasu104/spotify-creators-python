import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from urllib.parse import parse_qs, urlencode, urlsplit
from spotify_creators.auth import AuthClient, OAuthAttempt, Session
from spotify_creators.client import SpotifyClient, GraphError
from spotify_creators.http import HttpTransport, OutcomeUnknown, Response
from spotify_creators.media import UploadTarget, upload_exact, upload_multipart
from spotify_creators.protocol import rest_payload, rest_query, web_episode_id, legacy_episode_id
from spotify_creators.catalog import INVENTORY
from spotify_creators.tasks import CreatorsTasks, native_hour_offset
from spotify_creators.public import read_feed, read_public_episode

CREATORS_CLIENT_ID = "example-client-id"


def session(token='synthetic-access',refresh='synthetic-refresh'):
    return Session(token,time.time()+3600,CREATORS_CLIENT_ID,'user-read-email',refresh)

class FakeTransport:
    def __init__(self,*responses):
        self.responses=list(responses);self.calls=[]
    def execute(self,*args,**kwargs):
        self.calls.append((args,kwargs))
        value=self.responses.pop(0)
        if isinstance(value,Exception):raise value
        return value

class ContractTests(unittest.TestCase):
    def test_session_provider_renews_before_original_mutation_admission(self):
            expired=Session('expired-synthetic',0,CREATORS_CLIENT_ID,'user-read-email','refresh')
            fresh=session('renewed-synthetic');events=[]
            def current(original):events.append('session');return fresh
            http=FakeTransport(Response(200,{'email':'owner@example.test'}),Response(200,{}))
            client=SpotifyClient(http,expired,INVENTORY,expected_email='owner@example.test',session_provider=current)
            client.verify_account()
            client.rest('episode.update','eugi0',body={'title':'Original'},before_dispatch=lambda _:events.append('admit'))
            self.assertEqual(events,['session','session','admit'])
            self.assertEqual(http.calls[-1][1]['headers']['Authorization'],'Bearer renewed-synthetic')

    def test_release_fields_use_the_native_javascript_utc_millisecond_format(self):
            http=FakeTransport(Response(200,{'email':'owner@example.test'}),Response(200,{}))
            client=SpotifyClient(http,session(),INVENTORY,expected_email='owner@example.test');client.verify_account()
            CreatorsTasks(client).update_episode('eugi0',1,{'publishOn':'2026-10-29T16:00:00+05:30',
                'wizardDraftedToPublishOn':None},before_dispatch=lambda _:None)
            self.assertEqual(http.calls[-1][1]['body']['publishOn'],'2026-10-29T10:30:00.000Z')
            self.assertIsNone(http.calls[-1][1]['body']['wizardDraftedToPublishOn'])

    def test_pkce_code_is_bound_to_original_state_recipient_and_verifier(self):
            attempt=OAuthAttempt.prepare(client_id=CREATORS_CLIENT_ID,redirect_uri="https://example.test/callback");query=parse_qs(urlsplit(attempt.authorize_url).query)
            self.assertEqual(query['client_id'],[CREATORS_CLIENT_ID])
            self.assertEqual(query['code_challenge_method'],['S256'])
            callback='https://example.test/callback?'+urlencode({'code':'original','state':attempt.state})
            http=FakeTransport(Response(200,{'access_token':'synthetic','token_type':'Bearer','expires_in':3600,'refresh_token':'refresh'}))
            intents=[];AuthClient(http,expected_email='owner@example.test').exchange(attempt,callback,before_dispatch=intents.append)
            self.assertEqual(http.calls[0][1]['form']['code_verifier'],attempt.verifier)
            self.assertEqual(intents[0]['kind'],'spotify_pkce_exchange')
            with self.assertRaises(ValueError):attempt.callback_code(callback.replace('example.test','other.example'))
            with self.assertRaises(ValueError):attempt.callback_code(callback.replace(attempt.state,'wrong'))
            self.assertNotIn(attempt.verifier,repr(attempt))

    def test_refresh_preserves_omitted_refresh_token_and_rechecks_exact_account(self):
            http=FakeTransport(Response(200,{'access_token':'new','token_type':'Bearer','expires_in':3600}),
                               Response(200,{'email':'different@example.test'}))
            auth=AuthClient(http,expected_email='owner@example.test');renewed=auth.renew(session(),before_dispatch=lambda _:None)
            self.assertEqual(renewed.refresh_token,'synthetic-refresh')
            with self.assertRaises(ValueError):auth.verify(renewed)
            self.assertNotIn('synthetic-refresh',repr(renewed))

    def test_auth_admission_failure_and_missing_refresh_do_not_dispatch(self):
            http=FakeTransport();auth=AuthClient(http,expected_email='owner@example.test')
            def refused(_):raise ValueError('original intent already consumed')
            with self.assertRaises(ValueError):auth.renew(session(),before_dispatch=refused)
            with self.assertRaises(ValueError):auth.renew(session(refresh=None),before_dispatch=lambda _:None)
            self.assertEqual(http.calls,[])

    def test_native_ids_keep_boolean_omission_and_bounded_nested_semantics(self):
            station=format(100*(100000+12345),'x')
            self.assertEqual(rest_payload({'webStationId':station,'webEpisodeId':'eugi0','isPublished':False}),
                             {'stationId':12345,'episodeId':0,'isPublished':False})
            value={'audios':[{'webAudioId':'augi0','webEpisodeId':'eugi0','nested':{'webAudioId':'augi0'}}]}
            result=rest_payload(value)
            self.assertEqual(result['audios'][0]['audioId'],0)
            self.assertEqual(result['audios'][0]['webEpisodeId'],'eugi0')
            self.assertEqual(result['audios'][0]['nested']['webAudioId'],'augi0')
            self.assertEqual(parse_qs(rest_query({'isMumsCompatible':True,'flag':False})),
                             {'isMumsCompatible':['true'],'flag':['false']})

    def test_signing_get_requires_verified_account_and_original_native_intent(self):
            http=FakeTransport(Response(200,{'email':'owner@example.test'}),Response(200,{'requestUuid':'issued'}))
            api=SpotifyClient(http,session(),{'graphql_operations':[]},expected_email='owner@example.test')
            with self.assertRaises(ValueError):api.rest('media.sign',query={'filename':'original.mp4'})
            self.assertEqual(http.calls,[])
            api.verify_account()
            with self.assertRaises(ValueError):api.rest('media.sign',query={'filename':'original.mp4'})
            intents=[];api.rest('media.sign',query={'filename':'original.mp4'},before_dispatch=intents.append)
            self.assertEqual(len(intents),1)
            self.assertTrue(http.calls[-1][1]['mutation'])

    def test_graphql_http_200_error_is_not_delivery_or_permission_to_retry(self):
            op={'name':'updateClip','sha256':'a'*64,'kind':'mutation','creator_clients':['microfrontend-merch-tools']}
            http=FakeTransport(Response(200,{'email':'owner@example.test'}),
                               Response(200,{'data':{'updateClip':None},'errors':[{'extensions':{'code':'FORBIDDEN'}}]}))
            api=SpotifyClient(http,session(),{'graphql_operations':[op]},expected_email='owner@example.test');api.verify_account()
            intents=[]
            with self.assertRaises(GraphError) as error:
                api.graphql('updateClip',{'request':{'is18Plus':False}},creator_client='microfrontend-merch-tools',before_dispatch=intents.append)
            self.assertEqual(error.exception.codes,('FORBIDDEN',));self.assertEqual(len(intents),1)
            self.assertEqual(len(http.calls),2)

    def test_http_form_encoding_and_transport_does_not_follow_redirects(self):
            class Reply:
                code=200;headers={}
                def __enter__(self):return self
                def __exit__(self,*_):pass
                def read(self,_):return b'{}'
            calls=[]
            class Opener:
                def open(self,request,**kwargs):calls.append(request);return Reply()
            transport=HttpTransport();transport.opener=Opener()
            transport.execute('POST','https://accounts.spotify.com/api/token',form={'grant_type':'refresh_token','refresh_token':'a+b'},mutation=True)
            self.assertEqual(parse_qs(calls[0].data.decode())['refresh_token'],['a+b'])
            self.assertEqual(calls[0].get_header('Content-type'),'application/x-www-form-urlencoded')
            with self.assertRaises(ValueError):transport.execute('GET','https://other.example/api/token')

    def test_issued_upload_has_exact_bytes_and_no_account_credentials(self):
            class Reply:
                status=200
                def read(self,_):return b''
                def getheader(self,_):return 'original-etag'
            class Connection:
                sent=b''
                def __init__(self,*args,**kwargs):pass
                def putrequest(self,*_):pass
                def putheader(self,*_):pass
                def endheaders(self):pass
                def send(self,value):self.sent+=value
                def getresponse(self):return Reply()
                def close(self):pass
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory).resolve()/'source';path.write_bytes(b'original bytes')
                artifact={'path':str(path),'size':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
                result=upload_exact(UploadTarget('https://storage.example/issued?signature=private','PUT'),artifact,before_dispatch=lambda _:None,connection_factory=Connection)
                self.assertEqual(result['sha256'],artifact['sha256']);self.assertEqual(result['etag'],'original-etag')
                with self.assertRaises(ValueError):
                    upload_exact(UploadTarget('https://storage.example/issued','PUT',{'Authorization':'Bearer secret'}),artifact,before_dispatch=lambda _:None,connection_factory=Connection)
                artifact['sha256']='0'*64
                with self.assertRaises(ValueError):upload_exact(UploadTarget('https://storage.example/issued','PUT'),artifact,before_dispatch=lambda _:None,connection_factory=Connection)

    def test_exact_graphql_variables_are_validated_before_reserving_a_mutation(self):
            http=FakeTransport(Response(200,{'email':'owner@example.test'}))
            api=SpotifyClient(http,session(),INVENTORY,expected_email='owner@example.test');api.verify_account()
            intents=[]
            with self.assertRaises(ValueError):
                api.graphql('uploadThumbnailComplete',{'episodeUri':'spotify:episode:'+'a'*22},
                            creator_client='public-website',before_dispatch=intents.append)
            with self.assertRaises(ValueError):
                api.graphql('generateMediaUpload',{'episodeUri':'spotify:episode:'+'a'*22,'uploadType':'VIDEO'},
                            creator_client='public-website',before_dispatch=intents.append)
            self.assertEqual(intents,[]);self.assertEqual(len(http.calls),1)

    def test_show_metadata_is_flattened_but_draft_update_does_not_invent_publish(self):
            http=FakeTransport(Response(200,{'email':'owner@example.test'}),Response(200,{}),Response(200,{}))
            api=SpotifyClient(http,session(),INVENTORY,expected_email='owner@example.test');api.verify_account();tasks=CreatorsTasks(api)
            tasks.update_show(format((100000+123)*100,'x'),42,{'podcastDescription':'approved','podcastIsExplicit':False},before_dispatch=lambda _:None)
            self.assertEqual(http.calls[-1][1]['body'],{'userId':42,'stationId':123,'podcastDescription':'approved','podcastIsExplicit':'false'})
            tasks.update_episode(web_episode_id(987),42,{'title':'approved'},before_dispatch=lambda _:None)
            self.assertNotIn('isPublished',http.calls[-1][1]['body'])
            self.assertEqual(legacy_episode_id(web_episode_id(987)),987)

    def test_native_multipart_retains_exact_ranges_etags_and_stops_on_unknown(self):
            connections=[]
            class Reply:
                status=200
                def read(self,_):return b''
                def getheader(self,_):return '"part-etag"'
            class Connection:
                def __init__(self,*args,**kwargs):self.sent=b'';connections.append(self)
                def putrequest(self,*_):pass
                def putheader(self,*_):pass
                def endheaders(self):pass
                def send(self,block):self.sent+=block
                def getresponse(self):return Reply()
                def close(self):pass
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory).resolve()/'input';path.write_bytes(b'abcdefghijk')
                artifact={'path':str(path),'size':11,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
                parts=[{'partNumber':i,'url':'https://storage.example/part'+str(i)} for i in (1,2,3)]
                intents=[];receipts=[]
                result=upload_multipart(parts,artifact,before_dispatch=intents.append,after_part=receipts.append,connection_factory=Connection)
                self.assertEqual([c.sent for c in connections],[b'abcd',b'efgh',b'ijk'])
                self.assertEqual([r['offset'] for r in receipts],[0,4,8])
                self.assertEqual(result,[{'partNumber':i,'etag':'part-etag'} for i in (1,2,3)])
                connections.clear()
                resumed=[]
                upload_multipart(parts,artifact,before_dispatch=intents.append,after_part=resumed.append,
                                 completed_parts=receipts[:2],connection_factory=Connection)
                self.assertEqual([c.sent for c in connections],[b'ijk'])
                self.assertEqual([r['partNumber'] for r in resumed],[3])
                connections.clear()
                with self.assertRaises(ValueError):
                    upload_multipart(parts,artifact,before_dispatch=intents.append,after_part=resumed.append,
                                     completed_parts=[{**receipts[0],'sha256':'f'*64}],connection_factory=Connection)
                self.assertEqual(connections,[])
                class Lost(Connection):
                    def getresponse(self):raise TimeoutError('synthetic lost response')
                with self.assertRaises(OutcomeUnknown):
                    upload_multipart(parts,artifact,before_dispatch=lambda _:None,after_part=lambda _:None,connection_factory=Lost)
                self.assertEqual(len(connections),1)

    def test_clip_uses_parent_show_and_original_episode_without_uploading_bytes(self):
            show='s'*22;episode='e'*22
            http=FakeTransport(Response(200,{'email':'owner@example.test'}),
                               Response(200,{'data':{'createClipForEpisode':{'clipUri':'original-clip'}}}))
            api=SpotifyClient(http,session(),INVENTORY,expected_email='owner@example.test');api.verify_account();tasks=CreatorsTasks(api)
            details={'description':'approved','is18Plus':False,'isExplicit':False,
                     'parentUri':'spotify:episode:'+episode,'uploadContentType':'video/mp4','uploadOrigin':'UPLOAD_ORIGIN_UNSPECIFIED'}
            intents=[]
            with self.assertRaises(ValueError):tasks.create_clip(episode,show,details,before_dispatch=intents.append)
            details['parentUri']='spotify:show:'+show
            tasks.create_clip(episode,show,details,before_dispatch=intents.append)
            request=http.calls[-1][1]['body']['variables']['request']
            self.assertEqual(request['episodeUri'],'spotify:episode:'+episode)
            self.assertEqual(request['details']['parentUri'],'spotify:show:'+show)
            self.assertEqual(len(intents),1);self.assertEqual(len(http.calls),2)

    def test_thumbnail_string_false_does_not_establish_completion(self):
            http=FakeTransport(Response(200,{'email':'owner@example.test'}),
                               Response(200,{'data':{'completeThumbnailUpload':{'success':'false'}}}))
            api=SpotifyClient(http,session(),INVENTORY,expected_email='owner@example.test');api.verify_account()
            with self.assertRaises(ValueError):CreatorsTasks(api).complete_thumbnail('a'*22,'original',before_dispatch=lambda _:None)

    def test_native_hour_offset_preserves_js_sign_and_actual_dst(self):
            from datetime import datetime, timezone
            winter=datetime(2026,1,10,tzinfo=timezone.utc);summer=datetime(2026,7,10,tzinfo=timezone.utc)
            self.assertEqual(native_hour_offset('Asia/Kolkata',winter),-5.5)
            self.assertEqual(native_hour_offset('America/Los_Angeles',winter),8)
            self.assertEqual(native_hour_offset('America/Los_Angeles',summer),7)

    def test_public_readback_has_no_credentials_and_requires_exact_episode(self):
            class Reply:
                code=200
                def __init__(self,value):self.value=value
                def __enter__(self):return self
                def __exit__(self,*_):pass
                def read(self,_):return self.value
            class Opener:
                def __init__(self,value):self.value=value;self.calls=[]
                def open(self,request,**kwargs):self.calls.append(request);return Reply(self.value)
            identity='a'*22;url='https://open.spotify.com/episode/'+identity
            opener=Opener(('<meta property="og:url" content="'+url+'"><meta property="og:title" content="Original">').encode())
            self.assertEqual(read_public_episode(identity,opener=opener)['episode_id'],identity)
            self.assertNotIn('Authorization',dict(opener.calls[0].header_items()))
            wrong=Opener(b'<meta property="og:url" content="https://open.spotify.com/episode/different"><meta property="og:title" content="Original">')
            with self.assertRaises(ValueError):read_public_episode(identity,opener=wrong)
            with self.assertRaises(ValueError):read_feed('https://other.example/feed',opener=opener)

    def test_episode_census_rejects_changed_or_duplicate_pages(self):
            class API:
                def graphql(self,name,variables,**kwargs):
                    return {'showByShowUri':{'episodesV2':{
                        'pagination':{'currentPage':variables['currentPage'],'totalItems':2,'totalPages':2},
                        'items':[{'uri':'spotify:episode:'+'a'*22}],'indexStatus':'COMPLETED'}}}
            with self.assertRaisesRegex(ValueError,'repeated across pages'):
                CreatorsTasks(API()).all_episodes('s'*22)

    def test_empty_episode_index_requires_completed_zero_census(self):
            class API:
                status='COMPLETED'
                def graphql(self,*args,**kwargs):
                    return {'showByShowUri':{'episodesV2':{'items':[],
                        'pagination':{'currentPage':0,'totalItems':0,'totalPages':0},'indexStatus':self.status}}}
            api=API();self.assertEqual(CreatorsTasks(api).all_episodes('s'*22)['items'],[])
            api.status='IN_PROGRESS'
            with self.assertRaisesRegex(ValueError,'index is not complete'):CreatorsTasks(api).all_episodes('s'*22)
