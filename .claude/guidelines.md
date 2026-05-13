# GetGit — Guidelines

This document captures the design decisions made for GetGit. New work should respect these constraints unless explicitly revisited.

## Goals

GetGit scrapes GitHub authorship data for a person. It runs in two phases:

1. **Phase 1 (now)** — Python CLI. The operator supplies a Personal Access Token (PAT) and a target username. Pulls data for that one user.
2. **Phase 2 (later)** — FastAPI web wrapper with GitHub OAuth. Any logged-in user can pull:
   - Their **own** data (public + private)
   - **Someone else's** public data

The Python core from phase 1 must remain reusable in phase 2. Only the auth-token source should change between the two.

## Data to collect

**Commits**
- Total count
- Datetime of each commit
- Commit message

**Pull Requests** (state: merged or closed)
- Total count
- Lines added / removed per PR (`additions` / `deletions` from REST)
- Comment count per PR
- JIRA ticket codes — extracted by regex `[A-Z]{2,10}-\d+` from PR title, body, and branch name. Dedupe per PR.

## Architecture

### Auth layer (pluggable)

A common `Auth` interface returns an authed HTTP client. Implementations:

- `PersonalTokenAuth` — reads PAT from env var. Phase 1 default.
- `OAuthAppAuth` — GitHub OAuth flow. Added in phase 2.
- `UnauthenticatedAuth` — public-only fallback (heavy rate limit).

Fetchers must never read tokens directly — they receive the client from the auth layer.

### Scope resolver

Given `(viewer, target_user)`, decides what's fetchable:
- `viewer == target` → public + private
- `viewer != target` → public only

Fetchers stay dumb: they ask the resolver "can I see X?" rather than encoding visibility logic themselves.

### Fetchers

One module per data domain. Each returns normalized dicts.
- `repos.py`
- `commits.py`
- `prs.py`
- (extend as needed: `issues.py`, `reviews.py`, `contributions.py`)

### Storage / cache

Local cache (SQLite or JSON keyed by `user/endpoint/etag`). Use ETags + `If-None-Match` so reruns don't burn rate limit.

### CLI entry point

```
ghscrape <username> --include commits,prs --since 2024-01-01 --out data/
```

## Tech choices

- **Language**: Python.
- **HTTP**: `httpx` (sync or async) — *not* PyGithub. PyGithub is REST-only and gets in the way when mixing GraphQL.
- **REST** for repo/PR/commit details.
- **GraphQL** (`api.github.com/graphql`) for contribution calendar and aggregate counts — REST does not expose these accurately.
- **Web framework (phase 2)**: FastAPI + Authlib for OAuth.

## Rate-limit notes

- Authenticated REST: 5,000 req/hr.
- Search API (`/search/commits`, `/search/issues`): 30 req/min, 1,000-result cap per query — slice by date range to work around.
- Always set ETag headers to avoid spending quota on unchanged data.

## Conventions

- Don't add features, abstractions, or error handling beyond what the current task requires.
- Trust internal code; validate only at system boundaries (PAT input, GitHub API responses, user-supplied usernames).
- Default to no comments. Add one only when the *why* is non-obvious.
- Prefer editing existing files over creating new ones.
