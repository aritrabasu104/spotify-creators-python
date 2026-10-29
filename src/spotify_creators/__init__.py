"""Independent Spotify Creators client. See docs for authentication and writes."""

from .auth import AuthClient, OAuthAttempt, Session
from .catalog import INVENTORY, OPERATIONS
from .client import GraphError, SpotifyClient
from .endpoints import ENDPOINTS
from .http import HttpTransport, OutcomeUnknown, ProviderError
from .media import UploadTarget, upload_exact, upload_multipart
from .tasks import CreatorsTasks
from .protocol import web_episode_id

__version__ = "0.1.0"


class Client(SpotifyClient):
    """Convenient client with bundled operation contracts and task methods.

    Call ``verify_account()`` before a write. Every write also needs a
    ``before_dispatch`` callback that reserves the intent in your application.
    """

    def __init__(self, session, *, expected_email=None, transport=None,
                 session_provider=None, inventory=None):
        super().__init__(transport or HttpTransport(), session,
                         INVENTORY if inventory is None else inventory,
                         expected_email=expected_email, session_provider=session_provider)
        self.tasks = CreatorsTasks(self)

    def get_show(self, show_id):
        """Read show metadata using its Spotify base62 ID."""
        identifiers = self.tasks.legacy_show(show_id)
        return self.tasks.metadata(identifiers["webStationId"])

    def get_episode(self, episode_id):
        """Read episode metadata using its Spotify base62 ID."""
        resolved = self.tasks.resolve_episode(episode_id)
        return self.tasks.episode(web_episode_id(int(resolved["episodeId"])))

    def list_episodes(self, show_id, *, max_pages=500):
        """Return a complete, validated episode census for one show."""
        return self.tasks.all_episodes(show_id, max_pages=max_pages)

    def update_episode(self, episode_id, fields, *, before_dispatch):
        """Update the specified episode; the callback reserves this write once."""
        original = self.get_episode(episode_id)
        return self.tasks.update_episode(original["webEpisodeId"], original["userId"],
                                         fields, before_dispatch=before_dispatch)


__all__ = ["Client", "SpotifyClient", "CreatorsTasks", "Session", "OAuthAttempt",
           "AuthClient", "HttpTransport", "ProviderError", "GraphError", "OutcomeUnknown",
           "UploadTarget", "upload_exact", "upload_multipart", "ENDPOINTS", "OPERATIONS"]
