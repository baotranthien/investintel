"""
Unicode integrity and mojibake regression tests.

Ensures that user-facing frontend files and API router responses do not contain
corrupted Vietnamese characters, Windows-1252/UTF-8 double-encoding artifacts,
replacement characters, or unexpected UTF-8 BOM markers.
"""

from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_SRC = ROOT_DIR / "apps" / "web" / "src"
API_ROUTERS = ROOT_DIR / "apps" / "api" / "routers"

# Signature byte sequences produced when UTF-8 Vietnamese is misread as Windows-1252/Latin-1
MOJIBAKE_SIGNATURES = [
    "Danh má",
    "khÃ",
    "LÃ",
    "Tá»",
    "ChÆ",
    "Cáº",
    "má»",
    "Ä‘",
    "Äƒ",
    "Ä‚",
    "áº",
    "á»",
    "Æ°",
    "Æ¡",
    "\ufffd",
    "â€",
    "â€™",
    "â€“",
    "â€¦",
]

def scan_text_for_mojibake(text: str) -> list[tuple[int, str, list[str]]]:
    issues = []
    for line_idx, line in enumerate(text.splitlines(), start=1):
        found = [sig for sig in MOJIBAKE_SIGNATURES if sig in line]
        if found:
            issues.append((line_idx, line.strip(), found))
    return issues


def test_mojibake_detection_logic():
    """Verify that the detection logic accurately distinguishes valid Vietnamese from mojibake."""
    corrupted_samples = [
        "Danh má»¥c",
        "khÃ´ng Ä‘áº·t lá»‡nh",
        "LÃ m má»›i",
        "Tá»•ng giÃ¡ trá»‹",
        "ChÆ°a cÃ³ holding",
        "Cáº¥u hÃ¬nh khá»Ÿi Ä‘áº§u cÃ¡ nhÃ¢n",
        "Error with \ufffd replacement character",
        "Special dash â€“ and quote â€™",
    ]
    for sample in corrupted_samples:
        issues = scan_text_for_mojibake(sample)
        assert len(issues) > 0, f"Failed to detect mojibake in sample: {sample}"

    valid_samples = [
        "Danh mục",
        "không đặt lệnh",
        "Làm mới",
        "Tổng giá trị",
        "Chưa có holding",
        "Cấu hình khởi đầu cá nhân",
        "Personal Starting Template / Cấu hình khởi đầu cá nhân",
        "PHÂN TÍCH",
        "CÁ NHÂN · LOCAL-FIRST",
        "Không thể lưu dữ liệu.",
        "Manual transaction record đã được lưu; holdings không tự thay đổi.",
    ]
    for sample in valid_samples:
        issues = scan_text_for_mojibake(sample)
        assert len(issues) == 0, f"False positive detected in valid Vietnamese: {sample} (found: {issues})"


def test_no_mojibake_in_frontend_sources():
    """Assert all files in apps/web/src are free from mojibake patterns."""
    assert FRONTEND_SRC.exists(), f"Frontend src directory not found at {FRONTEND_SRC}"

    extensions = {".tsx", ".ts", ".css", ".json"}
    all_issues = []

    for path in FRONTEND_SRC.rglob("*"):
        if not path.is_file() or path.suffix not in extensions:
            continue
        rel_path = path.relative_to(ROOT_DIR)
        content = path.read_text(encoding="utf-8", errors="replace")
        file_issues = scan_text_for_mojibake(content)
        if file_issues:
            for line_no, line, sigs in file_issues:
                all_issues.append(f"{rel_path}:{line_no} (sigs: {sigs}): {line}")

    assert not all_issues, "Mojibake detected in frontend sources:\n" + "\n".join(all_issues)


def test_no_mojibake_in_api_routers():
    """Assert all API routers are free from mojibake patterns."""
    assert API_ROUTERS.exists(), f"API routers directory not found at {API_ROUTERS}"

    all_issues = []
    for path in API_ROUTERS.glob("*.py"):
        rel_path = path.relative_to(ROOT_DIR)
        content = path.read_text(encoding="utf-8", errors="replace")
        file_issues = scan_text_for_mojibake(content)
        if file_issues:
            for line_no, line, sigs in file_issues:
                all_issues.append(f"{rel_path}:{line_no} (sigs: {sigs}): {line}")

    assert not all_issues, "Mojibake detected in API routers:\n" + "\n".join(all_issues)


def test_no_utf8_bom_in_frontend_sources():
    """Assert no source files in apps/web/src contain a UTF-8 BOM."""
    bom_files = []
    for path in FRONTEND_SRC.rglob("*"):
        if not path.is_file() or path.suffix not in {".tsx", ".ts", ".css"}:
            continue
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            bom_files.append(str(path.relative_to(ROOT_DIR)))

    assert not bom_files, f"UTF-8 BOM detected in frontend files: {bom_files}"
