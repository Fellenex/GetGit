# GetGit — Guidelines

This document captures the design decisions made for GetGit. New work should respect these constraints unless explicitly revisited.

User-facing material — what the project does, how to install and run it, output formats, task list — lives in [`README.md`](../README.md). This file is for design contracts and architectural reasoning, not usage docs.

## Roadmap

GetGit ships in three phases. Each phase introduces a new deployment surface; the data model and fetcher core stay reusable across all of them.

### Phase 1 — Python CLI
Operator supplies a PAT and a target username. Runs locally; writes JSON + CSV to disk.

- **v0.1.0** — download own (public + private) data via console.
- **v0.2.0** — hardening release: tests, rate-limit handling, verify the stranger-public-data path end-to-end.
- **v0.3.0** — dockerize so a single `docker compose up` produces the output files.

### Phase 2 — Local web wrapper
FastAPI + GitHub OAuth running on the operator's machine. Any logged-in user can pull their own data (public + private) or anyone else's public data.

### Phase 3 — Cloud-deployed, web-accessible
Hosted FastAPI service reachable at a public URL. Any GitHub user can sign in and pull data without installing anything. Introduces multi-tenant concerns (per-user token storage, persistent results storage, isolation between users, abuse/quota controls) that don't exist in phase 2.

The Python core from phase 1 must remain reusable in phases 2 and 3. The auth-token source and the storage destination are the only layers expected to change between phases.

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

One module per data domain. Each returns dataclass instances (see `models/`).
- `repos.py`
- `commits.py`
- `prs.py`
- (extend as needed: `issues.py`, `contributions.py`)

### Storage / cache

Local file output today (JSON + CSV). Phase 3 will need a persistent store (DB or object storage) and per-user isolation. ETags + `If-None-Match` are the mechanism for not re-spending quota on unchanged data — wire them in when caching becomes a real constraint.

## Tech choices

- **Language**: Python.
- **HTTP**: `httpx` (sync or async) — *not* PyGithub. PyGithub is REST-only and gets in the way when mixing GraphQL.
- **REST** for repo/PR/commit details.
- **GraphQL** (`api.github.com/graphql`) for contribution calendar and aggregate counts when REST does not expose them accurately.
- **Web framework (phase 2/3)**: FastAPI + Authlib for OAuth.

## Rate-limit notes

- Authenticated REST: 5,000 req/hr.
- Search API (`/search/commits`, `/search/issues`): 30 req/min, 1,000-result cap per query — slice by date range to work around.
- Per-PR cost in the current design: 6 calls (`/pulls/{n}`, `/pulls/{n}/commits`, `/pulls/{n}/files`, `/pulls/{n}/reviews`, `/issues/{n}/comments`, `/pulls/{n}/comments`). `--no-extension-breakdown` drops it to 5.
- Always set ETag headers when caching is added to avoid spending quota on unchanged data.

## Conventions

- Don't add features, abstractions, or error handling beyond what the current task requires.
- Trust internal code; validate only at system boundaries (PAT input, GitHub API responses, user-supplied usernames).
- Default to no inline comments. Add one only when the *why* is non-obvious.
- **Every function and class gets a docstring.** Even one-liners. State *what* it does and, when it isn't obvious, *why*. Document non-trivial parameters and return shapes. Module-level docstrings are encouraged when a file's role isn't clear from its name.
- **Public methods/functions appear above private ones** (`_`-prefixed) in every file. Reading top-to-bottom should walk the public surface first, then drop into helpers.
- **One class per file.** A file may contain module-level helper functions or constants that support its class, but never two classes.
- **Filenames mirror their class name** in `snake_case`. `AppSettings` lives in `app_settings.py`; `JSONModel` in `json_model.py`. The matching is mechanical so nothing is hidden.
- **Source is organized by domain**, not by technical layer. Each domain is a folder under `src/getgit/` with an `__init__.py` that re-exports the public types. Current domains: `authentication/`, `cli/`, `fetchers/`, `github_api/`, `models/`. Single-file utilities (e.g. `storage.py`) stay top-level until they grow a class to organize.
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

