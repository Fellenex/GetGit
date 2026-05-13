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

- `<username>.json` — full structured report (canonical source).
- `<username>.commits.csv`
- `<username>.authored_pull_requests.csv`
- `<username>.participated_pull_requests.csv`
- `<username>.reviews.csv`

### JSON shape

```jsonc
{
  "username": "Fellenex",
  "generated_at": "2026-05-12T10:30:00+00:00",
  "commits": [
    {
      "sha": "abc123…",
      "repo": "owner/repo",
      "authored_at": "2026-05-10T14:22:00+00:00",
      "message": "Fix typo in README",
      "pull_request_number": 42        // null for direct pushes
    }
  ],
  "authored_pull_requests": [
    {
      "number": 42,
      "repo": "owner/repo",
      "title": "WD-1234: Add feature X",
      "merged": true,                  // false = closed-without-merge
      "created_at": "2026-05-01T...",
      "closed_at":  "2026-05-03T...",  // null only if still open (we filter is:closed, so always set)
      "additions": {".py": 120, ".yml": 8, "": 3},   // "" = files with no extension
      "deletions": {".py": 14},                       // "*" appears instead when --no-extension-breakdown
      "comments": 7,                                  // total across all authors
      "comments_by_author": 2,                        // subset by the target user
      "jira_codes": ["WD-1234"]                       // sorted, deduped
    }
  ],
  "participated_pull_requests": [ /* same shape; user commented/reviewed but didn't author */ ],
  "reviews": [
    {
      "pr_repo": "owner/repo",
      "pr_number": 99,
      "index": 1,                       // 1-based ordinal of this user's reviews on this PR
      "state": "APPROVED",              // or CHANGES_REQUESTED / COMMENTED / DISMISSED
      "submitted_at": "2026-05-04T...",
      "body": "lgtm"
    }
  ]
}
```

### CSV columns

One CSV per top-level collection. Columns mirror the dataclass field order.

| File | Columns |
| --- | --- |
| `<u>.commits.csv` | `sha, repo, authored_at, message, pull_request_number` |
| `<u>.authored_pull_requests.csv` | `number, repo, title, merged, created_at, closed_at, additions, deletions, comments, comments_by_author, jira_codes` |
| `<u>.participated_pull_requests.csv` | (same as authored) |
| `<u>.reviews.csv` | `pr_repo, pr_number, index, state, submitted_at, body` |

**Encoding rules for non-scalar cells:**
- List values (e.g. `jira_codes`) → `;`-joined string: `WD-1;YWFB-9`
- Dict values (e.g. `additions`) → `key:value;...` pairs sorted by key: `.py:120;.yml:8`
- An empty list or empty dict renders as the empty string.

If a collection is empty, the corresponding CSV is written as an empty file (no header) — there's no row from which to infer column names.

## API cost

GitHub's authenticated REST limit is **5,000 requests/hour**. Knowing how a run consumes that budget tells you whether to use `--max-prs`, `--max-commits`, or `--no-extension-breakdown`.

A run breaks into three buckets:

```
total ≈ fixed_overhead
      + 6 × (P_authored + P_participated)        # default mode
      + R + ⌈C / 100⌉                             # commits
```

| Bucket | What it costs | Affected by which flag |
| --- | --- | --- |
| **Fixed overhead** | `1` viewer call + `⌈R/100⌉` repo-listing pages + ~3 search paginations (one per: `author:`, `commenter:`, `reviewed-by:`) | Searches paginate fully even with `--max-prs`. Fixed overhead is typically `≤30 calls`. |
| **PR hydration** | **6 calls per PR** (default) — `/pulls/{n}`, `/pulls/{n}/commits`, `/pulls/{n}/files`, `/pulls/{n}/reviews`, `/issues/{n}/comments`, `/pulls/{n}/comments`. Drops to **5** with `--no-extension-breakdown`. PRs with many files / comments / reviews / commits paginate further. | `--max-prs N` caps **each** of `P_authored` and `P_participated` at `N`. `--no-extension-breakdown` shaves 1 call per PR. |
| **Commit fetch** | `R + ⌈C/100⌉` — one paginated request per repo, plus extra pages if the repo has many commits by the user. | `--max-commits N` stops once `N` commits are collected, but the loop still touches repos until then. |

### Worked examples

Assuming `R = 20` repos, `5,000 req/hr` budget:

| Scenario | Flags | Approx. calls |
| --- | --- | --- |
| Tiny test | `--max-commits 50 --max-prs 50` | `~30` overhead + `6 × 100` = **~630** |
| Tiny + no extension breakdown | `--max-commits 50 --max-prs 50 --no-extension-breakdown` | `~30` + `5 × 100` = **~530** |
| Medium user (200 PRs of each type, 1k commits) | (no caps) | `~30` + `6 × 400` + `20 + 10` = **~2,460** |
| Heavy user (1,000 PRs of each type, 10k commits) | (no caps) | `~30` + `6 × 2,000` + `20 + 100` = **~12,150** ❗ exceeds hourly limit |
| Same heavy user, breakdown disabled | `--no-extension-breakdown` | `~30` + `5 × 2,000` + `120` = **~10,150** ❗ still over |
| Heavy user, throttled by `--max-prs 400` | `--max-prs 400 --no-extension-breakdown` | `~30` + `5 × 800` + `120` = **~4,150** ✅ |

**Rule of thumb:** if you expect more than ~400 PRs per set, use `--no-extension-breakdown` and/or `--max-prs` to stay under one hour's budget. The fetcher does not currently sleep on rate-limit responses — exceeding the budget will surface as `403`s mid-run.

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
