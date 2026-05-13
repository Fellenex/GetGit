"""Tests for the PR fetcher's pure helpers."""

from getgit.fetchers.prs import _extract_jira_codes, _file_extension


def test_file_extension_simple():
    """Standard filenames should yield their suffix with the dot."""
    assert _file_extension("foo.py") == ".py"
    assert _file_extension("path/to/foo.yml") == ".yml"


def test_file_extension_compound():
    """Only the last suffix is considered (so `.tar.gz` → `.gz`)."""
    assert _file_extension("archive.tar.gz") == ".gz"


def test_file_extension_none():
    """Files like `Dockerfile` have no extension and should return ''."""
    assert _file_extension("Dockerfile") == ""
    assert _file_extension("path/Makefile") == ""


def test_extract_jira_codes_dedupes_across_inputs():
    """A code appearing in multiple blobs should appear once in the result."""
    codes = _extract_jira_codes("WD-1 and YWFB-2", "WD-1 again", "PTR-99")
    assert codes == ["PTR-99", "WD-1", "YWFB-2"]


def test_extract_jira_codes_ignores_none_and_empty():
    """None and empty strings should be tolerated."""
    assert _extract_jira_codes(None, "", "WD-5") == ["WD-5"]


def test_extract_jira_codes_returns_sorted_for_deterministic_output():
    """Output order should not depend on input order."""
    a = _extract_jira_codes("WD-1 YWFB-2 PTR-3")
    b = _extract_jira_codes("PTR-3 YWFB-2 WD-1")
    assert a == b == ["PTR-3", "WD-1", "YWFB-2"]


def test_extract_jira_codes_requires_uppercase_prefix():
    """Lowercase prefixes (e.g. `wd-1`) must not match — JIRA codes are uppercase."""
    assert _extract_jira_codes("wd-1 and Pr-2") == []


def test_extract_jira_codes_no_match_returns_empty_list():
    """No matches anywhere should produce an empty list (not None)."""
    assert _extract_jira_codes("nothing here", "still nothing") == []