### 2026-05-12 — Roadmap by phase
**Decision:** three phases — Phase 1 (Python CLI, versioned v0.1/v0.2/v0.3 internally), Phase 2 (local FastAPI + OAuth), Phase 3 (cloud-deployed, public URL). The Python core from Phase 1 must stay reusable in 2 and 3 — only the auth source and storage destination change between phases.
**Alternatives:** ship the OAuth web wrapper before dockerizing; combine v0.1 and v0.2 (since the only difference is scope-resolver behavior); skip phase 2 and jump straight to cloud.
**Why:** front-loading the self-only path keeps the surface area small and lets us validate the data shape and JIRA-extraction quality before opening it to arbitrary users. Docker comes before the web wrapper because the web wrapper depends on a known-good runtime. Phase 2 (local web) exists as a deliberate stepping-stone so OAuth and request-time scope resolution are working before we add multi-tenant cloud concerns.

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

### 2026-05-12 — `--max-commits` / `--max-prs` for test runs
**Decision:** each fetcher accepts an optional `limit: int | None` parameter and stops iterating once reached. The CLI exposes `--max-commits` and `--max-prs`. Default is `None` (no cap).
**Alternatives:** a single global `--max` knob; sampling (random N from full result); environment variable instead of CLI flags.
**Why:** per-fetcher limits map directly to the two API surfaces with different cost profiles (per-repo commits vs. search-API PRs). Stopping at the fetcher level avoids paying for paginated calls we'd then discard. Defaulting to `None` keeps production behavior unchanged.

### 2026-05-12 — `_extract_jira_codes` uses a set
**Decision:** JIRA-code extraction uses a `set` internally and returns `sorted(found)`.
**Alternatives:** keep the order-preserving list-with-`in`-check; `dict.fromkeys` for ordered dedupe; return the set directly.
**Why:** dedupe is O(1) per insert (vs. O(n) for the list scan), and a sorted output makes the JSON deterministic across runs — diffing two reports stays meaningful. Returning a list (not a set) preserves JSON-serializability without special-casing in `JSONModel`.

### 2026-05-12 — Pytest under `tests/`, mirroring the package layout
**Decision:** test framework is `pytest`, declared as a `[dev]` optional dependency in `pyproject.toml`. Tests live under `tests/getgit/...` mirroring `src/getgit/...`. Pytest config sets `pythonpath = ["src"]` and `--import-mode=importlib`. **Test directories must not contain `__init__.py`** — they would shadow the real `getgit` package and break imports.
**Alternatives:** `unittest` (stdlib, no install needed); flat `tests/` dir without subdirs; rely on `pip install -e .` instead of `pythonpath`.
**Why:** pytest is the de facto standard — concise asserts, fixtures, and a vast plugin ecosystem (will matter when we want HTTP mocking via `respx` or `pytest-httpx`). Mirroring the package keeps "where do I add a test for this file?" trivial. `importlib` import mode plus no `__init__.py` files in `tests/` is the only combination that avoids the namespace collision with the real `getgit` package; `pythonpath` keeps tests runnable without an editable install.

### 2026-05-12 — Commit→PR linkage built from PR-side, not commit-side
**Decision:** the commit→PR mapping is built by walking `/repos/.../pulls/{n}/commits` for each PR we already fetched, then attaching `pull_request_number` to each commit during materialization. **Updated 2026-05-12:** the index is now built inside `fetch_pull_requests` in the same loop that materializes each `PullRequest`, returned as part of a `PullRequestFetchResult`. The standalone `build_commit_pr_index` was removed.
**Alternatives:** call `/repos/.../commits/{sha}/pulls` for every commit (the obvious per-commit lookup); use the GraphQL `Commit.associatedPullRequests` field per commit; keep PR materialization and indexing as two separate passes over the PR list.
**Why:** per-commit lookups are O(commits), which dominates O(PRs) for any active user. The merged single-pass design doesn't reduce API calls (each PR still needs `/pulls/{n}` plus `/pulls/{n}/commits`), but it eliminates a redundant traversal of the PR list and keeps the two related calls colocated. The `PullRequestFetchResult` wrapper makes the dual-output explicit at call sites instead of returning a bare tuple.

