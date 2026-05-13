"""Tests for the PR fetcher's pure helpers and sparse-breakdown logic."""

from getgit.fetchers import PullRequestFetcher
from getgit.fetchers.pull_request_fetcher import _extract_jira_codes, _file_extension


class _FakeClient:
    """Minimal stand-in for GithubClient — yields a pre-set list from paginate."""

    def __init__(self, files: list[dict]):
        self._files = files

    def paginate(self, _url: str, _params: dict | None = None):
        return iter(self._files)


def test_file_extension_simple():
    """Standard filenames should yield their suffix with the dot."""
    assert _file_extension("foo.py") == ".py"
    assert _file_extension("path/to/foo.yml") == ".yml"


def test_file_extension_compound():
    """Only the last suffix is considered (so `.tar.gz` → `.gz`)."""
    assert _file_extension("archive.tar.gz") == ".gz"


def test_file_extension_falls_back_to_basename_for_extensionless_files():
    """Files like `Dockerfile` have no extension and should return the bare filename."""
    assert _file_extension("Dockerfile") == "Dockerfile"
    assert _file_extension("path/Makefile") == "Makefile"


def test_file_extension_dotfiles_are_their_own_key():
    """Hidden files like `.gitignore` should bucket under their bare name, not ''."""
    assert _file_extension(".gitignore") == ".gitignore"


def test_extract_jira_codes_groups_by_project_prefix():
    """Codes should bucket under their project prefix."""
    out = _extract_jira_codes("WD-1 YWFB-2 WD-3")
    assert out == {"WD": ["WD-1", "WD-3"], "YWFB": ["YWFB-2"]}


def test_extract_jira_codes_dedupes_across_inputs():
    """A code appearing in multiple blobs should appear once in its project bucket."""
    out = _extract_jira_codes("WD-1 and YWFB-2", "WD-1 again", "PTR-99")
    assert out == {"PTR": ["PTR-99"], "WD": ["WD-1"], "YWFB": ["YWFB-2"]}


def test_extract_jira_codes_ignores_none_and_empty():
    """None and empty strings should be tolerated."""
    assert _extract_jira_codes(None, "", "WD-5") == {"WD": ["WD-5"]}


def test_extract_jira_codes_is_deterministic_across_input_orders():
    """Output should not depend on input order."""
    a = _extract_jira_codes("WD-1 YWFB-2 PTR-3")
    b = _extract_jira_codes("PTR-3 YWFB-2 WD-1")
    assert a == b == {"PTR": ["PTR-3"], "WD": ["WD-1"], "YWFB": ["YWFB-2"]}


def test_extract_jira_codes_requires_uppercase_prefix():
    """Lowercase prefixes (e.g. `wd-1`) must not match — JIRA codes are uppercase."""
    assert _extract_jira_codes("wd-1 and Pr-2") == {}


def test_extract_jira_codes_no_match_returns_empty_dict():
    """No matches anywhere should produce an empty dict (not None)."""
    assert _extract_jira_codes("nothing here", "still nothing") == {}


def test_ext_breakdown_omits_zero_entries():
    """A `.unity` file with deletions but no additions should appear only in `deletions`."""
    files = [
        {"filename": "Assets/foo.unity", "additions": 0, "deletions": 3},
        {"filename": "src/foo.py", "additions": 10, "deletions": 0},
        {"filename": "src/bar.py", "additions": 5, "deletions": 2},
    ]
    fetcher = PullRequestFetcher(_FakeClient(files))

    additions, deletions = fetcher._ext_breakdown("o/r", 1)

    assert additions == {".py": 15}
    assert deletions == {".unity": 3, ".py": 2}


def test_ext_breakdown_no_changes_yields_empty_dicts():
    """A PR with only zero-line file entries returns two empty dicts (not `{ext: 0}`)."""
    files = [{"filename": "noop.txt", "additions": 0, "deletions": 0}]
    fetcher = PullRequestFetcher(_FakeClient(files))

    additions, deletions = fetcher._ext_breakdown("o/r", 1)

    assert additions == {}
    assert deletions == {}
