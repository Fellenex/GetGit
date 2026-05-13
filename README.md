# GetGit

A tool for scraping GitHub authorship data — commits, pull requests, and associated metadata — for a given user.

## Status

Phase 1: Python CLI core. Authenticates via a GitHub Personal Access Token (PAT) and pulls data for a single user.

Phase 2 (planned): FastAPI web wrapper with GitHub OAuth login, allowing any user to pull their own data (public + private) or anyone else's public data.

## Data collected

**Commits**
- Total count
- Datetime
- Commit messages

**Pull Requests** (merged and closed)
- Total count
- Lines added / removed per PR
- Comment count per PR
- Associated JIRA ticket codes (extracted via regex from title, body, and branch name — pattern: `[A-Z]{2,10}-\d+`)

## Setup

```bash
pip install -e .
export GITHUB_TOKEN=ghp_your_token_here    # PowerShell: $env:GITHUB_TOKEN="ghp_..."
python -m getgit <username> [--out output] [--max-commits N] [--max-prs N]
# or, after install:
getgit <username> [--out output] [--max-commits N] [--max-prs N]
```

Use `--max-commits` and `--max-prs` to cap data volume for cheap test runs (e.g. `getgit Fellenex --max-commits 5 --max-prs 5`).

When `<username>` matches the authenticated user, both public and private repos are scanned. Otherwise only public data is returned.

Output: `output/<username>.json` containing commits and closed/merged pull requests with extracted JIRA codes.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

Tests live under `tests/getgit/`, mirroring the package layout.

## Tasks

If you have [Task](https://taskfile.dev) installed:

| Task              | What it does                                              |
| ----------------- | --------------------------------------------------------- |
| `task startup-tiny` | Scrape `Fellenex` with `--max-commits 50 --max-prs 50` (cheap test run). |
| `task startup`      | Full scrape of `Fellenex` with no caps.                 |
| `task test`         | Run the pytest suite.                                   |

## Architecture

See [.claude/guidelines.md](.claude/guidelines.md) for the design contract that shapes this project.