### 2026-05-12 — Drop `PullRequest.state`; keep only `merged`
**Decision:** removed the `state: str` field. `merged: bool` is the single source of truth.
**Alternatives:** keep both for "self-documenting JSON"; replace with an enum.
**Why:** the search query is hardcoded to `is:closed`, so every PR returned is in one of two terminal states fully determined by `merged_at`. Two fields encoding the same bit invites them to drift. Consumers needing a string label can derive `"merged" if merged else "closed"` trivially.

### 2026-05-12 — CSV export alongside JSON; one file per row-shaped model
**Decision:** `write_report` emits the canonical JSON plus one CSV per row-shaped model (`<user>.commits.csv`, `<user>.pull_requests.csv`). Columns come from `dataclasses.fields()` order. List-valued fields (currently only `jira_codes`) are joined with `;`. CSV writing lives in `storage.py` — models stay pure data.
**Alternatives:** add a `to_csv_row()` method on `JSONModel`; emit one combined CSV with a discriminator column; ship JSON only and let downstream tools convert.
**Why:** keeping the conversion in storage avoids polluting the model layer with a serialization format that's strictly downstream of `to_jsonable()`. One file per model maps cleanly onto how spreadsheets and BI tools consume tabular data — combining them would force consumers to filter. The `;` join is lossless for JIRA codes (which never contain semicolons) and avoids CSV-quoting edge cases. If a future model becomes deeply nested, that's the trigger to introduce a per-model `to_csv_row()` with a custom flattening rule, but flat dataclasses don't need it yet.

