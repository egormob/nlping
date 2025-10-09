#!/usr/bin/env python3
"""Validate local and served links for HTML documents.

The script walks over HTML files discovered either from a filesystem scope
(`--scope`) or a manifest of URLs (`--manifest`). For every HTML document it
verifies that the file exists, inspects referenced assets (stylesheets,
scripts, images, media, embeds) and optionally performs HTTP status checks via
a base URL (local server, Cloudflare Pages preview, etc.).

Results are written to a timestamped JSON log under ``logs/`` so each run can
be attached to a roadmap entry or progress journal.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import ParseResult, quote, urlparse
from urllib.request import Request, urlopen

from list_assets import (  # type: ignore
    AssetCollector,
    AssetEntry,
    PROJECT_ROOT,
    iter_html_files,
)

LOG_DIR = PROJECT_ROOT / "logs"
DEFAULT_SCOPE = PROJECT_ROOT


@dataclass
class HTTPCheck:
    url: str
    status: Optional[int]
    ok: Optional[bool]
    error: Optional[str] = None


@dataclass
class AssetCheck:
    url: str
    category: str
    resolved_path: Optional[str]
    exists: Optional[bool]
    http: Optional[HTTPCheck]
    status: str
    request_path: Optional[str]


@dataclass
class DocumentCheck:
    source: str
    path: str
    request_path: Optional[str]
    exists: bool
    http: Optional[HTTPCheck]
    assets: List[AssetCheck] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)


def default_log_path() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return LOG_DIR / f"check_links-{timestamp}.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check local HTML files and their asset links."
    )
    parser.add_argument(
        "--scope",
        action="append",
        dest="scopes",
        default=None,
        help="Directory or HTML file to analyse (can be used multiple times).",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help="File with URLs or relative paths to validate.",
    )
    parser.add_argument(
        "--base",
        type=str,
        help="Base URL for HTTP checks (e.g. http://localhost:8000).",
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
        help="Write detailed JSON report to this path (default: logs/check_links-<timestamp>.json).",
    )
    parser.add_argument(
        "--request-plan",
        type=Path,
        help="Write a JSON file listing document and asset HTTP requests to execute remotely.",
    )
    parser.add_argument(
        "--request-plan-format",
        choices=["json", "jsonl"],
        default="json",
        help="Format for the request plan output (default: json).",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_SCOPE,
        help="Root directory used to resolve manifest paths (default: project root).",
    )
    parser.add_argument(
        "--include-remote",
        action="store_true",
        help="Also perform HTTP checks for remote (absolute) asset URLs.",
    )
    return parser


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args


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
    html_files = list(iter_html_files(scopes))
    for html in html_files:
        relative = ensure_relative(html)
        request_path = "/" + relative.replace("\\", "/")
        targets.append((f"scope:{relative}", html, request_path))
    return targets


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


def try_http(url: str, timeout: float) -> HTTPCheck:
    request = Request(url, method="HEAD")
    try:
        with urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", response.getcode())
            return HTTPCheck(url=url, status=status, ok=200 <= status < 400)
    except HTTPError as exc:
        if exc.code in {405, 501}:
            get_request = Request(url, method="GET")
            try:
                with urlopen(get_request, timeout=timeout) as response:
                    status = getattr(response, "status", response.getcode())
                    return HTTPCheck(url=url, status=status, ok=200 <= status < 400)
            except Exception as inner_exc:  # pragma: no cover - defensive branch
                return HTTPCheck(url=url, status=None, ok=False, error=str(inner_exc))
        return HTTPCheck(url=url, status=exc.code, ok=False, error=str(exc))
    except URLError as exc:
        return HTTPCheck(url=url, status=None, ok=False, error=str(exc.reason))
    except Exception as exc:  # pragma: no cover - unexpected errors
        return HTTPCheck(url=url, status=None, ok=False, error=str(exc))


def load_assets(html_path: Path) -> Dict[str, List[AssetEntry]]:
    collector = AssetCollector(html_path)
    try:
        text = html_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = html_path.read_text(encoding="cp1251", errors="replace")
    collector.feed(text)
    return collector.to_entries()


def analyse_documents(
    targets: Sequence[Tuple[str, Path, Optional[str]]],
    base_url: Optional[str],
    timeout: float,
    include_remote: bool,
) -> List[DocumentCheck]:
    seen: Dict[str, DocumentCheck] = {}
    for source, path, request_path in targets:
        key = ensure_relative(path)
        doc = seen.get(key)
        if doc is None:
            http_result = try_http(build_http_url(base_url, request_path), timeout) if base_url else None
            doc = DocumentCheck(
                source=source,
                path=key,
                request_path=request_path,
                exists=path.exists(),
                http=http_result,
            )
            if not doc.exists:
                doc.issues.append("missing_file")
            if http_result and not (http_result.ok or http_result.status is None):
                doc.issues.append("http_error")
            seen[key] = doc
        else:
            # If we already saw the document but had no HTTP path earlier, try now.
            if doc.request_path is None and request_path is not None:
                doc.request_path = request_path
            if base_url and doc.http is None and request_path is not None:
                doc.http = try_http(build_http_url(base_url, request_path), timeout)
                if doc.http and not (doc.http.ok or doc.http.status is None):
                    doc.issues.append("http_error")

        if not path.exists():
            continue

        if doc.assets:
            # Assets already analysed for this document (avoid duplicates when
            # the same path appears from multiple sources).
            continue

        asset_map = load_assets(path)
        for category, entries in asset_map.items():
            for entry in entries:
                asset_http: Optional[HTTPCheck] = None
                status = "ok"
                if entry.resolved_path is None:
                    asset_request_path: Optional[str] = entry.url
                    if include_remote:
                        asset_http = try_http(entry.url, timeout)
                        if asset_http.ok is False:
                            status = "http_error"
                            doc.issues.append("asset_http_error")
                    else:
                        status = "skipped_remote"
                else:
                    if entry.exists is False:
                        status = "missing_file"
                        doc.issues.append("missing_asset")
                    asset_request_path = "/" + entry.resolved_path.replace("\\", "/")
                    if base_url:
                        asset_url = build_http_url(base_url, asset_request_path)
                        asset_http = try_http(asset_url, timeout)
                        if asset_http.ok is False:
                            status = "http_error"
                            doc.issues.append("asset_http_error")
                doc.assets.append(
                    AssetCheck(
                        url=entry.url,
                        category=category,
                        resolved_path=entry.resolved_path,
                        exists=entry.exists,
                        http=asset_http,
                        status=status,
                        request_path=asset_request_path,
                    )
                )
    return list(seen.values())


def summarise(documents: Sequence[DocumentCheck]) -> Dict[str, int]:
    summary = {
        "documents": len(documents),
        "documents_missing": 0,
        "documents_http_errors": 0,
        "assets_total": 0,
        "assets_missing": 0,
        "assets_http_errors": 0,
    }
    for doc in documents:
        if "missing_file" in doc.issues:
            summary["documents_missing"] += 1
        if "http_error" in doc.issues:
            summary["documents_http_errors"] += 1
        summary["assets_total"] += len(doc.assets)
        for asset in doc.assets:
            if asset.status == "missing_file":
                summary["assets_missing"] += 1
            if asset.status == "http_error":
                summary["assets_http_errors"] += 1
    return summary


def dump_report(
    documents: Sequence[DocumentCheck],
    output_path: Path,
    base_url: Optional[str],
    sources: Sequence[str],
) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "sources": list(sources),
        "summary": summarise(documents),
        "documents": [
            {
                "source": doc.source,
                "path": doc.path,
                "request_path": doc.request_path,
                "exists": doc.exists,
                "http": asdict(doc.http) if doc.http else None,
                "issues": doc.issues,
                "assets": [
                    {
                        "url": asset.url,
                        "category": asset.category,
                        "resolved_path": asset.resolved_path,
                        "exists": asset.exists,
                        "status": asset.status,
                        "http": asdict(asset.http) if asset.http else None,
                        "request_path": asset.request_path,
                    }
                    for asset in doc.assets
                ],
            }
            for doc in documents
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def normalise_request_url(path: Optional[str], base_url: Optional[str]) -> Optional[str]:
    if path is None:
        return None
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if base_url:
        return build_http_url(base_url, path)
    return path


def build_request_plan(
    documents: Sequence[DocumentCheck],
    base_url: Optional[str],
) -> List[Dict[str, object]]:
    plan: List[Dict[str, object]] = []
    seen: Set[Tuple[str, str]] = set()

    for doc in documents:
        request_path = doc.request_path or "/" + doc.path.replace("\\", "/")
        url = normalise_request_url(request_path, base_url)
        if url:
            key = ("document", url)
            if key not in seen:
                seen.add(key)
                plan.append(
                    {
                        "type": "document",
                        "document": doc.path,
                        "path": request_path,
                        "url": url,
                        "issues": list(doc.issues),
                    }
                )
        for asset in doc.assets:
            asset_path = asset.request_path
            asset_url = normalise_request_url(asset_path, base_url)
            if not asset_url:
                continue
            key = ("asset", asset_url)
            if key in seen:
                continue
            seen.add(key)
            plan.append(
                {
                    "type": "asset",
                    "document": doc.path,
                    "category": asset.category,
                    "original_url": asset.url,
                    "path": asset_path
                    if asset_path and not asset_path.startswith(("http://", "https://"))
                    else None,
                    "url": asset_url,
                    "status": asset.status,
                }
            )
    return plan


def dump_request_plan(
    plan: Sequence[Dict[str, object]],
    output_path: Path,
    base_url: Optional[str],
    fmt: str,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "jsonl":
        metadata = {
            "type": "metadata",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "base_url": base_url,
            "total_requests": len(plan),
        }
        lines = [json.dumps(metadata, ensure_ascii=False)]
        lines.extend(json.dumps(item, ensure_ascii=False) for item in plan)
        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "total_requests": len(plan),
        "requests": list(plan),
    }
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    scopes: List[Path]
    if args.scopes:
        scopes = [Path(scope) for scope in args.scopes]
    else:
        scopes = [DEFAULT_SCOPE]

    targets: List[Tuple[str, Path, Optional[str]]] = []
    target_sources: List[str] = []

    if args.manifest:
        manifest_entries = manifest_targets(args.manifest, args.root)
        targets.extend(manifest_entries)
        target_sources.append(f"manifest:{args.manifest}")

    if scopes:
        scope_entries = scope_targets(scopes)
        targets.extend(scope_entries)
        target_sources.extend([ensure_relative(Path(scope).resolve()) for scope in scopes])

    if not targets:
        print("No HTML documents found for provided inputs.", file=sys.stderr)
        return 1

    documents = analyse_documents(
        targets=targets,
        base_url=args.base,
        timeout=args.timeout,
        include_remote=args.include_remote,
    )

    output_path = args.output or default_log_path()
    dump_report(documents, output_path, args.base, target_sources)

    if args.request_plan:
        plan = build_request_plan(documents, args.base)
        dump_request_plan(plan, args.request_plan, args.base, args.request_plan_format)

    summary = summarise(documents)
    print(
        "Checked {documents} documents (missing={documents_missing}, http_errors={documents_http_errors},"
        " assets={assets_total}, missing_assets={assets_missing}, asset_http_errors={assets_http_errors})"
        .format(**summary)
    )
    print(f"Report saved to {output_path}")
    return 0 if summary["documents_missing"] == 0 and summary["documents_http_errors"] == 0 and summary["assets_missing"] == 0 and summary["assets_http_errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
