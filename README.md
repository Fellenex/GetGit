# GetGit

A tool for scraping GitHub authorship data — commits, pull requests, and associated metadata — for a given user.

## Status

**Phase 1 (current)** — Python CLI. Authenticates via a GitHub Personal Access Token (PAT) and pulls data for a single user.

**Phase 2 (planned)** — Local FastAPI web wrapper with GitHub OAuth login. Any logged-in user can pull their own data (public + private) or anyone else's public data.

**Phase 3 (planned)** — Cloud-deployed, web-accessible. Hosted at a public URL so anyone can sign in and use it without installing anything.

See [`.claude/guidelines.md`](.claude/guidelines.md) for the full roadmap and architecture; the historical architectural-decision log lives in [`.claude/architecturalDecisions.md`](.claude/architecturalDecisions.md).

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
- Associated JIRA ticket codes — sorted, deduped flat list (`["WD-1234", "WD-5678", "YWFB-99"]`) extracted via regex `[A-Z]{2,10}-\d+` from the **PR description (body) only**. Title, branch name, and comments are intentionally not scanned.

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

Each run writes to a per-run subdirectory `output/<username>/<generated_at>/`, where the timestamp is `YYYY-MM-DD_THH-MM-SS` (hyphens, no colons — works on every filesystem). Inside the subdirectory, one JSON and one CSV per top-level collection:

```
output/
└── fellenex/
    └── 2026-05-13_T03-21-34/
        ├── commits.json
        ├── commits.csv
        ├── authored_pull_requests.json
        ├── authored_pull_requests.csv
        ├── participated_pull_requests.json
        ├── participated_pull_requests.csv
        ├── reviews.json
        └── reviews.csv
```

The username + timestamp in the path captures the metadata that used to live at the top of the unified JSON. Each JSON file is a top-level array of homogeneous rows.

### JSON row shapes

Each `<collection>.json` file inside the per-run subdirectory is a JSON array of these row shapes.

**`commits.json`**
```jsonc
[
  {
    "sha": "abc123…",
    "repo": "owner/repo",
    "authored_at": "2026-05-10T14:22:00+00:00",
    "message": "Fix typo in README",
    "pull_request_number": 42        // null for direct pushes
  }
]
```

**`authored_pull_requests.json`** (and `participated_pull_requests.json` — same shape)
```jsonc
[
  {
    "number": 42,
    "repo": "owner/repo",
    "title": "WD-1234: Add feature X",
    "merged": true,                  // false = closed-without-merge
    "created_at": "2026-05-01T...",
    "closed_at":  "2026-05-03T...",  // null only if still open (we filter is:closed, so always set)
    "updated_at": "2026-05-03T...",  // GitHub's updated_at — drives the next run's `updated:>=` watermark
    "additions": {".py": 120, ".yml": 8, "Dockerfile": 3},  // extensionless files key on basename
    "deletions": {".py": 14, ".unity": 3},                   // sparse: zero entries omitted, so the two dicts may differ in keys
    // "*" appears (instead of per-extension keys) when --no-extension-breakdown
    "comments": 7,                                           // total across all authors
    "comments_by_author": 2,                                 // subset by the target user
    "jira_codes": ["WD-1234", "WD-5678", "YWFB-99"]          // sorted, deduped flat list
  }
]
```

**`reviews.json`**
```jsonc
[
  {
    "pr_repo": "owner/repo",
    "pr_number": 99,
    "index": 1,                       // 1-based ordinal of this user's reviews on this PR
    "state": "APPROVED",              // or CHANGES_REQUESTED / COMMENTED / DISMISSED
    "submitted_at": "2026-05-04T...",
    "body": "lgtm"
  }
]
```

### CSV columns

One CSV per top-level collection. Columns mirror the dataclass field order.

| File | Columns |
| --- | --- |
| `commits.csv` | `sha, repo, authored_at, message, pull_request_number` |
| `authored_pull_requests.csv` | `number, repo, title, merged, created_at, closed_at, updated_at, additions, deletions, comments, comments_by_author, jira_codes` |
| `participated_pull_requests.csv` | (same as authored) |
| `reviews.csv` | `pr_repo, pr_number, index, state, submitted_at, body` |

**Encoding rules for non-scalar cells:**
- List values (e.g. `jira_codes`) → `;`-joined string: `WD-1234;WD-5678;YWFB-99`
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

**Rule of thumb:** if you expect more than ~400 PRs per set, use `--no-extension-breakdown` and/or `--max-prs` to stay under one hour's budget.

**On 403:** the client locks itself on the first `403`, aborts the scrape, and **writes a partial report from whatever data was already collected** — exit code `2` (vs. `0` for full success). Each provider attaches its in-progress accumulator to the raised exception so nothing collected is wasted. There's no automatic backoff; re-run after the rate-limit window resets (typically up to one hour).

## Resumable runs (checkpoint)

Each user has a checkpoint file at `output/<username>/state.json` recording how far the previous run got. On the next run, GetGit:

- Sends `updated:>=<watermark>` on every PR search, skipping PRs that haven't changed.
- Sends `since=<watermark>` to `/repos/{repo}/commits`, skipping commits already collected per repo.
- Always re-lists repos (cheap; usually one page).

Watermark behavior:

- **Complete run** → watermarks advance to the newest data collected.
- **Partial run (rate-limited)** → watermarks do *not* advance. The next run re-fetches the same window so nothing falls into a gap between the old watermark and the oldest item the partial managed to collect.

Each run writes its own `output/<username>/<timestamp>/` subdirectory containing only the delta (the data fetched in *that* run). To get the complete picture across runs, concatenate per-collection files across the timestamp dirs — e.g.

```bash
jq -s 'add' output/Fellenex/*/commits.json > all-commits.json
```

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
| `task startup-tiny -- USERNAME` | Scrape `USERNAME` with `--max-commits 100 --max-prs 100` (cheap test run). |
| `task startup -- USERNAME`      | Full scrape of `USERNAME` with no caps.                 |
| `task test`         | Run the pytest suite.                                   |

## Architecture and design decisions

[`.claude/guidelines.md`](.claude/guidelines.md) holds the design contract, roadmap, and conventions. The chronological log of architectural decisions (numbered `[ADR-001]` through current) lives in [`.claude/architecturalDecisions.md`](.claude/architecturalDecisions.md).
