"""Read an authorized account. Supply token, expiry and expected email securely."""

import os

from spotify_creators import Client, Session


def main():
    session = Session(access_token=os.environ["SPOTIFY_ACCESS_TOKEN"],
                      expires_at=float(os.environ["SPOTIFY_TOKEN_EXPIRES_AT"]))
    client = Client(session, expected_email=os.environ["SPOTIFY_ACCOUNT_EMAIL"])
    client.verify_account()
    for show in client.all_shows()["showsForUser"]["shows"]:
        print(show["uri"], show["name"])


if __name__ == "__main__":
    main()
