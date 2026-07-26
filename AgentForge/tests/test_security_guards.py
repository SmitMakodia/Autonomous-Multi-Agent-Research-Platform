"""Guard tests for the two trust boundaries: untrusted paths and untrusted URLs.

Run from the AgentForge directory:  venv\\Scripts\\python.exe -m pytest tests -v

These cover the security logic added in paths.py and net_guard.py. They deliberately use
literal IP addresses rather than hostnames so the URL cases need no DNS and no network.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from net_guard import UnsafeURLError, assert_public_url  # noqa: E402
from paths import (  # noqa: E402
    ALLOWED_UPLOAD_EXTENSIONS,
    UnsafePathError,
    resolve_upload,
    resolve_within,
    safe_upload_name,
)


# --------------------------------------------------------------------------- uploads

@pytest.mark.parametrize("filename", [
    "../../../Windows/System32/drivers/etc/hosts",   # no allowed extension once flattened
    "/etc/passwd",
    r"C:\Windows\System32\config\SAM",
    "..",
    ".",
    "",
    "   ",
])
def test_safe_upload_name_rejects_traversal_and_absolute(filename):
    with pytest.raises(UnsafePathError):
        safe_upload_name(filename)


@pytest.mark.parametrize("filename", [
    r"..\..\..\Windows\Temp\evil.txt",
    "....//....//evil.txt",
    "../../evil.txt",
])
def test_safe_upload_name_neutralises_traversal_to_basename(filename):
    """Traversal is stripped, not rejected, when what remains is a legal filename.

    The result must be a bare name with no separators left, so joining it onto the uploads
    directory cannot escape - that is the property that actually matters.
    """
    result = safe_upload_name(filename)
    assert result == "evil.txt"
    assert "/" not in result and "\\" not in result


@pytest.mark.parametrize("filename", [
    "payload.exe",
    "script.bat",
    "lib.dll",
    "archive.zip",
    "noextension",
])
def test_safe_upload_name_rejects_disallowed_extensions(filename):
    with pytest.raises(UnsafePathError):
        safe_upload_name(filename)


@pytest.mark.parametrize("filename,expected", [
    ("invoice.pdf", "invoice.pdf"),
    ("report.DOCX", "report.DOCX"),          # extension match is case-insensitive
    ("photo.jpeg", "photo.jpeg"),
    ("subdir/notes.md", "notes.md"),          # directory component stripped, not rejected
    (r"C:\Users\someone\Desktop\data.csv", "data.csv"),
])
def test_safe_upload_name_accepts_and_flattens(filename, expected):
    assert safe_upload_name(filename) == expected


def test_every_allowed_extension_survives():
    for ext in ALLOWED_UPLOAD_EXTENSIONS:
        assert safe_upload_name(f"file{ext}") == f"file{ext}"


# ------------------------------------------------------------------------ confinement

def test_resolve_within_accepts_child(tmp_path):
    (tmp_path / "doc.txt").write_text("hello", encoding="utf-8")
    assert resolve_within(tmp_path, "doc.txt") == (tmp_path / "doc.txt").resolve()


def test_resolve_within_accepts_nested_child(tmp_path):
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    assert resolve_within(tmp_path, "a/b") == nested.resolve()


@pytest.mark.parametrize("candidate", [
    "../outside.txt",
    "../../outside.txt",
    "a/../../outside.txt",
    "",
])
def test_resolve_within_rejects_escape(tmp_path, candidate):
    root = tmp_path / "uploads"
    root.mkdir()
    with pytest.raises(UnsafePathError):
        resolve_within(root, candidate)


def test_resolve_within_rejects_absolute_path_outside_root(tmp_path):
    root = tmp_path / "uploads"
    root.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("secret", encoding="utf-8")
    with pytest.raises(UnsafePathError):
        resolve_within(root, str(outside))


def test_resolve_upload_falls_back_to_basename(tmp_path):
    """The LLM often invents a plausible directory for a file that is really in uploads."""
    root = tmp_path / "uploads"
    root.mkdir()
    (root / "invoice.pdf").write_text("x", encoding="utf-8")
    assert resolve_upload(root, "/some/hallucinated/dir/invoice.pdf") == (root / "invoice.pdf").resolve()


def test_resolve_upload_fallback_still_cannot_escape(tmp_path):
    """The basename fallback must not become a second way out."""
    root = tmp_path / "uploads"
    root.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("secret", encoding="utf-8")
    resolved = resolve_upload(root, str(outside))
    assert resolved == (root / "secret.txt").resolve()
    assert not resolved.exists()  # points inside uploads, where no such file exists


# -------------------------------------------------------------------------------- SSRF

@pytest.mark.parametrize("url", [
    "http://127.0.0.1:8000/v1/chat/completions",   # the unauthenticated llama-server
    "http://127.0.0.1:8081/api/sessions",          # AgentForge's own API
    "http://localhost:8000/health",
    "http://[::1]:8000/",
    "http://169.254.169.254/latest/meta-data/",    # cloud metadata
    "http://10.0.0.5/admin",
    "http://192.168.1.1/",
    "http://172.16.0.1/",
    "http://0.0.0.0/",
])
def test_assert_public_url_rejects_internal_targets(url):
    with pytest.raises(UnsafeURLError):
        assert_public_url(url)


@pytest.mark.parametrize("url", [
    "file:///C:/Windows/win.ini",
    "ftp://example.com/x",
    "gopher://example.com/",
    "javascript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "not-a-url",
    "",
])
def test_assert_public_url_rejects_non_http_schemes(url):
    with pytest.raises(UnsafeURLError):
        assert_public_url(url)


@pytest.mark.parametrize("url", [
    "http://8.8.8.8/",
    "https://1.1.1.1/",
])
def test_assert_public_url_allows_public_addresses(url):
    assert assert_public_url(url) == url