### 2026-05-12 — Track reviews; split PRs into authored vs participated
**Decision:** the report now carries three PR-side collections: `authored_pull_requests` (search: `author:USER`), `participated_pull_requests` (union of `commenter:USER` and `reviewed-by:USER`, minus authored), and a flat `reviews` list of every review the user submitted on either set. New `Review` model (`pr_repo`, `pr_number`, `index` (1-based ordinal among the user's reviews on that PR), `state`, `submitted_at`, `body`).
**Alternatives:** keep one combined PR list with an `authored_by_user: bool` field; nest reviews inside their PR rather than flattening; use GitHub's `involves:USER` qualifier (covers author/assignee/mentions/commenter, too broad).
**Why:** authored vs participated answer fundamentally different questions ("what did I ship" vs "what did I help with"), so consumers shouldn't have to filter. Flat `reviews` list keeps the model symmetric with `commits` (authorship-as-output regardless of source) and makes the reviews CSV trivially diffable. `commenter` + `reviewed-by` is the most precise way to capture "user touched this PR".

### 2026-05-12 — `additions`/`deletions` keyed by file extension; `--no-extension-breakdown` opt-out
**Decision:** `PullRequest.additions` and `.deletions` are now `dict[str, int]` keyed by file extension (`{".py": 20, ".yml": 5}`). Empty key `""` is files without an extension. The sentinel key `"*"` means the breakdown was disabled and the value is the aggregate total. Disabled via `--no-extension-breakdown`, which skips the `/pulls/{n}/files` call and reads totals from the `/pulls/{n}` payload we already fetch.
**Alternatives:** keep `int` totals and add a separate `additions_by_extension` field; parse the raw diff ourselves; bake extension grouping into the consumer.
**Why:** consumers asking for per-extension breakdown almost never want both shapes — adding a parallel field is dead weight. Using a sentinel `"*"` keeps the schema stable across both modes (always `dict[str, int]`) so the JSON consumer doesn't need a type-switch. The flag exists because file-level fetches add one paginated call per PR; on huge histories that may be the difference between fitting in a rate-limit budget and not.

### 2026-05-12 — `comments_by_author` alongside total `comments`
**Decision:** `PullRequest.comments` (all-author total, free from `/pulls/{n}`) stays; new `comments_by_author: int` counts comments the target user authored across both `/issues/{n}/comments` and `/pulls/{n}/comments` (review/inline comments). Costs two extra paginated calls per PR.
**Alternatives:** drop the all-author total; only count for participated PRs and set authored to `0`; use GraphQL to get both counts in one call.
**Why:** for authored PRs the author-self-comment count signals self-discussion; for participated PRs it's the entire reason the PR is in the report. Both numbers belong. GraphQL would consolidate calls but introduces a second API surface for marginal savings — revisit if rate limits become a real ceiling.

### 2026-05-12 — `_file_extension` falls back to bare basename for extensionless files
**Decision:** files without a suffix (`Dockerfile`, `Makefile`, `.gitignore`) bucket under their full basename instead of `""`.
**Alternatives:** keep the `""` bucket; introduce a sentinel like `"<noext>"`; classify by content type.
**Why:** the `""` bucket conflated meaningfully different filetypes (Dockerfiles vs. Makefiles vs. dotfiles), giving consumers a useless "lots of edits with no extension" cell. The bare basename is what a human would call the type and is unique enough for the per-extension breakdown to remain readable.

### 2026-05-12 — Dedicated `ArgumentParser` class producing `AppSettings`
**Decision:** CLI arg parsing lives in a class (`getgit.argument_parser.ArgumentParser`) that wraps `argparse.ArgumentParser` via composition and returns an `AppSettings` dataclass (`getgit.settings.AppSettings`). `cli.main` calls `ArgumentParser().parse(argv)` then hands the settings to `_run`.
**Alternatives:** keep the inline argparse in `main`; subclass `argparse.ArgumentParser`; use Click/Typer; pass the raw `argparse.Namespace` directly.
**Why:** decoupling parsing from orchestration means the same fetcher pipeline can be driven by a phase-2 HTTP form or a phase-3 JSON request body — only the producer of `AppSettings` changes. Composition (not subclassing) keeps the public surface tiny and avoids inheriting argparse internals. Click/Typer would be the right call if the CLI grew subcommands, but argparse is stdlib and currently sufficient.

### 2026-05-12 — One file per `@dataclass`; mirrored test files
**Decision:** every `@dataclass` lives in its own file. New homes: `getgit/settings.py` (`AppSettings`), `getgit/fetchers/pull_request_fetch_result.py` (`PullRequestFetchResult`). Tests follow the same one-file-per-source-file rule under `tests/getgit/...`.
**Alternatives:** group related dataclasses in `models.py` / `results.py` files; rely on a flat test file per concern (e.g., `test_models.py`).
**Why:** a 1:1 file mapping makes "where does this type live?" and "where do I add a test for this file?" mechanical questions with no judgment calls. Costs a few extra files but keeps imports unambiguous and diffs scoped — particularly important as the model count grows in phase 2/3.

### 2026-05-12 — `GithubClient` class replaces free-function `github_api`
**Decision:** the GitHub-side network surface is now `getgit.github_client.GithubClient`, a class wrapping `httpx.Client`. It exposes `get`, `paginate`, and `viewer_login`, and acts as a context manager. `Auth.client()` returns a `GithubClient` directly; the old `github_api.py` module is gone.
**Alternatives:** keep `paginate` as a free function; subclass `httpx.Client`; introduce a thin GraphQL helper alongside.
**Why:** every fetcher now takes one constructor argument (the client) instead of receiving a raw `httpx.Client` plus importing free helpers. That's the seam phase 2 will need: an OAuth-backed `GithubClient` (or a per-request mock) drops in without changing fetcher code. Composition over `httpx.Client` keeps our public surface narrow — fetchers can't accidentally reach into low-level HTTP details.

### 2026-05-12 — Fetchers are classes parameterized by `GithubClient`
**Decision:** `RepoFetcher`, `CommitFetcher`, and `PullRequestFetcher` are classes. Each takes a `GithubClient` in `__init__` and exposes its work via methods (`list_repos`, `fetch`, `fetch`).
**Alternatives:** keep the module-level functions and pass the client every call; use a single mega-fetcher class.
**Why:** stateful collaboration with the client is the norm (every method makes calls), so the client becomes a constructor param instead of polluting every signature. Per-domain classes mirror the per-domain modules and stay independently testable. A single mega-fetcher would couple unrelated concerns and grow indefinitely.

### 2026-05-12 — `PullRequest.jira_codes` is `dict[str, list[str]]` keyed by project prefix
**Decision:** changed the field from `list[str]` to `dict[str, list[str]]`. `{"WD": ["WD-1234", "WD-5678"], "YWFB": ["YWFB-99"]}`. Inner lists are sorted/deduped; outer keys are alphabetical.
**Alternatives:** keep the flat list; use `dict[str, int]` (project → mention count); switch to a custom dataclass.
**Why:** mirrors the `additions`/`deletions` per-extension shape (group by category), which is how consumers want to slice this data ("how many YWFB tickets did this PR touch?"). Inner lists keep the full codes — a count alone would lose the references. CSV gets a nested separator (`|` inside lists, `;` between entries) so the dict-of-lists round-trips through a single cell unambiguously.

### 2026-05-12 — Public methods/functions appear above private (`_`-prefixed)
**Decision:** within any file (or class), the public surface comes first; `_`-prefixed helpers go below.
**Alternatives:** alphabetical ordering; helpers above their callers (a la C); no rule.
**Why:** reading top-to-bottom should answer "what does this thing do?" before "how does it do it?". This also localizes the public API at a glance without scanning past helpers.

### 2026-05-12 — Source organized by domain; one class per file; filename = snake_case(class)
**Decision:** every class lives in its own file named after it (`AppSettings` → `app_settings.py`). Files are grouped into domain folders under `src/getgit/`: `authentication/`, `cli/`, `fetchers/`, `github_api/`, `models/`. Each domain has an `__init__.py` that re-exports its public types so external callers do `from getgit.fetchers import PullRequestFetcher` instead of digging into module paths. Tests mirror the same layout (`tests/getgit/<domain>/test_<file>.py`). `Auth` (Protocol) and `PersonalTokenAuth` are in separate files inside `authentication/`. Single-file utilities (e.g. `storage.py`) stay top-level until they grow a class.
**Alternatives:** organize by technical layer (`controllers/`, `services/`, `repositories/`); keep multi-class files where classes are tightly related (e.g. `auth.py` with both `Auth` and `PersonalTokenAuth`); leave file names short (`prs.py`, `repos.py`) and rely on imports for disambiguation.
**Why:** domain folders make "where does X go?" answerable from the domain name alone — phase 2 will add OAuth, which slots into `authentication/` next to `personal_token_auth.py` without touching anything else. One-class-per-file plus matching filenames removes the small-but-cumulative friction of "which file holds this class?" — the answer is mechanical. Re-export `__init__.py`s keep external imports stable as files move within a domain.

### 2026-05-12 — Manual constructor DI now; FastAPI `Depends` in phase 2/3
**Decision:** dependency injection is manual constructor injection in phase 1 — `Fetcher(client)`, wired once inside `cli._run`. When the FastAPI layer lands in phase 2, request-scoped collaborators (the `GithubClient`, the per-request token, eventually a session/DB handle) move to `fastapi.Depends` providers. No standalone DI container (e.g. `dependency-injector`, `injector`, `punq`) until the wiring graph genuinely outgrows what `Depends` handles cleanly.
**Alternatives:** adopt `dependency-injector` now to "future-proof" the wiring; lean on `punq` as a lightweight middle ground; keep manual injection forever.
**Why:** there are ~4 collaborators today and they wire up in one place, so a container would be pure ceremony. `fastapi.Depends` is the de facto DI mechanism for any FastAPI app — using it means our DI surface is already part of a framework the team will know, not a parallel system to learn. A dedicated container only wins past ~15+ services with multiple environment-specific implementations; we'll revisit if phase 3 gets there.

### 2026-05-12 — Load secrets from `.env` via python-dotenv
**Decision:** `cli.py` calls `load_dotenv()` at startup. `.env` is gitignored; `.env.example` is committed as a template. Code still reads from `os.environ` — `.env` only populates the environment, it is never parsed directly by application code.
**Alternatives:** require operators to `export` env vars manually; build a custom config loader; use Pydantic Settings.
**Why:** `.env` is the de facto standard for local secrets and matches what FastAPI/Docker will expect in phase 2/3. Keeping `os.environ` as the single read path means Docker, CI, and `.env` all flow through the same interface — no library lock-in inside fetchers.
