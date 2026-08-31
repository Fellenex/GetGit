# GetGit — Guidelines

This document captures the design decisions made for GetGit. New work should respect these constraints unless explicitly revisited.

User-facing material — what the project does, how to install and run it, output formats, task list — lives in [`README.md`](../README.md). This file is for design contracts and architectural reasoning, not usage docs.

## Roadmap

GetGit ships in three phases. Each phase introduces a new deployment surface; the data model and fetcher core stay reusable across all of them.

### Phase 1 — Python CLI
Operator supplies a PAT and a target username. Runs locally; writes JSON + CSV to disk.

- **v0.1.0** — download own (public + private) data via console.
- **v0.2.0** — hardening release: tests, rate-limit handling, verify the stranger-public-data path end-to-end.
- **v0.3.0** — dockerize so a single `docker compose up` produces the output files. This is a *packaging/reproducibility* milestone (no local Python/venv setup for the operator), independent of scheduling; the container mounts `output/` as a volume so a run's files land on the host.
- **v0.4.0** — periodic ("cron") runs that incrementally build a user's history over time. Each invocation is bounded (rate-limit-friendly) and resumable via the per-user `UserState` checkpoint. **Baseline is host cron** (or Task Scheduler) firing a dedicated bounded `task` target — the checkpoint is already an on-disk file, so nothing extra is needed to persist state between runs. The v0.3.0 Docker image is an *optional* deployment variant, not a prerequisite; running the scheduled scrape in a container is where the mounted `output/` volume matters (see [ADR-050]). Does **not** reuse the uncapped `startup` task — a cron target needs its own tuned caps so one run fits inside a rate-limit window.

### Phase 2 — Local web wrapper
FastAPI + GitHub OAuth running on the operator's machine. Any logged-in user can pull their own data (public + private) or anyone else's public data.

