#!/usr/bin/env python3
"""Validate encoding and SEO-critical fields for mirrored documents.

The script iterates over HTML (and XML) documents referenced either in the
URL manifest or via explicit filesystem scopes. For every document it:

* Ensures the file exists on disk and records the declared charset.
* Detects encoding issues such as UTF-8 replacement characters (�) or
  confusing double-encoding artefacts (`Ã`, `Ð`, `пїЅ`).
* Optionally performs an HTTP probe (HEAD with GET fallback) against a base
  URL to confirm the served ``Content-Type`` charset matches expectations.
* Compares ``<title>``, ``<meta name="description">`` and the first ``<h1>``
  against the offline SEO baseline produced by ``generate_seo_baseline.py``.

Results are written to ``logs/check_utf8-<timestamp>.json`` by default so the
report can be attached to roadmap entries and the progress journal.
"""
from __future__ import annotations

import argparse
import difflib
import gzip
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import ParseResult, quote, urlparse
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOOLS_ROOT = PROJECT_ROOT / "tools"
DEFAULT_MANIFEST = TOOLS_ROOT / "url_manifest.txt"
DEFAULT_BASELINE = PROJECT_ROOT / "snapshot" / "seo_baseline.json.gz"
DEFAULT_ROOT = PROJECT_ROOT / "nlping.ru"
LOG_DIR = PROJECT_ROOT / "logs"
HTML_EXTENSIONS = {".html", ".htm", ".xhtml"}
XML_EXTENSIONS = {".xml", ".rss", ".atom"}
TEXT_EXTENSIONS = HTML_EXTENSIONS | XML_EXTENSIONS


@dataclass
class HTTPProbe:
    url: str
    method: str
    status: Optional[int]
    ok: Optional[bool]
    content_type: Optional[str] = None
    error: Optional[str] = None


@dataclass
class SeoSnapshot:
    title: Optional[str]
    h1: Optional[str]
    meta: Dict[str, str]


@dataclass
class SeoComparison:
    field: str
    baseline: Optional[str]
    current: Optional[str]
    diff: Optional[str]


@dataclass
class DocumentReport:
    source: str
    path: str
    exists: bool
    declared_charset: Optional[str] = None
    detected_encoding: Optional[str] = None
    contains_replacement: bool = False
    contains_suspect_sequences: bool = False
    http: Optional[HTTPProbe] = None
    seo: SeoSnapshot = field(default_factory=lambda: SeoSnapshot(None, None, {}))
    baseline_available: bool = False
    comparisons: List[SeoComparison] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Path to URL manifest (default: tools/url_manifest.txt).",
    )
    parser.add_argument(
        "--scope",
        action="append",
        dest="scopes",
        default=None,
        help="Additional directories or files to inspect (can repeat).",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help="Root directory used to resolve manifest paths (default: nlping.ru).",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE,
        help="SEO baseline file produced by generate_seo_baseline.py (default: snapshot/seo_baseline.json.gz).",
    )
    parser.add_argument(
        "--base",
        type=str,
        help="Optional base URL for HTTP HEAD/GET probes (e.g. http://localhost:8787).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Timeout for HTTP requests in seconds (default: 10).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write JSON report to this location (default: logs/check_utf8-<timestamp>.json).",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Write the report without indentation (useful for large manifests).",
    )
    return parser


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def ensure_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path.resolve())


def normalize_manifest_path(root: Path, parsed: ParseResult, raw: str) -> Path:
    if parsed.scheme in {"http", "https"}:
        relative = parsed.path or "/"
    else:
        relative = raw
    relative = relative.strip()
    if not relative:
        relative = "/"
    if relative.startswith("http://") or relative.startswith("https://"):
        parsed_inner = urlparse(relative)
        relative = parsed_inner.path or "/"
    if not relative.startswith("/"):
        relative = "/" + relative
    if relative.endswith("/"):
        candidate = root / relative.lstrip("/") / "index.html"
    else:
        candidate = root / relative.lstrip("/")
    if candidate.is_dir():
        candidate = candidate / "index.html"
    return candidate


