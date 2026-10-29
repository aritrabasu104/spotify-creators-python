"""Update one episode with an application-owned SQLite intent reservation."""

import argparse
from contextlib import closing
import os
import sqlite3

from spotify_creators import Client, Session


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("episode_id")
    parser.add_argument("title")
    parser.add_argument("--intent-db", required=True)
    args = parser.parse_args(argv)
    session = Session(access_token=os.environ["SPOTIFY_ACCESS_TOKEN"],
                      expires_at=float(os.environ["SPOTIFY_TOKEN_EXPIRES_AT"]))
    client = Client(session, expected_email=os.environ["SPOTIFY_ACCOUNT_EMAIL"])
    client.verify_account()

    with closing(sqlite3.connect(args.intent_db)) as db:
        db.execute("CREATE TABLE IF NOT EXISTS intents (digest TEXT PRIMARY KEY, operation TEXT, state TEXT)")
        db.commit()
        reserved = []

        def reserve(intent):
            # The unique digest refuses a repeat of the same unresolved write.
            with db:
                db.execute("INSERT INTO intents VALUES (?, ?, 'dispatched')",
                           (intent["request_sha256"], intent["operation"]))
            reserved.append(intent["request_sha256"])

        client.update_episode(args.episode_id, {"title": args.title}, before_dispatch=reserve)
        saved = client.get_episode(args.episode_id)
        if saved.get("title") != args.title:
            raise RuntimeError("Keep the original intent; saved copy is not yet confirmed")
        with db:
            db.execute("UPDATE intents SET state='verified' WHERE digest=? AND state='dispatched'",
                       (reserved[0],))
        print("Saved episode title verified")


if __name__ == "__main__":
    main()
