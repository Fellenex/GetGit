# GetGit

A tool for scraping GitHub authorship data — commits, pull requests, and associated metadata — for a given user.

## Status

**Phase 1 (current)** — Python CLI. Authenticates via a GitHub Personal Access Token (PAT) and pulls data for a single user.

**Phase 2 (planned)** — Local FastAPI web wrapper with GitHub OAuth login. Any logged-in user can pull their own data (public + private) or anyone else's public data.

**Phase 3 (planned)** — Cloud-deployed, web-accessible. Hosted at a public URL so anyone can sign in and use it without installing anything.

See [`.claude/guidelines.md`](.claude/guidelines.md) for the full roadmap and architectural decision log.

## Data collected

**Commits**
- SHA, repo, datetime, commit message
- Linking PR number (the PR that merged the commit, when available)

**Pull Requests** — split into two collections:
- **Authored** — PRs the user opened
- **Participated** — PRs the user commented on or reviewed but did not author

For each PR:
- Number, repo, title, merged/closed status, timestamps
- Lines added / removed **per file extension** (`{".py": 20, ".yml": 5}`)
- Total comment count *and* count of comments by the target user
- Associated JIRA ticket codes (regex `[A-Z]{2,10}-\d+` over title, body, branch name)

**Reviews** — every code review the user submitted on either set of PRs:
- Source PR, 1-based ordinal index on that PR, state (`APPROVED` / `CHANGES_REQUESTED` / `COMMENTED` / `DISMISSED`), submitted-at, body

## Setup

```bash
pip install -e .
cp .env.example .env       # then edit .env and paste your PAT
python -m getgit <username> [--out output] [--max-commits N] [--max-prs N] [--no-extension-breakdown]
# or, after install:
getgit <username> [--out output] [--max-commits N] [--max-prs N] [--no-extension-breakdown]
```

| Flag | Purpose |
| --- | --- |
| `--out` | Output directory (default `./output`). |
| `--max-commits N` | Cap commits collected. Useful for cheap test runs. |
| `--max-prs N` | Cap PRs collected per set (authored / participated). |
| `--no-extension-breakdown` | Skip the per-file API call; store totals only under the `"*"` key. Saves one paginated call per PR. |

When `<username>` matches the authenticated user, both public and private repos are scanned. Otherwise only public data is returned.

## Output

Written to `output/`:

- `<username>.json` — the full report.
- `<username>.commits.csv`
- `<username>.authored_pull_requests.csv`
- `<username>.participated_pull_requests.csv`
- `<username>.reviews.csv`

In CSV, list-valued fields (e.g. `jira_codes`) render as `;`-joined strings. Dict-valued fields (e.g. `additions`) render as `key:value;...` pairs sorted by key.

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

## Architecture and design decisions

See [`.claude/guidelines.md`](.claude/guidelines.md) for the design contract, roadmap, and the chronological log of architectural decisions.