def manifest_targets(manifest_path: Path, root: Path) -> List[Tuple[str, Path, Optional[str]]]:
    targets: List[Tuple[str, Path, Optional[str]]] = []
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest file not found: {manifest_path}")
    for idx, line in enumerate(manifest_path.read_text(encoding="utf-8").splitlines(), start=1):
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        parsed = urlparse(raw)
        candidate = normalize_manifest_path(root, parsed, raw)
        request_path: Optional[str]
        if parsed.scheme in {"http", "https"}:
            request_path = parsed.path or "/"
            if parsed.params:
                request_path += f";{parsed.params}"
            if parsed.query:
                request_path += f"?{parsed.query}"
        else:
            request_path = "/" + raw.lstrip("/")
        source = f"manifest:{manifest_path.name}:{idx}"
        targets.append((source, candidate, request_path))
    return targets


def scope_targets(scopes: Iterable[Path]) -> List[Tuple[str, Path, Optional[str]]]:
    targets: List[Tuple[str, Path, Optional[str]]] = []
    for scope in scopes:
        if scope.is_dir():
            for path in sorted(scope.rglob("*")):
                if path.suffix.lower() in TEXT_EXTENSIONS and path.is_file():
                    relative = ensure_relative(path)
                    targets.append((f"scope:{relative}", path, "/" + relative.replace("\\", "/")))
        elif scope.is_file() and scope.suffix.lower() in TEXT_EXTENSIONS:
            relative = ensure_relative(scope)
            targets.append((f"scope:{relative}", scope, "/" + relative.replace("\\", "/")))
    return targets


def default_log_path() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return LOG_DIR / f"check_utf8-{timestamp}.json"


def build_http_url(base: str, path: Optional[str]) -> str:
    if not path:
        path = "/"
    if not path.startswith("/"):
        path = "/" + path
    base = base.rstrip("/")
    encoded = "/".join(quote(part) for part in path.split("/"))
    if not encoded.startswith("/"):
        encoded = "/" + encoded
    return base + encoded


def probe_http(base: str, request_path: Optional[str], timeout: float) -> HTTPProbe:
    url = build_http_url(base, request_path)
    last_error: Optional[str] = None
    for method in ("HEAD", "GET"):
        request = Request(url, method=method)
        try:
            with urlopen(request, timeout=timeout) as response:
                status = getattr(response, "status", response.getcode())
                content_type = response.headers.get("Content-Type") if hasattr(response, "headers") else None
                return HTTPProbe(url=url, method=method, status=status, ok=200 <= status < 400, content_type=content_type)
        except HTTPError as exc:
            content_type = exc.headers.get("Content-Type") if exc.headers else None
            if method == "HEAD" and exc.code in {405, 501}:
                last_error = str(exc)
                continue
            return HTTPProbe(url=url, method=method, status=exc.code, ok=False, content_type=content_type, error=str(exc))
        except URLError as exc:
            last_error = str(exc.reason) if hasattr(exc, "reason") else str(exc)
            if method == "HEAD":
                continue
            return HTTPProbe(url=url, method=method, status=None, ok=False, error=last_error)
    return HTTPProbe(url=url, method="GET", status=None, ok=False, error=last_error or "unknown error")


def detect_declared_charset(text: str) -> Optional[str]:
    lower = text.lower()
    search_area = lower[:4096]
    meta_pos = search_area.find("charset=")
    if meta_pos != -1:
        start = meta_pos + len("charset=")
        end = start
        while end < len(lower) and lower[end] not in {'"', "'", '>', ' ', ';'}:
            end += 1
        candidate = lower[start:end].strip()
        if candidate:
            return candidate
    return None


