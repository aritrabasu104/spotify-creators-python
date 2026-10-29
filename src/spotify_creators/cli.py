"""Print package information or public API contracts; never read credentials."""

import argparse
import json

from . import ENDPOINTS, OPERATIONS, __version__


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("command", choices=["list-apis"])
    args = parser.parse_args(argv)
    if args.command == "list-apis":
        print(json.dumps({"rest": [{"id": r[0], "method": r[1], "path": r[2],
                                   "fields": r[3].split()} for r in ENDPOINTS],
                          "graphql": OPERATIONS}, indent=2))
    return 0
