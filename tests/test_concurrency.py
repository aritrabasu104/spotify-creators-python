"""Exercise real overlapping calls and authentication races without a provider."""

from concurrent.futures import ThreadPoolExecutor
import threading
import time
import unittest

from spotify_creators import Client, OutcomeUnknown, Session, SessionManager, UploadPool
from spotify_creators.http import HttpTransport, Response
from spotify_creators.http import ProviderError, require_success
from spotify_creators.protocol import web_episode_id


class ConcurrencyTests(unittest.TestCase):
    def test_default_ten_requests_overlap_on_one_verified_client(self):
        barrier = threading.Barrier(10)
        lock = threading.Lock()
        active = peak = 0

        class Transport:
            def execute(self, method, url, **kwargs):
                nonlocal active, peak
                if url.endswith('/v1/me'):
                    return Response(200, {'email': 'owner@example.test'})
                with lock:
                    active += 1
                    peak = max(peak, active)
                barrier.wait(timeout=5)
                with lock:
                    active -= 1
                return Response(200, {})

        client = Client(Session('synthetic', time.time()+3600), transport=Transport(),
                        expected_email='owner@example.test')
        client.verify_account()
        admissions = []
        results = client.run_uploads(lambda index: client.rest('episode.update', web_episode_id(index),
            body={'title': 'Example'}, before_dispatch=admissions.append), range(20))
        self.assertEqual(peak, 10)
        self.assertEqual(len(admissions), 20)
        self.assertTrue(all(result.error is None for result in results))
        self.assertEqual([result.index for result in results], list(range(20)))

    def test_failed_transfer_is_returned_once_and_completed_siblings_are_retained(self):
        calls = []
        def operation(index):
            calls.append(index)
            if index == 2:
                raise OutcomeUnknown('Original transfer reply lost')
            return index * 2
        results = UploadPool().run(operation, range(12))
        self.assertEqual(sorted(calls), list(range(12)))
        self.assertEqual(results[11].result(), 22)
        with self.assertRaises(OutcomeUnknown):
            results[2].result()

    def test_login_and_refresh_are_single_flight_and_valid_tokens_are_reused(self):
        clock = [1000]
        stored = [None]
        counts = {'load': 0, 'login': 0, 'refresh': 0}
        def load():
            counts['load'] += 1
            return stored[0]
        def login():
            counts['login'] += 1
            stored[0] = Session('synthetic-first', clock[0]+3600)
            return stored[0]
        def refresh(previous):
            self.assertIs(previous, stored[0])
            counts['refresh'] += 1
            stored[0] = Session('synthetic-renewed', clock[0]+3600)
            return stored[0]
        manager = SessionManager(load, login=login, refresh=refresh, clock=lambda: clock[0])
        with ThreadPoolExecutor(max_workers=10) as executor:
            first = list(executor.map(manager, range(40)))
            self.assertTrue(all(session is first[0] for session in first))
            self.assertEqual(counts, {'load': 1, 'login': 1, 'refresh': 0})
            clock[0] += 3550
            renewed = list(executor.map(manager, range(40)))
        self.assertTrue(all(session is renewed[0] for session in renewed))
        self.assertEqual(counts, {'load': 2, 'login': 1, 'refresh': 1})

    def test_lost_refresh_is_fenced_for_every_waiting_caller(self):
        calls = []
        def refresh(previous):
            calls.append(previous)
            raise OutcomeUnknown('Original refresh reply lost')
        manager = SessionManager(lambda: Session('expired', 0), refresh=refresh)
        results = UploadPool().run(lambda _: manager(), range(20))
        self.assertEqual(len(calls), 1)
        self.assertTrue(all(isinstance(row.error, OutcomeUnknown) for row in results))
        fresh = Session('reconciled', time.time()+3600)
        manager.replace(fresh)
        self.assertIs(manager(), fresh)

    def test_another_owners_rotated_token_is_adopted_without_refresh(self):
        clock = [1000]
        stored = [Session('first', 1100)]
        manager = SessionManager(lambda: stored[0], clock=lambda: clock[0])
        manager()
        clock[0] += 50
        stored[0] = Session('renewed-by-owner', 4700)
        self.assertIs(manager(), stored[0])

    def test_http_openers_are_per_thread_and_invalid_limits_are_rejected(self):
        transport = HttpTransport()
        barrier = threading.Barrier(4)
        def opener(_):
            value = transport.opener
            barrier.wait(timeout=5)
            return value
        with ThreadPoolExecutor(max_workers=4) as executor:
            values = list(executor.map(opener, range(4)))
        self.assertEqual(len({id(value) for value in values}), 4)
        for value in (0, -1, True, 1.5, 65):
            with self.assertRaises(ValueError):
                UploadPool(value)

    def test_rate_limit_exposes_actual_cooldown_without_retry(self):
        with self.assertRaises(ProviderError) as caught:
            require_success(Response(429, {}, {'retry-after':'720'}))
        self.assertEqual(caught.exception.retry_after, 720)

    def test_overlapping_batches_share_the_same_pool_ceiling(self):
        pool=UploadPool(3)
        barrier=threading.Barrier(3)
        lock=threading.Lock()
        active=peak=0
        def operation(index):
            nonlocal active,peak
            with lock:
                active+=1;peak=max(peak,active)
            barrier.wait(timeout=5)
            with lock:active-=1
            return index
        with ThreadPoolExecutor(max_workers=2) as executor:
            batches=[executor.submit(pool.run,operation,range(6)) for _ in range(2)]
            for batch in batches:
                self.assertTrue(all(row.error is None for row in batch.result()))
        self.assertEqual(peak,3)

    def test_changed_session_is_verified_before_any_write_reservation(self):
        first=Session('original',time.time()+3600)
        changed=Session('different-account',time.time()+3600)
        current=[first]
        calls=[]
        class Transport:
            def execute(self,method,url,**kwargs):
                calls.append(method)
                self_token=kwargs['headers']['Authorization']
                email='owner@example.test' if self_token.endswith('original') else 'other@example.test'
                return Response(200,{'email':email})
        client=Client(first,transport=Transport(),expected_email='owner@example.test',session_provider=lambda _:current[0])
        client.verify_account();current[0]=changed
        admissions=[]
        with self.assertRaises(ValueError):
            client.rest('episode.update',web_episode_id(1),body={'title':'Example'},before_dispatch=admissions.append)
        self.assertEqual(calls,['GET','GET'])
        self.assertEqual(admissions,[])


if __name__ == '__main__':
    unittest.main()
