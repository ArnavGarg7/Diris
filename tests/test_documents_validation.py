"""Offline unit tests for upload validation (no DB, no disk, no huge allocations)."""
import pytest
from fastapi import HTTPException

from diris.config import settings
from diris.services.documents import validate_upload


def test_accepts_allowed_extension_case_insensitive():
    assert validate_upload("Report.PDF", 1000) == ".pdf"


def test_rejects_unsupported_extension():
    with pytest.raises(HTTPException) as exc:
        validate_upload("malware.exe", 100)
    assert exc.value.status_code == 400


def test_rejects_empty_file():
    with pytest.raises(HTTPException) as exc:
        validate_upload("a.pdf", 0)
    assert exc.value.status_code == 400


def test_rejects_too_large_without_allocating():
    too_big = settings.max_upload_mb * 1024 * 1024 + 1  # just an integer
    with pytest.raises(HTTPException) as exc:
        validate_upload("a.pdf", too_big)
    assert exc.value.status_code == 413


def test_strips_directory_components_from_filename():
    # A path-traversal-style name is judged by its real basename extension.
    assert validate_upload("../../../etc/passwd.txt", 10) == ".txt"
