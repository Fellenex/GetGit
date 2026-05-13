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
- Default to no inline comments. Add one only when the *why* is non-obvious.
- **Every function and class gets a docstring.** Even one-liners. State *what* it does and, when it isn't obvious, *why*. Document non-trivial parameters and return shapes. Module-level docstrings are encouraged when a file's role isn't clear from its name.
- Prefer editing existing files over creating new ones.

## Recording architectural decisions

Every architectural decision must be appended to the "Architectural decisions" section below. An "architectural decision" includes:

- How code is organized: module boundaries, class/function structure, design patterns
- Library or framework choices
- Data-shape contracts (model definitions, serialization formats)
- Error-handling, caching, storage, or auth strategies
- **Any time a choice is made between two or more options**, even if the alternatives feel obvious — the rejected options matter for future readers

Trivial implementation details (variable names, one-line refactors) do not belong here.

**Format** — append in chronological order:

```
### YYYY-MM-DD — Short title
**Decision:** what was chosen.
**Alternatives:** what was considered and rejected.
**Why:** the reasoning, including any constraints or future-phase implications.
```

If a prior decision is reversed, update the original entry with a `**Reversed YYYY-MM-DD:**` note and link to the new decision — do not silently overwrite.

## Architectural decisions

### 2026-05-12 — Roadmap by version
**Decision:** v0.1.0 = download own (public + private) data via console; v0.2.0 = download a stranger's public data via console; v0.3.0 = dockerize so a single `docker compose up` produces the output files.
**Alternatives:** ship the OAuth web wrapper before dockerizing; combine v0.1 and v0.2 (since the only difference is scope-resolver behavior).
**Why:** front-loading the self-only path keeps the surface area small and lets us validate the data shape and JIRA-extraction quality before opening it to arbitrary users. Docker comes before the web wrapper because the web wrapper depends on a known-good runtime.

### 2026-05-12 — JSON as the export format
**Decision:** all collected data is serialized to `.json` files.
**Alternatives:** SQLite, CSV, Parquet.
**Why:** matches GitHub's native API shapes (no lossy flattening); easy to diff and inspect; trivially consumable by phase 2 (FastAPI). CSV stays a downstream concern, not the storage format.

### 2026-05-12 — Dataclasses for every JSON model
**Decision:** every distinct JSON model has a Python `@dataclass` (or `pydantic` model if validation is needed) in `getgit/models.py`. Fetchers return dataclass instances; serialization to JSON happens at the storage boundary.
**Alternatives:** pass raw dicts everywhere; use TypedDict.
**Why:** dataclasses make the model contract explicit and refactor-safe; phase 2's FastAPI layer can lift them into response models with minimal changes.

### 2026-05-12 — CLI accepts username as positional argument
**Decision:** the CLI takes a GitHub username as a required positional argument (e.g. `python -m getgit <username>`).
**Alternatives:** infer the username from the PAT's authenticated user; prompt interactively.
**Why:** explicit is better than implicit, and v0.2.0 will need to target arbitrary usernames anyway — using the same interface from v0.1.0 avoids a breaking change.

### 2026-05-12 — Self vs stranger handled by a single `is_self` branch in the repo fetcher
**Decision:** the only structural difference between scraping yourself and scraping a stranger lives in `getgit/fetchers/repos.py`: `is_self=True` calls `/user/repos` (public + private), `is_self=False` calls `/users/{u}/repos` (public only). Everything downstream (commits, PRs, search) is identical because the GitHub API already filters results by the PAT's visibility.
**Alternatives:** introduce a dedicated `ScopeResolver` class with explicit `can_see(...)` checks at every fetcher; gate the stranger path behind a `--public` flag.
**Why:** the GitHub API enforces visibility server-side, so a client-side resolver would be redundant ceremony at this stage. The `is_self` boolean is the minimum signal needed and keeps fetchers dumb. A real `ScopeResolver` becomes worthwhile in phase 2 when the *viewer* identity comes from OAuth and may differ per request — at that point the boolean grows into an object.

### 2026-05-12 — v0.2.0 is a hardening release, not a feature release
**Decision:** v0.2.0 ships no new fetchers or CLI surface. Scope: add tests (commits, PR JIRA extraction, pagination, `is_self` branching against a mocked API), handle rate-limit responses gracefully (`X-RateLimit-Remaining` / `Retry-After`), and verify the stranger path end-to-end against a real public account.
**Alternatives:** bundle Docker into v0.2.0; add a `--public` flag to force the stranger path even when targeting yourself.
**Why:** the stranger path already works structurally (see prior decision). The risk in opening it up is correctness and politeness toward GitHub's API, not missing code. Keeping Docker in v0.3.0 preserves the roadmap's separation of concerns: v0.2 = trust the data; v0.3 = trust the runtime.

### 2026-05-12 — src-layout with `pyproject.toml`
**Decision:** package lives at `src/getgit/`, declared in `pyproject.toml` via `tool.setuptools.packages.find` with `where = ["src"]`. Install with `pip install -e .`; run as `python -m getgit` or the `getgit` console script.
**Alternatives:** flat layout (`getgit/` at repo root); package literally named `src` (no `pyproject.toml`); `requirements.txt` + `PYTHONPATH=src` runtime hack.
**Why:** the src-layout prevents accidental imports from the working directory (a common cause of "tests pass locally but fail in CI" bugs) and forces the package to be installed before it's importable — which mirrors how phase 2 (FastAPI in Docker) will consume it. `pyproject.toml` becomes the single source of truth for dependencies, replacing `requirements.txt` for the package itself.

### 2026-05-12 — `models/` package with `JSONModel` mixin
**Decision:** models live under `src/getgit/models/` — one file per model (`commit.py`, `pull_request.py`, `report.py`) plus a `base.py` that defines a `JSONModel` mixin with a `to_jsonable()` method. Models are `@dataclass` classes that inherit from `JSONModel`. The package `__init__.py` re-exports the public surface so callers still write `from .models import Commit`.
**Alternatives:** keep a single `models.py` with a free-function `to_jsonable`; make `JSONModel` itself a dataclass parent; reach for Pydantic for runtime validation.
**Why:** as the model count grows (issues, reviews, contributions in later phases), a flat file becomes unwieldy. A mixin keeps serialization logic next to the contract it serializes — `report.to_jsonable()` reads better than `to_jsonable(report)` and removes the temptation to bypass it. `JSONModel` is *not* a dataclass on purpose: mixing dataclass inheritance forces field-ordering rules that subclasses would have to think about. Pydantic stays out for now — dataclasses are stdlib and we don't yet need runtime validation; we'll revisit when the FastAPI layer lands in phase 2.

### 2026-05-12 — Load secrets from `.env` via python-dotenv
**Decision:** `cli.py` calls `load_dotenv()` at startup. `.env` is gitignored; `.env.example` is committed as a template. Code still reads from `os.environ` — `.env` only populates the environment, it is never parsed directly by application code.
**Alternatives:** require operators to `export` env vars manually; build a custom config loader; use Pydantic Settings.
**Why:** `.env` is the de facto standard for local secrets and matches what FastAPI/Docker will expect in phase 2/3. Keeping `os.environ` as the single read path means Docker, CI, and `.env` all flow through the same interface — no library lock-in inside fetchers.