def decode_content(raw: bytes) -> Tuple[str, str]:
    for encoding in ("cp1251", "utf-8"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace"), "utf-8"


def detect_suspect_sequences(text: str, raw: bytes) -> bool:
    if "Ã" in text or "Ð" in text or "пїЅ" in text:
        return True
    if b"\xef\xbf\xbd" in raw:
        return True
    if "ï¿½" in text:
        return True
    return False


class SeoHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._capture_title = False
        self._capture_h1 = False
        self.title_parts: List[str] = []
        self.h1_parts: List[str] = []
        self.meta: Dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs):
        tag_lower = tag.lower()
        attrs_lower = {k.lower(): (v or "") for k, v in attrs if k}
        if tag_lower == "title":
            self._capture_title = True
        elif tag_lower == "h1" and not self.h1_parts:
            self._capture_h1 = True
        elif tag_lower == "meta":
            name = attrs_lower.get("name") or attrs_lower.get("property")
            content = attrs_lower.get("content")
            if name and content:
                name_lower = name.lower()
                if name_lower in {"description", "keywords", "og:title", "og:description", "twitter:title", "twitter:description"}:
                    self.meta[name_lower] = content.strip()

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

    def result(self) -> SeoSnapshot:
        def clean(parts: List[str]) -> Optional[str]:
            joined = "".join(parts).strip()
            return joined or None

        return SeoSnapshot(
            title=clean(self.title_parts),
            h1=clean(self.h1_parts),
            meta=self.meta,
        )


def extract_seo(text: str) -> SeoSnapshot:
    parser = SeoHTMLParser()
    parser.feed(text)
    parser.close()
    return parser.result()


def load_baseline(path: Path) -> Dict[str, SeoSnapshot]:
    if not path.exists():
        return {}
    if path.suffix == ".gz":
        opener = lambda p: gzip.open(p, "rt", encoding="utf-8")
    else:
        opener = lambda p: open(p, "rt", encoding="utf-8")
    baseline: Dict[str, SeoSnapshot] = {}
    with opener(path) as handle:
        payload = json.load(handle)
    for entry in payload.get("html", []):
        raw_path = Path(entry.get("path", ""))
        try:
            relative = raw_path.resolve().relative_to(PROJECT_ROOT)
        except ValueError:
            relative = raw_path
        snapshot = SeoSnapshot(
            title=entry.get("title"),
            h1=entry.get("h1"),
            meta={k: v for k, v in entry.get("meta", {}).items()},
        )
        baseline[str(relative)] = snapshot
    return baseline


def compare_seo(baseline: Optional[SeoSnapshot], current: SeoSnapshot) -> Tuple[List[SeoComparison], List[str]]:
    comparisons: List[SeoComparison] = []
    issues: List[str] = []

    def append(field: str, old: Optional[str], new: Optional[str]) -> None:
        if (old or "") == (new or ""):
            return
        diff = "\n".join(
            difflib.unified_diff(
                [old or ""],
                [new or ""],
                fromfile="baseline",
                tofile="current",
                lineterm="",
            )
        ) or None
        comparisons.append(SeoComparison(field=field, baseline=old, current=new, diff=diff))
        issues.append(f"seo_mismatch:{field}")

    if baseline is None:
        if any([current.title, current.h1, current.meta]):
            comparisons.append(SeoComparison(field="baseline", baseline=None, current=None, diff=None))
        return comparisons, issues

    append("title", baseline.title, current.title)
    append("h1", baseline.h1, current.h1)

    meta_keys = set(baseline.meta.keys()) | set(current.meta.keys())
    for key in sorted(meta_keys):
        append(f"meta:{key}", baseline.meta.get(key), current.meta.get(key))

    return comparisons, issues


