#!/usr/bin/env python3
"""Release helpers for .github/workflows/release.yml (issue #86).

    check_release_version.py check TAG VERSION
        Exit 1 unless TAG is exactly ``v`` + VERSION (e.g. ``v1.3.0`` / ``1.3.0``).
    check_release_version.py notes TAG [RELEASE_NOTES.md]
        Print the body of the ``## TAG …`` section of the release notes;
        exit 1 if there is none.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence
from pathlib import Path


def tag_matches_version(tag: str, version: str) -> bool:
    """True when the pushed tag names exactly this package version."""
    return tag == f"v{version}"


def extract_release_notes(text: str, tag: str) -> str:
    """Return the body of the ``## <tag>`` section, up to the next ``## `` heading."""
    heading = re.compile(rf"^## {re.escape(tag)}(?=\s|$).*$", re.MULTILINE)
    match = heading.search(text)
    if match is None:
        raise LookupError(f"no '## {tag}' section in the release notes")
    rest = text[match.end() :]
    following = re.search(r"^## ", rest, re.MULTILINE)
    return (rest[: following.start()] if following else rest).strip() + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="tag must equal v<version>")
    check.add_argument("tag")
    check.add_argument("version")
    notes = sub.add_parser("notes", help="print the release notes section for a tag")
    notes.add_argument("tag")
    notes.add_argument("path", nargs="?", default="RELEASE_NOTES.md", type=Path)
    args = parser.parse_args(argv)

    if args.command == "check":
        if tag_matches_version(args.tag, args.version):
            print(f"tag {args.tag} matches package version {args.version}")
            return 0
        print(
            f"error: tag {args.tag} does not match package version {args.version} "
            f"(expected v{args.version}); bump __version__ or fix the tag",
            file=sys.stderr,
        )
        return 1

    try:
        sys.stdout.write(extract_release_notes(args.path.read_text(encoding="utf-8"), args.tag))
    except LookupError as e:
        print(f"error: {e} ({args.path})", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
