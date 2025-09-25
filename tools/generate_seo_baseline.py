#!/usr/bin/env python3
"""Generate SEO baseline data for nlping.ru content.

The script walks through the legacy mirror stored in the nlping.ru/
folder, extracts core SEO fields (title, description, keywords, first
H1) from HTML files, and captures channel metadata from XML feeds.

By default the result is written as a gzip-compressed JSON file to
``snapshot/seo_baseline.json.gz`` so the repository does not carry a
massive text artifact. Use ``--output``/``--no-gzip`` to override.
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
CONTENT_ROOT = ROOT / "nlping.ru"
DEFAULT_OUTPUT_PATH = ROOT / "snapshot" / "seo_baseline.json.gz"


class SeoHTMLParser(HTMLParser):
    """Collect basic SEO fields from an HTML document."""

    def __init__(self) -> None:
        super().__init__()
        self._capture_title = False
        self._capture_h1 = False
        self.title_parts: List[str] = []
        self.h1_parts: List[str] = []
        self.meta: Dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs):
        tag_lower = tag.lower()
        if tag_lower == "title":
            self._capture_title = True
        elif tag_lower == "h1" and not self.h1_parts:
            self._capture_h1 = True
        elif tag_lower == "meta":
            attr_dict = {k.lower(): (v or "") for k, v in attrs}
            name = attr_dict.get("name") or attr_dict.get("property")
            content = attr_dict.get("content")
            if name and content:
                name_lower = name.lower()
                if name_lower in {
                    "description",
                    "keywords",
                    "og:title",
                    "og:description",
                    "twitter:title",
                    "twitter:description",
                }:
                    self.meta[name_lower] = content

    def handle_endtag(self, tag: str):
        tag_lower = tag.lower()
        if tag_lower == "title":
            self._capture_title = False
        elif tag_lower == "h1" and self._capture_h1:
            self._capture_h1 = False

    def handle_data(self, data: str):
        if self._capture_title:
            self.title_parts.append(data)
        if self._capture_h1:
            self.h1_parts.append(data)

    def result(self) -> Dict[str, Optional[str]]:
        def clean(parts: List[str]) -> Optional[str]:
            joined = "".join(parts).strip()
            return joined or None

        return {
            "title": clean(self.title_parts),
            "h1": clean(self.h1_parts),
            "meta": self.meta,
        }


@dataclass
class HtmlRecord:
    path: str
    title: Optional[str]
    h1: Optional[str]
    meta: Dict[str, str]


@dataclass
class XmlRecord:
    path: str
    title: Optional[str]
    description: Optional[str]


def decode_bytes(data: bytes) -> str:
    """Decode bytes using CP1251 fallback to UTF-8."""
    for encoding in ("cp1251", "utf-8"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    # Last resort: replace errors using cp1251
    return data.decode("cp1251", errors="replace")


def parse_html(path: Path) -> Optional[HtmlRecord]:
    parser = SeoHTMLParser()
    raw = path.read_bytes()
    text = decode_bytes(raw)
    parser.feed(text)
    parser.close()
    info = parser.result()
    if not any((info["title"], info["h1"], info["meta"])):
        return None
    return HtmlRecord(
        path=path.as_posix(),
        title=info["title"],
        h1=info["h1"],
        meta=info["meta"],
    )


def parse_xml(path: Path) -> Optional[XmlRecord]:
    raw = path.read_bytes()
    text = decode_bytes(raw)
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None
    channel = root.find("channel") or root
    title_elem = channel.findtext("title")
    description_elem = channel.findtext("description")
    if title_elem is None and description_elem is None:
        return None
    return XmlRecord(
        path=path.as_posix(),
        title=title_elem.strip() if title_elem else None,
        description=description_elem.strip() if description_elem else None,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Where to write the baseline (default: snapshot/seo_baseline.json.gz)",
    )
    parser.add_argument(
        "--no-gzip",
        action="store_true",
        help="Force plain JSON even if the output file ends with .gz",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Write compact JSON without indentation",
    )
    return parser.parse_args()


def dump_payload(payload: Dict[str, object], output_path: Path, *, pretty: bool, force_plain: bool) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    json_text = json.dumps(payload, ensure_ascii=False, indent=None if not pretty else 2)
    compress = not force_plain and output_path.suffix == ".gz"
    if compress:
        with gzip.open(output_path, "wt", encoding="utf-8") as handle:
            handle.write(json_text)
    else:
        output_path.write_text(json_text, encoding="utf-8")


def main() -> int:
    args = parse_args()
    if not CONTENT_ROOT.exists():
        print(f"Content folder {CONTENT_ROOT} not found", file=sys.stderr)
        return 1

    html_records: List[HtmlRecord] = []
    xml_records: List[XmlRecord] = []

    for path in sorted(CONTENT_ROOT.rglob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix in {".html", ".htm", ".xhtml"}:
            record = parse_html(path)
            if record:
                html_records.append(record)
        elif suffix in {".xml", ".rss", ".atom"}:
            record = parse_xml(path)
            if record:
                xml_records.append(record)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(CONTENT_ROOT.as_posix()),
        "html": [asdict(r) for r in html_records],
        "feeds": [asdict(r) for r in xml_records],
    }
    dump_payload(payload, args.output, pretty=not args.compact, force_plain=args.no_gzip)
    print(
        "Captured {html} HTML records and {xml} XML records into {path}".format(
            html=len(html_records), xml=len(xml_records), path=args.output
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