def inspect_document(
    source: str,
    path: Path,
    request_path: Optional[str],
    baseline_map: Dict[str, SeoSnapshot],
    *,
    base: Optional[str],
    timeout: float,
) -> DocumentReport:
    relative_path = ensure_relative(path)
    report = DocumentReport(source=source, path=relative_path, exists=path.exists())
    if not report.exists:
        report.issues.append("missing_file")
        return report

    raw = path.read_bytes()
    text, detected_encoding = decode_content(raw)
    report.detected_encoding = detected_encoding
    report.declared_charset = detect_declared_charset(text)
    report.contains_replacement = "�" in text or "ï¿½" in text or b"\xef\xbf\xbd" in raw
    report.contains_suspect_sequences = detect_suspect_sequences(text, raw)

    if base:
        report.http = probe_http(base, request_path, timeout)
        if report.http and report.http.content_type:
            lowered = report.http.content_type.lower()
            if "charset=" in lowered:
                charset = lowered.split("charset=", 1)[1].split(";")[0].strip()
                if report.declared_charset and charset and charset != report.declared_charset:
                    report.issues.append("content_type_mismatch")
            else:
                report.issues.append("missing_charset_header")

    report.seo = extract_seo(text)
    baseline = baseline_map.get(relative_path)
    report.baseline_available = baseline is not None
    comparisons, seo_issues = compare_seo(baseline, report.seo)
    report.comparisons.extend(comparisons)
    report.issues.extend(seo_issues)

    return report


def summarise(reports: List[DocumentReport]) -> Dict[str, int]:
    summary: Dict[str, int] = {}
    for report in reports:
        summary.setdefault("total", 0)
        summary["total"] += 1
        if not report.exists:
            summary.setdefault("missing_file", 0)
            summary["missing_file"] += 1
        for issue in report.issues:
            summary.setdefault(issue, 0)
            summary[issue] += 1
        if report.contains_replacement:
            summary.setdefault("replacement_chars", 0)
            summary["replacement_chars"] += 1
        if report.contains_suspect_sequences:
            summary.setdefault("suspect_sequences", 0)
            summary["suspect_sequences"] += 1
    return summary


def dump_report(
    reports: List[DocumentReport],
    output_path: Path,
    *,
    compact: bool,
    manifest: Optional[Path],
    baseline: Optional[Path],
    base: Optional[str],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest": str(manifest) if manifest else None,
        "baseline": str(baseline) if baseline else None,
        "base_url": base,
        "summary": summarise(reports),
        "results": [
            {
                **{
                    "source": report.source,
                    "path": report.path,
                    "exists": report.exists,
                    "declared_charset": report.declared_charset,
                    "detected_encoding": report.detected_encoding,
                    "contains_replacement": report.contains_replacement,
                    "contains_suspect_sequences": report.contains_suspect_sequences,
                    "issues": report.issues,
                    "baseline_available": report.baseline_available,
                },
                **(
                    {"http": asdict(report.http)}
                    if report.http is not None
                    else {}
                ),
                "seo": asdict(report.seo),
                "comparisons": [asdict(comp) for comp in report.comparisons],
            }
            for report in reports
        ],
    }
    json_text = json.dumps(payload, ensure_ascii=False, indent=None if compact else 2)
    output_path.write_text(json_text, encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    manifest_path: Optional[Path] = args.manifest
    reports: List[DocumentReport] = []

    try:
        baseline_map = load_baseline(args.baseline)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Failed to load baseline {args.baseline}: {exc}", file=sys.stderr)
        baseline_map = {}

    targets: List[Tuple[str, Path, Optional[str]]] = []
    if manifest_path:
        try:
            targets.extend(manifest_targets(manifest_path, args.root))
        except FileNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    if args.scopes:
        extra = [Path(scope) for scope in args.scopes]
        targets.extend(scope_targets(extra))

    if not targets:
        print("No targets resolved — provide --manifest or --scope entries.", file=sys.stderr)
        return 1

    for source, path, request_path in targets:
        report = inspect_document(
            source,
            path,
            request_path,
            baseline_map,
            base=args.base,
            timeout=args.timeout,
        )
        reports.append(report)

    output_path = args.output or default_log_path()
    try:
        dump_report(
            reports,
            output_path,
            compact=args.compact,
            manifest=manifest_path,
            baseline=args.baseline,
            base=args.base,
        )
    except OSError as exc:
        print(f"Failed to write report to {output_path}: {exc}", file=sys.stderr)
        return 1

    print(f"Report written to {output_path}")
    summary = summarise(reports)
    if summary.get("missing_file") or summary.get("content_type_mismatch") or summary.get("replacement_chars"):
        return 1
    if any(key.startswith("seo_mismatch:") for key in summary):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
