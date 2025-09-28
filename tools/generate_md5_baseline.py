#!/usr/bin/env python3
"""Generate a compressed MD5 checksum baseline for the site mirror."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = ROOT
DEFAULT_OUTPUT = ROOT / "snapshot" / "baseline_md5.txt.gz"


def iter_files(source: Path) -> Iterable[Path]:
    for path in sorted(source.rglob("*")):
        if path.is_file():
            yield path


def md5sum(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def open_output(path: Path, compress: bool):
    path.parent.mkdir(parents=True, exist_ok=True)
    if compress:
        return gzip.open(path, "wt", encoding="utf-8")
    return path.open("w", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help="Root directory to hash (default: project root)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Where to write the baseline (default: snapshot/baseline_md5.txt.gz)",
    )
    parser.add_argument(
        "--no-gzip",
        action="store_true",
        help="Write plain text instead of gzip if set",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = args.source
    if not source.exists():
        print(f"Source directory {source} not found", file=sys.stderr)
        return 1

    compress = not args.no_gzip and args.output.suffix == ".gz"
    total = 0
    with open_output(args.output, compress) as handle:
        for path in iter_files(source):
            digest = md5sum(path)
            rel_path = path.relative_to(ROOT).as_posix()
            handle.write(f"{digest}  {rel_path}\n")
            total += 1

    print(f"Captured {total} files into {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
