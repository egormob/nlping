"""Utilities for converting legacy HTML/XML files to UTF-8.

The HTTrack snapshot keeps most of the content in Windows-1251.  This
script walks through the provided paths, detects the current encoding and
rewrites files in UTF-8 while storing a detailed JSON log for auditing.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Iterator, List, Optional

try:
    import chardet
except ImportError:  # pragma: no cover - fallback in test environment
    chardet = None


SUPPORTED_SUFFIXES = {".html", ".htm", ".xml", ".xhtml"}
DEFAULT_LIMIT = 150

WINDOWS_1251_HINTS = (
    b"charset=windows-1251",
    rb"charset\u003dwindows-1251",
    b"charset = windows-1251",
    b"encoding=\"windows-1251\"",
    b"encoding='windows-1251'",
)


@dataclass
class FileReport:
    """The outcome of a single file processing step."""

    path: str
    status: str
    original_encoding: Optional[str] = None
    detected_encoding: Optional[str] = None
    original_hash: Optional[str] = None
    new_hash: Optional[str] = None
    error: Optional[str] = None


def discover_files(paths: Iterable[Path]) -> Iterator[Path]:
    """Yield candidate files within the provided paths."""

    for path in paths:
        if path.is_dir():
            for child in sorted(path.rglob("*")):
                if child.is_file() and child.suffix.lower() in SUPPORTED_SUFFIXES:
                    yield child
        elif path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
            yield path


def _canonicalise(encoding: str) -> str:
    normalized = encoding.lower().replace("-sig", "")
    if normalized in {"cp1251", "windows1251", "windows_1251"}:
        return "windows-1251"
    if normalized in {"utf8", "utf_8"}:
        return "utf-8"
    return normalized


def detect_encoding(data: bytes) -> Optional[str]:
    """Return the best-effort encoding for the given payload."""

    if not data:
        return None

    # UTF-8 BOM
    if data.startswith(b"\xef\xbb\xbf"):
        return "utf-8"

    try:
        data.decode("utf-8", errors="strict")
        return "utf-8"
    except UnicodeDecodeError:
        pass

    if chardet is not None:
        result = chardet.detect(data)
        encoding = result.get("encoding")
        if encoding:
            return _canonicalise(encoding)

    for candidate in ("windows-1251", "koi8-r", "iso-8859-5"):
        try:
            data.decode(candidate, errors="strict")
            return candidate
        except UnicodeDecodeError:
            continue
    return None


def _maybe_decode_double_encoded(payload: bytes) -> Optional[str]:
    """Best-effort recovery for UTF-8 payloads with Windows-1251 hints.

    HTTrack occasionally produced files where Windows-1251 bytes were first
    interpreted as Latin-1 characters and *then* stored as UTF-8.  Such pages
    already pass a strict UTF-8 decoder but contain mojibake ("Ã\xadÃ\x8bÃ\x8f" вместо
    «НЛП»).  When a file advertises `charset=windows-1251` we attempt to
    reverse this by:

    1. Decoding the payload as UTF-8 to get the mojibake string.
    2. Re-encoding that string as Latin-1, returning to the original byte
       values.
    3. Decoding the bytes as Windows-1251 to obtain real Cyrillic text.

    If any of these steps fail, or the resulting text does not contain Cyrillic
    characters, the function returns ``None`` to let the regular UTF-8 path
    proceed unchanged.
    """

    lowered = payload.lower()
    if not any(hint in lowered for hint in WINDOWS_1251_HINTS):
        return None

    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return None

    try:
        raw_bytes = text.encode("latin1")
    except UnicodeEncodeError:
        # Some double-encoded documents contain punctuation such as en-dash
        # (`\u2013`) that falls outside of Latin-1.  When that happens we fall
        # back to a per-character conversion: treat every code point within the
        # 0-255 range as if it were a Windows-1251 byte while leaving genuine
        # Unicode characters intact.
        recovered_chars = []
        changed = False
        for char in text:
            code = ord(char)
            if code <= 0xFF:
                try:
                    decoded_char = bytes([code]).decode("windows-1251")
                except UnicodeDecodeError:
                    decoded_char = char
                if decoded_char != char:
                    changed = True
                recovered_chars.append(decoded_char)
            else:
                recovered_chars.append(char)
        if not changed:
            return None
        recovered = "".join(recovered_chars)
    else:
        try:
            recovered = raw_bytes.decode("windows-1251")
        except UnicodeDecodeError:
            return None

    if not any("\u0400" <= char <= "\u04ff" for char in recovered):
        return None

    return recovered


def compute_md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def convert_file(path: Path) -> FileReport:
    payload = path.read_bytes()
    original_hash = compute_md5(payload)

    if not payload:
        return FileReport(
            path=str(path),
            status="skipped",
            original_hash=original_hash,
            new_hash=original_hash,
            error="empty file",
        )

    detected = detect_encoding(payload)

    if detected is None:
        return FileReport(
            path=str(path),
            status="error",
            original_hash=original_hash,
            error="encoding detection failed",
        )

    # Already UTF-8?  Double-check by decoding strictly and attempt to
    # auto-recover mojibake when the markup still declares Windows-1251.
    if detected in {"utf-8", "ascii", "utf_8"}:
        try:
            payload.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            return FileReport(
                path=str(path),
                status="error",
                original_hash=original_hash,
                detected_encoding=detected,
                error=f"utf-8 validation failed: {exc}",
            )

        recovered = _maybe_decode_double_encoded(payload)
        if recovered is not None:
            reencoded = recovered.encode("utf-8")
            if reencoded != payload:
                path.write_bytes(reencoded)
                return FileReport(
                    path=str(path),
                    status="converted",
                    original_encoding="windows-1251",
                    detected_encoding=detected,
                    original_hash=original_hash,
                    new_hash=compute_md5(reencoded),
                )

        return FileReport(
            path=str(path),
            status="skipped",
            original_hash=original_hash,
            new_hash=original_hash,
            detected_encoding="utf-8",
            original_encoding="utf-8",
        )

    try:
        decoded = payload.decode(detected, errors="strict")
    except UnicodeDecodeError as exc:
        return FileReport(
            path=str(path),
            status="error",
            original_hash=original_hash,
            detected_encoding=detected,
            error=f"decode error: {exc}",
        )

    reencoded = decoded.encode("utf-8")

    if reencoded == payload:
        # Safety valve: detection said non-utf8 but bytes didn't change.
        return FileReport(
            path=str(path),
            status="skipped",
            original_hash=original_hash,
            new_hash=original_hash,
            detected_encoding=detected,
            original_encoding=detected,
        )

    path.write_bytes(reencoded)

    return FileReport(
        path=str(path),
        status="converted",
        original_encoding=detected,
        detected_encoding=detected,
        original_hash=original_hash,
        new_hash=compute_md5(reencoded),
    )


def ensure_logs_dir(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)


def write_log(log_dir: Path, records: List[FileReport]) -> Path:
    ensure_logs_dir(log_dir)
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = log_dir / f"reencode-{timestamp}.json"
    serialised = {
        "generated_at": timestamp,
        "files": [asdict(record) for record in records],
    }
    output_path.write_text(json.dumps(serialised, ensure_ascii=False, indent=2), "utf-8")
    return output_path


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert HTML/XML files to UTF-8.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--paths", nargs="+", type=Path, help="Explicit list of files to process.")
    group.add_argument("--scope", nargs="+", type=Path, help="Directories to scan for convertible files.")
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Maximum number of files to process (default: {DEFAULT_LIMIT}).",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=Path("logs"),
        help="Where to store JSON reports (default: ./logs).",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    if args.paths:
        candidates = [Path(path) for path in args.paths]
    else:
        candidates = [Path(path) for path in args.scope]

    files = list(discover_files(candidates))
    if args.limit and len(files) > args.limit:
        files = files[: args.limit]

    reports: List[FileReport] = []
    for path in files:
        reports.append(convert_file(path))

    log_path = write_log(Path(args.log_dir), reports)

    converted = sum(1 for report in reports if report.status == "converted")
    errors = [report for report in reports if report.status == "error"]

    print(f"Processed {len(reports)} file(s); converted {converted}; log: {log_path}")
    if errors:
        print("Errors detected:")
        for report in errors:
            print(f" - {report.path}: {report.error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
