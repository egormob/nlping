import json
from pathlib import Path

import pytest

from tools import reencode


def read_json(path: Path) -> dict:
    return json.loads(path.read_text("utf-8"))


def get_log_path(log_dir: Path) -> Path:
    files = list(log_dir.glob("reencode-*.json"))
    assert files, "expected log file to be created"
    return files[0]


def test_reencode_converts_cp1251(tmp_path: Path) -> None:
    content = "Привет, мир!"
    source = tmp_path / "page.html"
    source.write_bytes(content.encode("cp1251"))

    log_dir = tmp_path / "logs"
    exit_code = reencode.main([
        "--paths",
        str(source),
        "--log-dir",
        str(log_dir),
    ])

    assert exit_code == 0
    assert source.read_text("utf-8") == content

    log = read_json(get_log_path(log_dir))
    entry = log["files"][0]
    assert entry["status"] == "converted"
    assert entry["original_encoding"] == "windows-1251" or entry["detected_encoding"] == "windows-1251"


def test_reencode_recovers_double_encoded_cp1251(tmp_path: Path) -> None:
    original = "НЛП для руководителей"
    cp_bytes = original.encode("cp1251")
    mojibake = cp_bytes.decode("latin1")
    payload = (
        "<html><head><meta http-equiv=\"Content-Type\" content=\"text/html; charset=windows-1251\" /></head>"
        f"<body>{mojibake}</body></html>"
    )
    source = tmp_path / "page.html"
    source.write_text(payload, "utf-8")

    log_dir = tmp_path / "logs"
    exit_code = reencode.main([
        "--paths",
        str(source),
        "--log-dir",
        str(log_dir),
    ])

    assert exit_code == 0
    result = source.read_text("utf-8")
    assert "НЛП" in result
    assert "charset=windows-1251" in result  # meta is updated later

    log = read_json(get_log_path(log_dir))
    entry = log["files"][0]
    assert entry["status"] == "converted"
    assert entry["original_encoding"] == "windows-1251"


def test_reencode_skips_utf8(tmp_path: Path) -> None:
    source = tmp_path / "page.html"
    source.write_text("Алгоритм уже в UTF-8", "utf-8")

    log_dir = tmp_path / "logs"
    exit_code = reencode.main([
        "--paths",
        str(source),
        "--log-dir",
        str(log_dir),
    ])

    assert exit_code == 0
    assert source.read_text("utf-8") == "Алгоритм уже в UTF-8"

    log = read_json(get_log_path(log_dir))
    entry = log["files"][0]
    assert entry["status"] == "skipped"
    assert entry["original_hash"] == entry["new_hash"]


def test_reencode_reports_detection_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "page.html"
    source.write_bytes(b"garbage\xff\xfe\xfd")

    def fake_detect(_: bytes) -> None:
        return None

    monkeypatch.setattr(reencode, "detect_encoding", fake_detect)

    log_dir = tmp_path / "logs"
    exit_code = reencode.main([
        "--paths",
        str(source),
        "--log-dir",
        str(log_dir),
    ])

    assert exit_code == 1

    log = read_json(get_log_path(log_dir))
    entry = log["files"][0]
    assert entry["status"] == "error"
    assert entry["error"] == "encoding detection failed"
