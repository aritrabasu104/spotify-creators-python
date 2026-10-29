"""Bounded foreground batches and single-flight, caller-owned authentication."""

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
import threading
import time

from .auth import Session

DEFAULT_MAX_PARALLEL_UPLOADS = 10


def upload_limit(value):
    if type(value) is not int or not 1 <= value <= 64:
        raise ValueError("max_parallel_uploads must be an integer from 1 to 64")
    return value


@dataclass(frozen=True)
class UploadResult:
    """One input's outcome; a failed sibling never hides completed transfers."""

    index: int
    value: object = field(default=None, repr=False)
    error: Exception | None = field(default=None, repr=False)

    def result(self):
        if self.error is not None:
            raise self.error
        return self.value


class UploadPool:
    """At most ten operations by default, shared across calls on this pool.

    All started work settles before return. Results retain input order and
    individual exceptions. Nothing retries, stores credentials or runs detached.
    """

    def __init__(self, max_parallel_uploads=DEFAULT_MAX_PARALLEL_UPLOADS):
        self.max_parallel_uploads = upload_limit(max_parallel_uploads)
        self._slots = threading.BoundedSemaphore(self.max_parallel_uploads)
        self._local = threading.local()

    def _call(self, index, operation, item):
        with self._slots:
            self._local.active = True
            try:
                return UploadResult(index, value=operation(item))
            except Exception as exc:
                return UploadResult(index, error=exc)
            finally:
                self._local.active = False

    def run(self, operation, items):
        if not callable(operation):
            raise TypeError("Supply one operation for each input")
        if getattr(self._local, "active", False):
            raise RuntimeError("Do not nest batches on the same upload pool")
        iterator = enumerate(items)
        results = []
        with ThreadPoolExecutor(max_workers=self.max_parallel_uploads,
                                thread_name_prefix="spotify-upload") as executor:
            pending = set()
            exhausted = False
            while pending or not exhausted:
                while not exhausted and len(pending) < self.max_parallel_uploads:
                    try:
                        index, item = next(iterator)
                    except StopIteration:
                        exhausted = True
                        break
                    pending.add(executor.submit(self._call, index, operation, item))
                if pending:
                    settled, pending = wait(pending, return_when=FIRST_COMPLETED)
                    results.extend(future.result() for future in settled)
        return sorted(results, key=lambda result: result.index)


class SessionManager:
    """Reuse one session, serializing only login/load/refresh.

    Callbacks own secure persistence, identity checks and cross-process locks.
    A failed authentication callback is retained until ``replace`` supplies an
    explicitly reconciled session; concurrent callers cannot replay its grant.
    """

    def __init__(self, load, *, refresh=None, login=None, refresh_margin=60,
                 clock=time.time):
        if not callable(load) or not 0 <= refresh_margin <= 600:
            raise ValueError("Supply a session loader and a bounded refresh margin")
        self.load, self.refresh, self.login = load, refresh, login
        self.refresh_margin, self.clock = refresh_margin, clock
        self._lock = threading.RLock()
        self._session = None
        self._failure = None

    def _valid(self, session):
        return isinstance(session, Session) and session.expires_at - self.clock() > self.refresh_margin

    def __call__(self, current=None):
        with self._lock:
            if self._failure is not None:
                raise self._failure
            if self._valid(self._session):
                return self._session
            try:
                # Read the durable owner again before renewing: another process
                # may already have rotated the original pair.
                session = self.load()
                if session is None:
                    if self.login is None:
                        raise ValueError("Initial authorized sign-in is required")
                    session = self.login()
                elif not self._valid(session):
                    if self.refresh is None:
                        raise ValueError("The session requires an authorized token refresh")
                    session = self.refresh(session)
                if not self._valid(session):
                    raise ValueError("Authentication did not return a sufficiently valid session")
                self._session = session
                return session
            except Exception as exc:
                self._failure = exc
                raise

    def replace(self, session):
        """Adopt an explicitly reconciled session after an authentication failure."""
        with self._lock:
            if not self._valid(session):
                raise ValueError("Supply a reconciled, valid session")
            self._session, self._failure = session, None
