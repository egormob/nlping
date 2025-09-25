#!/usr/bin/env python3
"""Collect asset dependencies for HTML documents.

The script walks through provided scopes (files or directories) and inspects
HTML/XHTML files for linked assets (stylesheets, scripts, images, media, other
external resources). The resulting mapping is written to a JSON artifact that
will be used during structure refactors to ensure referenced files are moved
together with their dependants.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = PROJECT_ROOT / "artifacts" / "assets.json"
HTML_EXTENSIONS = {".html", ".htm", ".xhtml"}
REMOTE_PREFIXES = ("http://", "https://", "//", "mailto:", "tel:", "javascript:")


@dataclass
class AssetEntry:
    url: str
    resolved_path: Optional[str]
    exists: Optional[bool]
    category: str


class AssetCollector(HTMLParser):
    """HTML parser that collects asset references from HTML tags."""

    def __init__(self, html_path: Path) -> None:
        super().__init__(convert_charrefs=True)
        self.html_path = html_path
        self.assets: Dict[str, Set[Tuple[str, Optional[str], Optional[bool]]]] = defaultdict(set)

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        attr_map = {name.lower(): value for name, value in attrs if name}
        if tag == "link":
            href = attr_map.get("href")
            rel = (attr_map.get("rel") or "").lower()
            if href:
                if "stylesheet" in rel:
                    self._add_asset("stylesheets", href)
                elif any(token in rel for token in ("icon", "shortcut icon")):
                    self._add_asset("images", href)
                else:
                    self._add_asset("other", href)
        elif tag == "script":
            src = attr_map.get("src")
            if src:
                self._add_asset("scripts", src)
        elif tag in {"img", "iframe", "embed"}:
            src = attr_map.get("src")
            if src:
                category = "images" if tag == "img" else "embeds"
                self._add_asset(category, src)
            srcset = attr_map.get("srcset")
            if srcset:
                for candidate in _split_srcset(srcset):
                    self._add_asset("images", candidate)
            data_src = attr_map.get("data-src") or attr_map.get("data-original")
            if data_src:
                self._add_asset("images", data_src)
        elif tag in {"audio", "video", "source", "track"}:
            src = attr_map.get("src")
            if src:
                self._add_asset("media", src)
            srcset = attr_map.get("srcset")
            if srcset:
                for candidate in _split_srcset(srcset):
                    self._add_asset("media", candidate)
        elif tag == "object":
            data_attr = attr_map.get("data")
            if data_attr:
                self._add_asset("embeds", data_attr)

    def _add_asset(self, category: str, url: str) -> None:
        if not url:
            return
        url = url.strip()
        resolved_path, exists = resolve_local_path(self.html_path, url)
        self.assets[category].add((url, resolved_path, exists))

    def to_entries(self) -> Dict[str, List[AssetEntry]]:
        return {
            category: [
                AssetEntry(url=url, resolved_path=resolved, exists=exists, category=category)
                for url, resolved, exists in sorted(values)
            ]
            for category, values in sorted(self.assets.items())
        }


def _split_srcset(value: str) -> Iterable[str]:
    for candidate in value.split(","):
        url = candidate.strip().split()[0]
        if url:
            yield url


def resolve_local_path(html_path: Path, url: str) -> Tuple[Optional[str], Optional[bool]]:
    if url.startswith(REMOTE_PREFIXES):
        return None, None
    parsed = urlparse(url)
    if parsed.scheme or parsed.netloc:
        return None, None
    if parsed.path == "":
        return None, None
    raw_path = parsed.path
    candidate = (html_path.parent / raw_path).resolve()
    try:
        relative = candidate.relative_to(PROJECT_ROOT)
        exists = candidate.exists()
        return str(relative), exists
    except ValueError:
        return str(candidate), candidate.exists()


def iter_html_files(scopes: Iterable[Path]) -> Iterable[Path]:
    for scope in scopes:
        if scope.is_dir():
            for path in sorted(scope.rglob("*")):
                if path.suffix.lower() in HTML_EXTENSIONS and path.is_file():
                    yield path
        elif scope.is_file() and scope.suffix.lower() in HTML_EXTENSIONS:
            yield scope


def collect_assets(html_files: Iterable[Path]) -> Dict[str, Dict[str, List[AssetEntry]]]:
    report: Dict[str, Dict[str, List[AssetEntry]]] = {}
    for html_file in html_files:
        collector = AssetCollector(html_file)
        try:
            text = html_file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = html_file.read_text(encoding="cp1251", errors="replace")
        collector.feed(text)
        report[str(html_file.relative_to(PROJECT_ROOT))] = collector.to_entries()
    return report


def summarize(report: Dict[str, Dict[str, List[AssetEntry]]]) -> Dict[str, int]:
    summary: Dict[str, int] = defaultdict(int)
    for assets in report.values():
        for category, entries in assets.items():
            summary[category] += len(entries)
    return dict(summary)


def dump_report(report: Dict[str, Dict[str, List[AssetEntry]]], output_path: Path) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scopes": sorted(report.keys()),
        "files": {
            scope: {
                category: [asdict(entry) for entry in entries]
                for category, entries in assets.items()
            }
            for scope, assets in sorted(report.items())
        },
        "summary": summarize(report),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect asset dependencies for HTML documents.")
    parser.add_argument(
        "paths",
        nargs="*",
        default=["nlping.ru"],
        help="Files or directories to scan (default: nlping.ru)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path to write the JSON report (default: artifacts/assets.json)",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    scopes = [Path(p).resolve() if not Path(p).is_absolute() else Path(p) for p in args.paths]
    html_files = list(iter_html_files(scopes))
    if not html_files:
        print("No HTML files found for the provided scopes.", file=sys.stderr)
        return 1
    report = collect_assets(html_files)
    dump_report(report, args.output)
    print(f"Collected assets for {len(html_files)} HTML files → {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