**Open question — scheduling parity with v0.4.0:** the cron pattern from v0.4.0 needs a translation in the web version. Candidates: a server-side scheduler (Celery, APScheduler, or FastAPI's lifespan + `asyncio.create_task` for in-process intervals); GitHub Actions firing at our HTTP endpoint on a schedule; per-user opt-in subscriptions persisted to a DB and dispatched by a worker. Decide before adding scheduling to phase 2; the chosen mechanism likely shapes the phase-3 multi-tenant runtime too.

### Phase 3 — Cloud-deployed, web-accessible
Hosted FastAPI service reachable at a public URL. Any GitHub user can sign in and pull data without installing anything. Introduces multi-tenant concerns (per-user token storage, persistent results storage, isolation between users, abuse/quota controls) that don't exist in phase 2.

The Python core from phase 1 must remain reusable in phases 2 and 3. The auth-token source and the storage destination are the only layers expected to change between phases.

## Architecture

The current source layout, by domain:

```
src/getgit/
├── application/           # UI-agnostic orchestration
│   ├── data/              #   AppSettings, ScrapeSettings, UserState, ExitCode
│   ├── main.py            #   run(settings) — the entry point providers and exporters share
│   ├── user_state_repository.py  # file-backed UserState load/save
│   └── user_state_service.py     # UserState load/advance/save coordination
├── cli/                   # ArgumentParser, main()
├── exporting/             # Writers + JSON file handler + report orchestration
│   ├── interfaces/        #   Writer protocol
│   ├── services/          #   ReportService
│   ├── csv_writer.py      #   CsvWriter
│   └── json_file_handler.py
├── github/                # Everything GitHub-specific (service → provider → client)
│   ├── clients/           #   GithubClient (one typed endpoint method per route), GithubSettings, RateLimitExceededError, RepositoryAccessError
│   ├── data/              #   wire response objects (RepoSummary, PullRequestDetail, …) + domain models (Commit/PullRequest/Review) + AuthorshipReport/GithubScrapeResult
│   ├── providers/         #   GithubProvider (unravels response objects into domain objects)
│   └── services/          #   GithubService (facade over client + provider)
└── infrastructure/        # Cross-cutting building blocks
    ├── data/              #   JSONModel
    └── dates/             #   IsoDateParser
```

### Authentication

`GithubSettings(auth_token, base_url, timeout)` is the only auth concept — a passive config carrier. It lives in `github/clients/` next to the `GithubClient` it configures (there is no separate `authentication/` domain — a one-class domain wasn't earning its place; see [ADR-052]). There is no `Auth` protocol or `PersonalTokenAuth` strategy class; both were removed once it became clear the only artifact every implementation produced was a string token. The token enters via `AppSettings.access_token` (CLI reads `GITHUB_TOKEN` from env; phase 2's HTTP entry point will populate it from OAuth).

### Self vs stranger scope

The only client-side difference between scraping yourself and scraping a stranger lives in `GithubProvider.list_repos(username, is_self=...)`, which picks between two `GithubClient` endpoints: `is_self=True` → `list_own_repos()` (hits `/user/repos` with `affiliation=owner,collaborator,organization_member` so org-owned and collaborator repos are discovered, not just owned ones — see [ADR-046]); `is_self=False` → `list_user_repos(username)` (hits `/users/{u}/repos`, public owned repos only). Everything downstream is identical because the GitHub API enforces visibility server-side based on the PAT. A dedicated `ScopeResolver` will make sense in phase 2 when the *viewer* identity comes from OAuth and varies per request.

### The GitHub domain layering: client → provider → service

The domain reads top-to-bottom with one responsibility per layer (see [ADR-058], [ADR-059] — issue [#17](https://github.com/Fellenex/GetGit/issues/17)):

```
main.py → GithubService → GithubProvider → GithubClient → GitHub REST
          (orchestration)  (raw→domain)     (routes+transport)
```

- **`GithubClient` (`clients/`)** owns *every* GitHub route string, query-param shape, pagination call, and raw-JSON dict-key access. It exposes one typed method per route (`list_own_repos`, `list_user_repos`, `search_issues`, `list_repo_commits`, `get_pull_request`, `list_pull_request_{files,reviews,commits}`, `list_{issue,review}_comments`, `viewer_login`), each returning a **wire-shape response object** (`RepoSummary`, `IssueSearchResult`, `PullRequestDetail`, `PullRequestFile`, `PullRequestReview`, `Comment`, `CommitPayload`) with timestamps already parsed. `paginate`/`get` are private (`_paginate`/`_get`) — nothing outside the client constructs route strings. A rate-limit 403 still locks the client and raises `RateLimitExceededError`; a per-resource 403/404/409/422 surfaces as a plain `httpx.HTTPStatusError` for the caller to classify.
- **`GithubProvider` (`providers/`)** is the single raw→domain layer (it replaced the former `RepoProvider`/`PullRequestProvider`/`CommitProvider`). It consumes response objects and emits the domain `Commit`/`PullRequest`/`Review` objects, holding all business logic (JIRA extraction, extension breakdown, self-vs-stranger scope, comment counting, commit→PR index, `merged`/comment-sum derivations, search-query composition) and the partial-result/skip/422 error contract — but no route strings. `fetch_pull_requests(...)` returns a `GithubScrapeResult`; `fetch_commits(...)` returns `list[Commit]`; `list_repos(...)` returns `list[RepoSummary]`.
- **`GithubService` (`services/`)** bundles a `GithubProvider` + `ScrapeSettings` and exposes `fetch_repositories`, `fetch_pull_requests`, `fetch_commits`, so call sites stop re-threading `username`/`max_*`/`fetch_extensions`/`since*` — those flow from settings + `UserState`. `GithubService.build(client, settings)` is the composition root: it constructs the `GithubProvider` from one `GithubClient` so `application.run` never imports it (see [ADR-049]). `run` still owns the `GithubClient` lifecycle (the `with` block wraps the whole pipeline, including error handling).

### Storage / cache

Today: JSON + CSV files written by `ReportService` (in `exporting/`) to a per-run subdirectory `output/<username>/<generated_at>/`. `ReportService.write_report(username, commits, pr_result, out_dir, *, generated_at)` is the sole entry point: it assembles the `AuthorshipReport` from the collected pieces (via a private `_generate_report`) and persists it, so `application.run` neither constructs the model nor knows the file layout (see [ADR-049], [ADR-052]). Per-user incremental state lives at `output/<username>/state.json` via `UserState` + `UserStateRepository` (in `application/`). `UserStateService` sits over the repository and owns the watermark *transition* logic (`load_current_state()` / `save_new_state(...)`), so `application.run` deals in domain operations rather than raw load/save plus arithmetic; the repository stays pure file I/O (see [ADR-051]). Phase 3 will need a persistent store (DB or object storage) and per-user isolation. ETags + `If-None-Match` are the mechanism for not re-spending quota on unchanged data — wire them in when caching becomes a real constraint.

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
- **On a *rate-limit* 403, `GithubClient` locks itself and raises `RateLimitExceededError` for every subsequent call.** A 403 counts as a rate limit only when it carries a `Retry-After` header or `X-RateLimit-Remaining: 0` (see [ADR-047]); each `GithubProvider` fetch method catches the error, attaches its partial accumulator to `e.partial`, and re-raises. The orchestrator catches at the top, writes a partial report from whatever was collected, and returns exit code `2`. No automatic backoff/retry — the operator decides when to re-run.
- **A non-rate-limit 403 (per-resource access denial, e.g. an org repo behind SAML SSO) surfaces as a plain `httpx.HTTPStatusError` and does *not* lock the client.** `GithubProvider.fetch_commits` skips such a repo (alongside `404`/`409`) and keeps walking, so one inaccessible repo doesn't derail the run.
- Always set ETag headers when caching is added to avoid spending quota on unchanged data.

## Conventions

- Don't add features, abstractions, or error handling beyond what the current task requires.
- Trust internal code; validate only at system boundaries (PAT input, GitHub API responses, user-supplied usernames).
- Default to no inline comments. Add one only when the *why* is non-obvious.
- **Every function and class gets a docstring.** Even one-liners. State *what* it does and, when it isn't obvious, *why*. Document non-trivial parameters and return shapes. Module-level docstrings are encouraged when a file's role isn't clear from its name.
- **Public methods/functions appear above private ones** (`_`-prefixed) in every file. Reading top-to-bottom should walk the public surface first, then drop into helpers.
- **Module-level helpers belong inside the class they support.** If a function or constant only exists to serve one class in the same file, it lives on that class as a `_`-prefixed method (`@staticmethod`/`@classmethod` when it doesn't need `self`) or class-level constant. Keeps the public surface = the class.
- **One class per file.** A file may contain module-level helper functions or constants that support its class, but never two classes.
- **Filenames mirror their class name** in `snake_case`. `AppSettings` lives in `app_settings.py`; `JSONModel` in `json_model.py`. The matching is mechanical so nothing is hidden.
- **Reusable test support classes** (fakes, recording test doubles, fixtures) live under `tests/_support/<domain>/` — e.g. `tests/_support/github/fake_github_client.py`. One class per file, same naming convention. Test modules import via `from _support.github import FakeGithubClient`. `tests/` is on `pytest`'s `pythonpath` so `_support` is a top-level package; this is the *only* `__init__.py`-having tree under `tests/`.
- **Don't grow a bespoke fake class for every scenario.** A single, generic, reusable helper (`FakeGithubClient` for per-URL responses) is fine. One-off behaviors — raising a specific error, recording a specific call, returning a specific response — should use `unittest.mock.Mock(spec=...)` or `Mock(side_effect=...)` directly in the test.
- **Prefer real objects over fakes when the real one is cheap to build.** `httpx.Response`, `httpx.Request`, dataclasses — construct the real thing. Fake the *transport* (the `_http` field on `GithubClient`), not the value types it returns.
- **Source is organized by domain**, not by technical layer. Each domain is a folder under `src/getgit/` with an `__init__.py` that re-exports the public types. See the layout under "Architecture" above for the current set of domains.
- Prefer editing existing files over creating new ones.

## Architecture diagram

A `.drawio` dependency diagram lives at [`docs/architecture.drawio`](../docs/architecture.drawio). It shows every source file/class as a box, organized in left-to-right columns: **Client → Endpoint → Service → Repository → Source / Models**.

**The diagram is generated, not hand-drawn.** [`docs/generate_architecture.py`](../docs/generate_architecture.py) emits `architecture.drawio` from a declarative box/edge spec (the `COLUMNS` and `EDGES` tables at the top of the file). Layout — box heights, y-positions, which side each arrow leaves/enters, fan-out spacing — is computed from that spec so the constraints below hold by construction. Edit the spec, don't nudge geometry in a drawio editor (a hand edit is lost the next time the script runs). Layout invariants the script enforces: cross-column edges exit the **right** side of the source and enter the **left** side of the target; boxes grow tall enough to fan all their arrows on that short side; single-user classes sit as satellites immediately right of their one user.

**Update cadence:** the diagram is refreshed only when a new `git tag` is cut (e.g. `v0.1.2`, `v0.2.0`), not on every commit. Updating it per commit would be expensive upkeep relative to the value, and most readers care about the architecture as it stood at a release boundary. When tagging a new version:

1. Edit the `COLUMNS`/`EDGES` spec in [`docs/generate_architecture.py`](../docs/generate_architecture.py) so it matches the current source tree, then run `python docs/generate_architecture.py`.
2. Verify the result: no two boxes overlap (≥70px apart within a column), and no edge segment passes through a non-endpoint box. The long cross-column diagonals are routed explicitly in the script's pass 3 — re-check those if you move columns.
3. Commit both the script change and the regenerated `architecture.drawio` in the same commit as the version bump (the one being tagged).

If you discover the diagram is stale mid-cycle (something already shipped that isn't reflected), wait for the next tag — don't rush a one-off update.

## Recording architectural decisions

The chronological log of decisions lives in [`architecturalDecisions.md`](architecturalDecisions.md) — append new entries there, not here. This file owns the *format and process*; the log file owns the *history*.

An "architectural decision" includes:

- How code is organized: module boundaries, class/function structure, design patterns
- Library or framework choices
- Data-shape contracts (model definitions, serialization formats)
- Error-handling, caching, storage, or auth strategies
- **Any time a choice is made between two or more options**, even if the alternatives feel obvious — the rejected options matter for future readers

Trivial implementation details (variable names, one-line refactors) do not belong in the log.

**Format** — append entries to `architecturalDecisions.md` in chronological order. Each entry gets a stable `[ADR-NNN]` identifier (next unused number, zero-padded to 3 digits) so other documents can link to it:

```
### [ADR-NNN] YYYY-MM-DD — Short title
**Decision:** what was chosen.
**Alternatives:** what was considered and rejected.
**Why:** the reasoning, including any constraints or future-phase implications.
```

IDs **never change** once assigned. If a prior decision is reversed, annotate the original entry with a `**Reversed YYYY-MM-DD by [ADR-NNN]:**` (or `**Updated YYYY-MM-DD:**`) note, and the reversing entry leads with `**Reverses [ADR-NNN].**`. Never silently overwrite.

