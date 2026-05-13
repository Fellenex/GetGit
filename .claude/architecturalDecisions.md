# GetGit — Architectural Decision Log

Chronological history of architectural decisions made for GetGit. The format and recording rules live in [`guidelines.md`](guidelines.md) under "Recording architectural decisions" — this file is the log itself.

**Stable IDs:** every entry has an `[ADR-NNN]` identifier in its heading. IDs are assigned in append order and **never change**, so other documents (and other ADRs) can reference them safely. New entries take the next unused number.

If a prior decision is reversed or extended, the original entry is annotated with a `**Reversed YYYY-MM-DD by [ADR-NNN]:**` or `**Updated YYYY-MM-DD:**` note — entries are never silently overwritten. The reversing entry should also lead with `**Reverses [ADR-NNN].**` so the link is bidirectional.

---

### [ADR-001] 2026-05-12 — Roadmap by phase
**Decision:** three phases — Phase 1 (Python CLI, versioned v0.1/v0.2/v0.3 internally), Phase 2 (local FastAPI + OAuth), Phase 3 (cloud-deployed, public URL). The Python core from Phase 1 must stay reusable in 2 and 3 — only the auth source and storage destination change between phases.
**Alternatives:** ship the OAuth web wrapper before dockerizing; combine v0.1 and v0.2 (since the only difference is scope-resolver behavior); skip phase 2 and jump straight to cloud.
**Why:** front-loading the self-only path keeps the surface area small and lets us validate the data shape and JIRA-extraction quality before opening it to arbitrary users. Docker comes before the web wrapper because the web wrapper depends on a known-good runtime. Phase 2 (local web) exists as a deliberate stepping-stone so OAuth and request-time scope resolution are working before we add multi-tenant cloud concerns.

### [ADR-002] 2026-05-12 — JSON as the export format
**Decision:** all collected data is serialized to `.json` files.
**Alternatives:** SQLite, CSV, Parquet.
**Why:** matches GitHub's native API shapes (no lossy flattening); easy to diff and inspect; trivially consumable by phase 2 (FastAPI). CSV stays a downstream concern, not the storage format.

### [ADR-003] 2026-05-12 — Dataclasses for every JSON model
**Decision:** every distinct JSON model has a Python `@dataclass` (or `pydantic` model if validation is needed) in `getgit/models.py`. Fetchers return dataclass instances; serialization to JSON happens at the storage boundary.
**Alternatives:** pass raw dicts everywhere; use TypedDict.
**Why:** dataclasses make the model contract explicit and refactor-safe; phase 2's FastAPI layer can lift them into response models with minimal changes.

### [ADR-004] 2026-05-12 — CLI accepts username as positional argument
**Decision:** the CLI takes a GitHub username as a required positional argument (e.g. `python -m getgit <username>`).
**Alternatives:** infer the username from the PAT's authenticated user; prompt interactively.
**Why:** explicit is better than implicit, and v0.2.0 will need to target arbitrary usernames anyway — using the same interface from v0.1.0 avoids a breaking change.

### [ADR-005] 2026-05-12 — Self vs stranger handled by a single `is_self` branch in the repo fetcher
**Decision:** the only structural difference between scraping yourself and scraping a stranger lives in `getgit/fetchers/repos.py`: `is_self=True` calls `/user/repos` (public + private), `is_self=False` calls `/users/{u}/repos` (public only). Everything downstream (commits, PRs, search) is identical because the GitHub API already filters results by the PAT's visibility.
**Alternatives:** introduce a dedicated `ScopeResolver` class with explicit `can_see(...)` checks at every fetcher; gate the stranger path behind a `--public` flag.
**Why:** the GitHub API enforces visibility server-side, so a client-side resolver would be redundant ceremony at this stage. The `is_self` boolean is the minimum signal needed and keeps fetchers dumb. A real `ScopeResolver` becomes worthwhile in phase 2 when the *viewer* identity comes from OAuth and may differ per request — at that point the boolean grows into an object.

### [ADR-006] 2026-05-12 — v0.2.0 is a hardening release, not a feature release
**Decision:** v0.2.0 ships no new fetchers or CLI surface. Scope: add tests (commits, PR JIRA extraction, pagination, `is_self` branching against a mocked API), handle rate-limit responses gracefully (`X-RateLimit-Remaining` / `Retry-After`), and verify the stranger path end-to-end against a real public account.
**Alternatives:** bundle Docker into v0.2.0; add a `--public` flag to force the stranger path even when targeting yourself.
**Why:** the stranger path already works structurally (see prior decision). The risk in opening it up is correctness and politeness toward GitHub's API, not missing code. Keeping Docker in v0.3.0 preserves the roadmap's separation of concerns: v0.2 = trust the data; v0.3 = trust the runtime.

### [ADR-007] 2026-05-12 — src-layout with `pyproject.toml`
**Decision:** package lives at `src/getgit/`, declared in `pyproject.toml` via `tool.setuptools.packages.find` with `where = ["src"]`. Install with `pip install -e .`; run as `python -m getgit` or the `getgit` console script.
**Alternatives:** flat layout (`getgit/` at repo root); package literally named `src` (no `pyproject.toml`); `requirements.txt` + `PYTHONPATH=src` runtime hack.
**Why:** the src-layout prevents accidental imports from the working directory (a common cause of "tests pass locally but fail in CI" bugs) and forces the package to be installed before it's importable — which mirrors how phase 2 (FastAPI in Docker) will consume it. `pyproject.toml` becomes the single source of truth for dependencies, replacing `requirements.txt` for the package itself.

### [ADR-008] 2026-05-12 — `models/` package with `JSONModel` mixin
**Decision:** models live under `src/getgit/models/` — one file per model (`commit.py`, `pull_request.py`, `report.py`) plus a `base.py` that defines a `JSONModel` mixin with a `to_jsonable()` method. Models are `@dataclass` classes that inherit from `JSONModel`. The package `__init__.py` re-exports the public surface so callers still write `from .models import Commit`.
**Alternatives:** keep a single `models.py` with a free-function `to_jsonable`; make `JSONModel` itself a dataclass parent; reach for Pydantic for runtime validation.
**Why:** as the model count grows (issues, reviews, contributions in later phases), a flat file becomes unwieldy. A mixin keeps serialization logic next to the contract it serializes — `report.to_jsonable()` reads better than `to_jsonable(report)` and removes the temptation to bypass it. `JSONModel` is *not* a dataclass on purpose: mixing dataclass inheritance forces field-ordering rules that subclasses would have to think about. Pydantic stays out for now — dataclasses are stdlib and we don't yet need runtime validation; we'll revisit when the FastAPI layer lands in phase 2.

### [ADR-009] 2026-05-12 — `--max-commits` / `--max-prs` for test runs
**Decision:** each fetcher accepts an optional `limit: int | None` parameter and stops iterating once reached. The CLI exposes `--max-commits` and `--max-prs`. Default is `None` (no cap).
**Alternatives:** a single global `--max` knob; sampling (random N from full result); environment variable instead of CLI flags.
**Why:** per-fetcher limits map directly to the two API surfaces with different cost profiles (per-repo commits vs. search-API PRs). Stopping at the fetcher level avoids paying for paginated calls we'd then discard. Defaulting to `None` keeps production behavior unchanged.

### [ADR-010] 2026-05-12 — `_extract_jira_codes` uses a set
**Decision:** JIRA-code extraction uses a `set` internally and returns `sorted(found)`.
**Alternatives:** keep the order-preserving list-with-`in`-check; `dict.fromkeys` for ordered dedupe; return the set directly.
**Why:** dedupe is O(1) per insert (vs. O(n) for the list scan), and a sorted output makes the JSON deterministic across runs — diffing two reports stays meaningful. Returning a list (not a set) preserves JSON-serializability without special-casing in `JSONModel`.

### [ADR-011] 2026-05-12 — Pytest under `tests/`, mirroring the package layout
**Decision:** test framework is `pytest`, declared as a `[dev]` optional dependency in `pyproject.toml`. Tests live under `tests/getgit/...` mirroring `src/getgit/...`. Pytest config sets `pythonpath = ["src"]` and `--import-mode=importlib`. **Test directories must not contain `__init__.py`** — they would shadow the real `getgit` package and break imports.
**Alternatives:** `unittest` (stdlib, no install needed); flat `tests/` dir without subdirs; rely on `pip install -e .` instead of `pythonpath`.
**Why:** pytest is the de facto standard — concise asserts, fixtures, and a vast plugin ecosystem (will matter when we want HTTP mocking via `respx` or `pytest-httpx`). Mirroring the package keeps "where do I add a test for this file?" trivial. `importlib` import mode plus no `__init__.py` files in `tests/` is the only combination that avoids the namespace collision with the real `getgit` package; `pythonpath` keeps tests runnable without an editable install.

### [ADR-012] 2026-05-12 — Commit→PR linkage built from PR-side, not commit-side
**Decision:** the commit→PR mapping is built by walking `/repos/.../pulls/{n}/commits` for each PR we already fetched, then attaching `pull_request_number` to each commit during materialization. **Updated 2026-05-12:** the index is now built inside `fetch_pull_requests` in the same loop that materializes each `PullRequest`, returned as part of a `PullRequestFetchResult`. The standalone `build_commit_pr_index` was removed.
**Alternatives:** call `/repos/.../commits/{sha}/pulls` for every commit (the obvious per-commit lookup); use the GraphQL `Commit.associatedPullRequests` field per commit; keep PR materialization and indexing as two separate passes over the PR list.
**Why:** per-commit lookups are O(commits), which dominates O(PRs) for any active user. The merged single-pass design doesn't reduce API calls (each PR still needs `/pulls/{n}` plus `/pulls/{n}/commits`), but it eliminates a redundant traversal of the PR list and keeps the two related calls colocated. The `PullRequestFetchResult` wrapper makes the dual-output explicit at call sites instead of returning a bare tuple.

### [ADR-013] 2026-05-12 — Drop `PullRequest.state`; keep only `merged`
**Decision:** removed the `state: str` field. `merged: bool` is the single source of truth.
**Alternatives:** keep both for "self-documenting JSON"; replace with an enum.
**Why:** the search query is hardcoded to `is:closed`, so every PR returned is in one of two terminal states fully determined by `merged_at`. Two fields encoding the same bit invites them to drift. Consumers needing a string label can derive `"merged" if merged else "closed"` trivially.

### [ADR-014] 2026-05-12 — CSV export alongside JSON; one file per row-shaped model
**Decision:** `write_report` emits the canonical JSON plus one CSV per row-shaped model (`<user>.commits.csv`, `<user>.pull_requests.csv`). Columns come from `dataclasses.fields()` order. List-valued fields (currently only `jira_codes`) are joined with `;`. CSV writing lives in `storage.py` — models stay pure data.
**Alternatives:** add a `to_csv_row()` method on `JSONModel`; emit one combined CSV with a discriminator column; ship JSON only and let downstream tools convert.
**Why:** keeping the conversion in storage avoids polluting the model layer with a serialization format that's strictly downstream of `to_jsonable()`. One file per model maps cleanly onto how spreadsheets and BI tools consume tabular data — combining them would force consumers to filter. The `;` join is lossless for JIRA codes (which never contain semicolons) and avoids CSV-quoting edge cases. If a future model becomes deeply nested, that's the trigger to introduce a per-model `to_csv_row()` with a custom flattening rule, but flat dataclasses don't need it yet.

### [ADR-015] 2026-05-12 — Track reviews; split PRs into authored vs participated
**Decision:** the report now carries three PR-side collections: `authored_pull_requests` (search: `author:USER`), `participated_pull_requests` (union of `commenter:USER` and `reviewed-by:USER`, minus authored), and a flat `reviews` list of every review the user submitted on either set. New `Review` model (`pr_repo`, `pr_number`, `index` (1-based ordinal among the user's reviews on that PR), `state`, `submitted_at`, `body`).
**Alternatives:** keep one combined PR list with an `authored_by_user: bool` field; nest reviews inside their PR rather than flattening; use GitHub's `involves:USER` qualifier (covers author/assignee/mentions/commenter, too broad).
**Why:** authored vs participated answer fundamentally different questions ("what did I ship" vs "what did I help with"), so consumers shouldn't have to filter. Flat `reviews` list keeps the model symmetric with `commits` (authorship-as-output regardless of source) and makes the reviews CSV trivially diffable. `commenter` + `reviewed-by` is the most precise way to capture "user touched this PR".

### [ADR-016] 2026-05-12 — `additions`/`deletions` keyed by file extension; `--no-extension-breakdown` opt-out
**Decision:** `PullRequest.additions` and `.deletions` are now `dict[str, int]` keyed by file extension (`{".py": 20, ".yml": 5}`). Empty key `""` is files without an extension. The sentinel key `"*"` means the breakdown was disabled and the value is the aggregate total. Disabled via `--no-extension-breakdown`, which skips the `/pulls/{n}/files` call and reads totals from the `/pulls/{n}` payload we already fetch.
**Alternatives:** keep `int` totals and add a separate `additions_by_extension` field; parse the raw diff ourselves; bake extension grouping into the consumer.
**Why:** consumers asking for per-extension breakdown almost never want both shapes — adding a parallel field is dead weight. Using a sentinel `"*"` keeps the schema stable across both modes (always `dict[str, int]`) so the JSON consumer doesn't need a type-switch. The flag exists because file-level fetches add one paginated call per PR; on huge histories that may be the difference between fitting in a rate-limit budget and not.

### [ADR-017] 2026-05-12 — `comments_by_author` alongside total `comments`
**Decision:** `PullRequest.comments` (all-author total, free from `/pulls/{n}`) stays; new `comments_by_author: int` counts comments the target user authored across both `/issues/{n}/comments` and `/pulls/{n}/comments` (review/inline comments). Costs two extra paginated calls per PR.
**Alternatives:** drop the all-author total; only count for participated PRs and set authored to `0`; use GraphQL to get both counts in one call.
**Why:** for authored PRs the author-self-comment count signals self-discussion; for participated PRs it's the entire reason the PR is in the report. Both numbers belong. GraphQL would consolidate calls but introduces a second API surface for marginal savings — revisit if rate limits become a real ceiling.

### [ADR-018] 2026-05-12 — `_file_extension` falls back to bare basename for extensionless files
**Decision:** files without a suffix (`Dockerfile`, `Makefile`, `.gitignore`) bucket under their full basename instead of `""`.
**Alternatives:** keep the `""` bucket; introduce a sentinel like `"<noext>"`; classify by content type.
**Why:** the `""` bucket conflated meaningfully different filetypes (Dockerfiles vs. Makefiles vs. dotfiles), giving consumers a useless "lots of edits with no extension" cell. The bare basename is what a human would call the type and is unique enough for the per-extension breakdown to remain readable.

### [ADR-019] 2026-05-12 — Dedicated `ArgumentParser` class producing `AppSettings`
**Decision:** CLI arg parsing lives in a class (`getgit.argument_parser.ArgumentParser`) that wraps `argparse.ArgumentParser` via composition and returns an `AppSettings` dataclass (`getgit.settings.AppSettings`). `cli.main` calls `ArgumentParser().parse(argv)` then hands the settings to `_run`.
**Alternatives:** keep the inline argparse in `main`; subclass `argparse.ArgumentParser`; use Click/Typer; pass the raw `argparse.Namespace` directly.
**Why:** decoupling parsing from orchestration means the same fetcher pipeline can be driven by a phase-2 HTTP form or a phase-3 JSON request body — only the producer of `AppSettings` changes. Composition (not subclassing) keeps the public surface tiny and avoids inheriting argparse internals. Click/Typer would be the right call if the CLI grew subcommands, but argparse is stdlib and currently sufficient.

### [ADR-020] 2026-05-12 — One file per `@dataclass`; mirrored test files
**Decision:** every `@dataclass` lives in its own file. New homes: `getgit/settings.py` (`AppSettings`), `getgit/fetchers/pull_request_fetch_result.py` (`PullRequestFetchResult`). Tests follow the same one-file-per-source-file rule under `tests/getgit/...`.
**Alternatives:** group related dataclasses in `models.py` / `results.py` files; rely on a flat test file per concern (e.g., `test_models.py`).
**Why:** a 1:1 file mapping makes "where does this type live?" and "where do I add a test for this file?" mechanical questions with no judgment calls. Costs a few extra files but keeps imports unambiguous and diffs scoped — particularly important as the model count grows in phase 2/3.

### [ADR-021] 2026-05-12 — `GithubClient` class replaces free-function `github_api`
**Decision:** the GitHub-side network surface is now `getgit.github_client.GithubClient`, a class wrapping `httpx.Client`. It exposes `get`, `paginate`, and `viewer_login`, and acts as a context manager. `Auth.client()` returns a `GithubClient` directly; the old `github_api.py` module is gone.
**Alternatives:** keep `paginate` as a free function; subclass `httpx.Client`; introduce a thin GraphQL helper alongside.
**Why:** every fetcher now takes one constructor argument (the client) instead of receiving a raw `httpx.Client` plus importing free helpers. That's the seam phase 2 will need: an OAuth-backed `GithubClient` (or a per-request mock) drops in without changing fetcher code. Composition over `httpx.Client` keeps our public surface narrow — fetchers can't accidentally reach into low-level HTTP details.

### [ADR-022] 2026-05-12 — Fetchers are classes parameterized by `GithubClient`
**Decision:** `RepoFetcher`, `CommitFetcher`, and `PullRequestFetcher` are classes. Each takes a `GithubClient` in `__init__` and exposes its work via methods (`list_repos`, `fetch`, `fetch`).
**Alternatives:** keep the module-level functions and pass the client every call; use a single mega-fetcher class.
**Why:** stateful collaboration with the client is the norm (every method makes calls), so the client becomes a constructor param instead of polluting every signature. Per-domain classes mirror the per-domain modules and stay independently testable. A single mega-fetcher would couple unrelated concerns and grow indefinitely.

### [ADR-023] 2026-05-12 — `PullRequest.jira_codes` is `dict[str, list[str]]` keyed by project prefix
**Decision:** changed the field from `list[str]` to `dict[str, list[str]]`. `{"WD": ["WD-1234", "WD-5678"], "YWFB": ["YWFB-99"]}`. Inner lists are sorted/deduped; outer keys are alphabetical.
**Alternatives:** keep the flat list; use `dict[str, int]` (project → mention count); switch to a custom dataclass.
**Why:** mirrors the `additions`/`deletions` per-extension shape (group by category), which is how consumers want to slice this data ("how many YWFB tickets did this PR touch?"). Inner lists keep the full codes — a count alone would lose the references. CSV gets a nested separator (`|` inside lists, `;` between entries) so the dict-of-lists round-trips through a single cell unambiguously.
**Reversed 2026-05-13 by [ADR-024]:** the bucketing was unnecessary and made the simple case (any code touched?) require an extra step.

### [ADR-024] 2026-05-13 — Revert `jira_codes` to a flat sorted list
**Reverses [ADR-023].**
**Decision:** `PullRequest.jira_codes` is back to `list[str]` — sorted, deduped, e.g. `["WD-1234", "WD-5678", "YWFB-99"]`. CSV serialization is a plain `;`-join. The `_inner` helper in `CsvWriter` was deleted as dead code (no remaining model has dict-of-list values).
**Alternatives:** keep the project-prefix bucketing; switch to `set[str]` (not JSON-serializable without conversion).
**Why:** consumers grouping by project prefix can do `defaultdict(list)` in a one-liner; consumers asking "did this PR touch any tickets?" or "list all tickets" had to flatten the dict first. The bucketing optimized the rarer use case at the cost of the common one. Flat-list is also smaller in JSON output and CSV cells.

### [ADR-025] 2026-05-12 — Public methods/functions appear above private (`_`-prefixed)
**Decision:** within any file (or class), the public surface comes first; `_`-prefixed helpers go below.
**Alternatives:** alphabetical ordering; helpers above their callers (a la C); no rule.
**Why:** reading top-to-bottom should answer "what does this thing do?" before "how does it do it?". This also localizes the public API at a glance without scanning past helpers.

### [ADR-026] 2026-05-12 — Source organized by domain; one class per file; filename = snake_case(class)
**Decision:** every class lives in its own file named after it (`AppSettings` → `app_settings.py`). Files are grouped into domain folders under `src/getgit/`: `application/`, `authentication/`, `cli/`, `exporting/`, `github/` (with `clients/`, `providers/`, `services/`, `data/` subfolders), `infrastructure/` (cross-cutting building blocks; currently just `data/json_model.py`). Each domain has an `__init__.py` that re-exports its public types so external callers do `from getgit.github import PullRequestProvider` instead of digging into module paths. Tests mirror the same layout (`tests/getgit/<domain>/test_<file>.py`).
**Alternatives:** organize by technical layer (`controllers/`, `services/`, `repositories/`); keep multi-class files where classes are tightly related (e.g. `auth.py` with both `Auth` and `PersonalTokenAuth`); leave file names short (`prs.py`, `repos.py`) and rely on imports for disambiguation.
**Why:** domain folders make "where does X go?" answerable from the domain name alone — phase 2 will add OAuth, which slots into `authentication/` next to `personal_token_auth.py` without touching anything else. One-class-per-file plus matching filenames removes the small-but-cumulative friction of "which file holds this class?" — the answer is mechanical. Re-export `__init__.py`s keep external imports stable as files move within a domain.

### [ADR-027] 2026-05-13 — 403 from GitHub locks the client and aborts the scrape
**Decision:** `GithubClient.get` and `.paginate` check the response status; a 403 sets a `_rate_limited` flag on the client and raises a new `RateLimitExceededError` (in `github/clients/`). Subsequent calls raise the same error without hitting the network. `application.run` catches it, prints a one-line summary to stderr, and returns exit code `1` — no report is written.
**Alternatives:** auto-backoff with `Retry-After`; partial-save (write whatever was collected before the 403); silently swallow and continue; differentiate primary rate limit from secondary rate limit from token-scope 403s.
**Why:** GitHub's rate-limit recovery window is up to an hour — retries inside the same run almost never help and just waste the few requests we have left. Failing fast lets the operator address the cause (re-token, wait, use `--max-*`) and re-run. We don't distinguish 403 sub-causes because the response body is unreliable across endpoint families and the operator action is the same. Partial-save was deliberately deferred — useful but adds save-points to every fetcher; revisit if interrupted long runs become routine.
**Updated 2026-05-13:** partial save is now in. Each provider catches `RateLimitExceededError` internally, attaches its partial accumulator (`PullRequestFetchResult`, `list[Commit]`, or `list[dict]` for repos) to `e.partial`, and re-raises. `application.run` catches at the top, dispatches the partial back into the local result vars by type, and writes the report regardless. Exit code becomes `2` to distinguish partial save from full success (`0`).

### [ADR-028] 2026-05-13 — Distribute `models/` between `github/data/` and `infrastructure/data/`
**Decision:** the top-level `models/` domain is gone. GitHub-specific dataclasses (`Commit`, `PullRequest`, `Review`, `AuthorshipReport`) move into `github/data/` alongside `PullRequestFetchResult`. Domain-agnostic building blocks (`JSONModel`) move into a new `infrastructure/data/` domain. `infrastructure/` is the home for anything that's a tool used by domains rather than a domain itself.
**Alternatives:** keep `models/` as the central data home; promote `JSONModel` to a top-level `json_model.py`; nest `infrastructure/` under `github/`.
**Why:** the previous `models/` was an artificial neighbourhood — `Commit` belongs near the providers that produce it, not in a generic bucket alongside an abstract base class. Splitting on the GitHub-specific vs cross-cutting axis matches how the code is actually consumed: providers/services/exporters reach into `github.data` for their domain types, and exporters reach into `infrastructure.data` for the JSON-serialization mixin. `infrastructure/` is the conventional name for "stuff every domain uses but no domain owns" (logging, persistence base classes, serialization helpers).

### [ADR-029] 2026-05-13 — Consolidate GitHub-specific code into `github/` with `clients/`, `providers/`, `data/`
**Decision:** the old top-level `fetchers/` and `github_api/` domains were merged into a single `github/` domain with three subdomains: `clients/` (`GithubClient`), `providers/` (`RepoProvider`, `PullRequestProvider`, `CommitProvider` — formerly `*Fetcher`), and `data/` (`PullRequestFetchResult`). The `*_fetcher.py` files were renamed to `*_provider.py`; their classes followed (`CommitFetcher` → `CommitProvider`, etc.) per the `filename = snake_case(ClassName)` convention. `PullRequestFetchResult` kept its name — it's a result record, not a provider, and the term "fetch result" still describes it accurately. `GithubService` constructor params followed the rename (`repo_fetcher` → `repo_provider`, etc.).
**Alternatives:** keep `fetchers/` and `github_api/` as siblings; only rename files without renaming classes (would violate the filename = class-name rule); rename `PullRequestFetchResult` to `PullRequestProviderResult` (clunky and less descriptive).
**Why:** all three concepts are GitHub-specific and were artificially split across two top-level domains. Co-locating them under `github/` makes the GitHub-vs-everything-else seam visible at a glance, and the `clients/providers/data` triple is a recognizable pattern (transport, repository-style adapters, DTOs). "Provider" is more accurate than "fetcher" because these classes can also count, index, and aggregate — not just fetch — and "provider" is the standard term in the repository/data-source pattern.

### [ADR-030] 2026-05-13 — `services/` domain — `GithubService` facade over per-resource fetchers
**Decision:** new `services/` domain holds higher-level coordinators. First inhabitant: `GithubService(repo_fetcher, pull_request_fetcher, commit_fetcher, settings)`. The service exposes `fetch_repositories(is_self)`, `fetch_pull_requests()`, and `fetch_commits(repos, pr_index)`. Each method threads `AppSettings` (`username`, `max_*`, `fetch_extensions`) into the underlying fetcher so call sites stop re-passing them. The fetchers themselves still own the `GithubClient` they were constructed with — the service is a coordinator, not a new transport.
**Alternatives:** keep the orchestration inline in `application.run`; merge the service into `application/`; put it under `github_api/` (same domain name root); have the service own the `GithubClient` and instantiate the fetchers internally.
**Why:** `application.run` was re-typing `settings.username, limit=settings.max_prs, fetch_extensions=settings.fetch_extensions` at every fetcher call — a textbook signal that those parameters belong on a wrapper. A dedicated `services/` domain (vs. folding into `application/` or `github_api/`) keeps each domain's responsibility narrow: `application/` wires entry points, `github_api/` is the low-level transport, `fetchers/` are per-resource scrapers, and `services/` aggregates them. Constructing fetchers outside the service preserves DI symmetry — the service receives ready-made collaborators instead of building them, which is what FastAPI `Depends` will hand it in phase 2. Method names use snake_case despite the spec's camelCase example, per Python convention.

### [ADR-031] 2026-05-13 — `data/` subdomain inside mixed-content domains
**Decision:** when a domain folder mixes behavior (services, fetchers, writers) with passive data classes, the data classes move into a `data/` subfolder. Currently applied: `application/data/app_settings.py`, `fetchers/data/pull_request_fetch_result.py`. Each `data/__init__.py` re-exports the dataclasses; the parent domain's `__init__.py` re-exports them from `.data` so the public surface is unchanged. Domains that are entirely data (`models/`, `authentication/`) do not get a redundant `data/` folder — the domain itself already plays that role.
**Alternatives:** keep dataclasses next to the behavior they accompany; rename the model files to a `_dto.py` suffix; promote every `data/` collection to its own top-level domain.
**Why:** mixing dataclasses with services in one folder makes the folder listing ambiguous about which file is "the thing" and which is "data the thing operates on". A `data/` subfolder makes that distinction visible at the directory level. The re-export keeps callers writing `from getgit.application import AppSettings` — the move is invisible across the public surface.

### [ADR-032] 2026-05-13 — `additions`/`deletions` are sparse — zero entries omitted
**Decision:** when aggregating per-extension `additions`/`deletions`, an extension is included in a dict only if its accumulated value is non-zero. The two dicts may have different key sets — a `.unity` file with 0 additions and 3 deletions appears in `deletions` only. The same rule applies to the `--no-extension-breakdown` `"*"` total: a PR with zero changes produces `{}` instead of `{"*": 0}`.
**Alternatives:** keep the dicts symmetric for "schema stability"; emit `null` instead of omitting; ship a separate `extensions_touched` field.
**Why:** symmetric zero-padded dicts are noise — every consumer that wants "did this PR touch `.py`?" has to check `value > 0` anyway. Sparse dicts are the truthful representation of what changed. Schema stability isn't lost: the field type is still `dict[str, int]`; consumers iterate keys instead of probing fixed ones.

### [ADR-033] 2026-05-13 — Per-run output subdirectory: `<out>/<username>/<generated_at>/`
**Decision:** `write_report` puts every file under `<out_dir>/<username>/<generated_at>/`, where the timestamp uses `%Y-%m-%d_T%H-%M-%S`. Filenames inside drop the username prefix — `commits.json` instead of `<u>.commits.json`. Each run lands in its own folder, so two runs against the same user don't overwrite each other.
**Alternatives:** keep flat output with timestamped filenames; use ISO-8601 with colons (breaks Windows); skip the username folder and rely on the timestamp alone.
**Why:** the path now carries the metadata that used to live at the top of the unified JSON (`username`, `generated_at`). Hyphens replace colons because Windows refuses paths with `:`. The username folder makes "diff two runs of the same user" trivial without the noise of other users' runs in the same listing.

### [ADR-034] 2026-05-13 — `exporting/` domain with a `Writer` protocol
**Decision:** the old `storage.py` becomes the `exporting/` domain. A `Writer` protocol declares `write(items: list[JSONModel], filename: Path) -> Path`. Two implementations: `JsonWriter` (writes a JSON array) and `CsvWriter` (writes a header + rows, flattening list/dict cells per the existing rules). `report_exporter.write_report(report, out_dir)` is the orchestrator: it calls each writer once per top-level collection (`commits`, `authored_pull_requests`, `participated_pull_requests`, `reviews`), producing **8 files total** (4 collections × 2 formats). The old unified `<username>.json` was dropped — the symmetric per-collection design fits the writer protocol cleanly, and the lost top-level metadata (`generated_at`, `username`) is recoverable from filenames + file mtimes.
**Alternatives:** keep the unified `<username>.json` and write it as a special case outside the writer interface; have `JsonWriter` consume the whole `AuthorshipReport` (breaks the symmetric `list`-shaped contract); ship JSON only and skip the writer protocol entirely.
**Why:** a `Writer` protocol with a single shape is what makes new formats (Parquet, NDJSON, SQLite) drop in without touching the orchestrator. Mixing per-collection and per-document writes through the same interface would have forced a polymorphic data parameter and defeated the abstraction. The JSON-shape change is a real loss for top-level metadata, but the alternative is a leaky writer protocol; downstream consumers wanting the unified shape can join the per-collection files in a single `jq` call.

### [ADR-035] 2026-05-13 — `GithubSettings` replaces `Auth`/`PersonalTokenAuth`
**Decision:** `GithubClient` now takes a `GithubSettings(auth_token, base_url="https://api.github.com", timeout=30.0)` directly — no auth-strategy intermediary. The token enters the system via `AppSettings.access_token`. The CLI's `ArgumentParser` reads it from `GITHUB_TOKEN`; phase 2's HTTP entry point will populate it from the OAuth flow. `application.run` validates presence and raises `RuntimeError` if missing. The `Auth` Protocol and `PersonalTokenAuth` class are deleted as redundant.
**Alternatives:** keep `Auth`/`PersonalTokenAuth` and add `OAuthAuth` later as another implementation; pull the token directly from env inside `GithubClient`; move token validation into `GithubSettings` itself.
**Why:** the `Auth` abstraction was solving a problem we don't have — both PAT and (future) OAuth produce the same artifact (a string token). `GithubSettings` is the actual contract `GithubClient` cares about; routing the token through `AppSettings` makes the CLI/HTTP/test seams explicit. Validation lives in `application.run` because it's where missing-token first matters operationally — `GithubSettings` stays a passive data carrier so tests can build invalid configurations to exercise downstream behavior.

### [ADR-036] 2026-05-13 — `application/` domain — UI-agnostic orchestration
**Decision:** the scrape orchestration lives in `application/main.py` as a public `run(settings: AppSettings) -> int`. `AppSettings` lives in `application/app_settings.py`. `cli/main.py` is now reduced to "load .env, build settings from argv, call `run(settings)`". Phase 2's FastAPI endpoint will follow the same pattern: build `AppSettings` from the request, call `run(settings)`.
**Alternatives:** keep orchestration in `cli/main.py` and have FastAPI duplicate it; introduce an `App` class with a `run` method; route `print` statements through a logger immediately.
**Why:** the moment we have two entry points (CLI + HTTP), they need to share the orchestration without sharing argv parsing or .env loading. Splitting now — while there's only one consumer — is cheaper than untangling later. Stayed with a function not a class because there's no per-instance state to carry; an `App` class with one method would be ceremony. `print(..., file=sys.stderr)` is borderline for a UI-agnostic layer; deferring the swap to structured logging until phase 2 adds a non-CLI consumer that benefits from it.

### [ADR-037] 2026-05-12 — Manual constructor DI now; FastAPI `Depends` in phase 2/3
**Decision:** dependency injection is manual constructor injection in phase 1 — `Fetcher(client)`, wired once inside `cli._run`. When the FastAPI layer lands in phase 2, request-scoped collaborators (the `GithubClient`, the per-request token, eventually a session/DB handle) move to `fastapi.Depends` providers. No standalone DI container (e.g. `dependency-injector`, `injector`, `punq`) until the wiring graph genuinely outgrows what `Depends` handles cleanly.
**Alternatives:** adopt `dependency-injector` now to "future-proof" the wiring; lean on `punq` as a lightweight middle ground; keep manual injection forever.
**Why:** there are ~4 collaborators today and they wire up in one place, so a container would be pure ceremony. `fastapi.Depends` is the de facto DI mechanism for any FastAPI app — using it means our DI surface is already part of a framework the team will know, not a parallel system to learn. A dedicated container only wins past ~15+ services with multiple environment-specific implementations; we'll revisit if phase 3 gets there.

### [ADR-038] 2026-05-12 — Load secrets from `.env` via python-dotenv
**Decision:** `cli.py` calls `load_dotenv()` at startup. `.env` is gitignored; `.env.example` is committed as a template. Code still reads from `os.environ` — `.env` only populates the environment, it is never parsed directly by application code.
**Alternatives:** require operators to `export` env vars manually; build a custom config loader; use Pydantic Settings.
**Why:** `.env` is the de facto standard for local secrets and matches what FastAPI/Docker will expect in phase 2/3. Keeping `os.environ` as the single read path means Docker, CI, and `.env` all flow through the same interface — no library lock-in inside fetchers.

### [ADR-039] 2026-05-13 — `UserState` as a `JSONModel`; `UserStateStore` for persistence
**Decision:** the per-user checkpoint is a `UserState` dataclass extending `JSONModel`, living at `application/data/user_state.py`. It replaces the prior `Checkpoint` plain dataclass. `UserStateStore` (in `application/`) handles file I/O at `output/<username>/state.json` — `save` delegates serialization to `UserState.to_jsonable()`; `load` parses the JSON back manually since `to_jsonable` is one-way.
**Alternatives:** keep `Checkpoint` as a plain dataclass with bespoke serialization in the store; place `UserState` in `github/data/` since the watermarks are about GitHub data; add a `from_jsonable` constructor to `JSONModel` for round-tripping.
**Why:** `JSONModel` already centralizes datetime/dict/list flattening for every other persisted shape; `UserState` having a parallel hand-rolled serializer was duplication. Application-domain placement matches that the data is GetGit's bookkeeping about a target user, not a GitHub-API resource. Adding a `from_jsonable` to the mixin would help here but creates a generic deserialization API we don't have a second use case for yet — revisit when a third reader appears.

### [ADR-040] 2026-05-13 — v0.4.0 introduces periodic ("cron") runs
**Decision:** v0.4.0 ships scheduled, incremental data collection. Each run is bounded (rate-limit-safe) and resumable via `UserState`. The scheduler itself is **external** in v0.4.0 — system cron, Windows Task Scheduler, or a sidecar cron container in `docker compose` triggers `getgit <username>` on an interval.
**Alternatives:** build the scheduler into GetGit itself (long-running daemon process); skip cron entirely and require manual reruns; combine cron + DB tracking up front.
**Why:** the per-user `UserState` plus the `--max-*` caps already make every CLI invocation behave like a "tick" — a separate scheduler doesn't need to know anything about GetGit beyond "run me at this interval against this user". Embedding a scheduler would require GetGit to become a long-running process, which contradicts the v0.3.0 "single `docker compose up` produces output" model. Decision punted on phase-2 scheduling — see the "Open question" note in `guidelines.md`'s Phase 2 section, since the web version's scheduling needs likely shape the phase-3 multi-tenant runtime.

### [ADR-041] 2026-05-13 — Narrow JIRA-code extraction to PR description only
**Decision:** `PullRequestProvider._hydrate_pr` now passes only `pr.get("body")` to `_extract_jira_codes`. Title and branch name are no longer scanned. Comments were never scanned and remain so.
**Alternatives:** keep title + body + branch (the previous behavior); also scan PR comments; keep title and branch but document that the description is canonical.
**Why:** the description is where contributors deliberately link tickets; titles often contain ticket-flavored prefixes like `[hotfix]` or scratch text that pattern-matches the JIRA regex by accident, and branch names suffer the same problem with `WD-1234-fix-typo` repeating something already in the description. Scanning comments would surface tickets the PR author never intended to link. One canonical source — the description — keeps the JIRA list trustworthy.
**Updated 2026-05-13:** title is back in the scan set — the source is now **title + body**, branch and comments stay excluded. Real-world PR titles routinely lead with the JIRA code (`WD-1234: Add feature X`) and the original concern (titles being noisy) didn't show up at the rate expected. Branch names stay excluded because we make typos in them too often (`WD-12343-fix` instead of `WD-1234-fix`) — the body/title combo is human-curated enough to trust.

### [ADR-042] 2026-05-13 — `JSONFileHandler` (was `JsonWriter`); `UserStateRepository` (was `UserStateStore`); handler injected
**Decision:** `JsonWriter` becomes `JSONFileHandler` and gains a `read()` method, accepting any JSON-serializable payload (single `JSONModel`, list of them, or plain dict/list/scalar). It no longer implements the `Writer` protocol — `Writer` stays narrowly for the row-shaped `list[JSONModel]` case (which `CsvWriter` still uses). `UserStateStore` becomes `UserStateRepository` and takes a `JSONFileHandler` as a constructor argument; its `load()` calls `handler.read()` then marshals the raw dict into a `UserState`, and `save()` calls `handler.write(state, path)`.
**Alternatives:** generalize the `Writer` protocol to accept any JSON-able payload (would require special-casing list-vs-scalar in every implementation); keep `JsonWriter` and add a separate `JsonFileReader`; let the repository continue to read/write JSON inline (rejecting the injection request).
**Why:** the JSON-serialization seam now lives in one place (`JSONFileHandler`) for both per-collection report files and per-user state. The repository becomes responsible only for path resolution and `UserState` ↔ raw-dict marshaling, which is the actual repository concern (not "how do we put bytes on disk"). "Repository" is the conventional name for a class that hides the storage medium behind a domain-shaped CRUD interface — the previous "Store" was less precise. The `Writer` protocol stays narrow because broadening it would force `CsvWriter` to gain a code path it doesn't need; better to have two small abstractions (Writer for tabular row shapes, JSONFileHandler for general JSON I/O) than one over-broad one.

### [ADR-043] 2026-05-13 — `IsoDateParser` consolidates ISO-8601 → datetime parsing
**Decision:** ISO-8601 → `datetime` parsing lives in `IsoDateParser.parse(value)` under `src/getgit/infrastructure/dates/`. The previous `_parse_dt` static methods on `PullRequestProvider` and `UserStateRepository` are deleted; both classes now call `IsoDateParser.parse(...)`. The implementation always normalizes a trailing `Z` to `+00:00` before handing to `datetime.fromisoformat`, so the two source flavors (GitHub's `Z`-suffixed timestamps and our own offset-suffixed serialization) flow through one path.
**Alternatives:** leave the duplicates in place (they're 4 lines each); promote `parse` to a module-level function in `infrastructure/dates/`; reach for `dateutil.parser.parse` (heavier dep, more permissive than we need).
**Why:** two copies of the same parser is the start of a drift problem — if we add new behavior (e.g., raise on malformed input, accept naive date-only strings) we'd have to remember to update both. A single `IsoDateParser` is the obvious home, and a class (vs. free function) makes the call sites read self-documentingly (`IsoDateParser.parse(...)`) without imports being mistaken for stdlib calls. `infrastructure/dates/` mirrors `infrastructure/data/` — these are the cross-cutting helpers no domain owns.

### [ADR-044] 2026-05-13 — `exporting/` gets `interfaces/` and `services/` subdomains; `ReportExporter` → `ReportService`
**Decision:** the `exporting/` domain now mirrors the `github/` layout. `Writer` (the protocol) lives at `exporting/interfaces/writer.py`. `ReportExporter` is renamed `ReportService` and lives at `exporting/services/report_service.py`. `CsvWriter` and `JSONFileHandler` stay top-level in `exporting/` since they're concrete leaf classes (neither protocols/abstractions nor orchestrators). Public surface is unchanged via the parent `__init__.py` re-exports.
**Alternatives:** keep `Writer` and the orchestrator at the top of `exporting/`; promote both subdomains but leave the class name `ReportExporter`; subdomain only `interfaces/` (services has only one file).
**Why:** the `clients/`/`providers/`/`services/`/`data/` triple in `github/` has been working; using the same `interfaces/`/`services/` shape in `exporting/` makes "what kind of file is this?" answerable from the path alone. Renaming `ReportExporter` to `ReportService` aligns it with `GithubService` — both are the higher-level orchestrators in their respective domains. `CsvWriter` and `JSONFileHandler` remain top-level because they're not abstractions (so not `interfaces/`) and not orchestrators (so not `services/`); promoting them would create a `writers/` or `handlers/` subdomain with one file each, which is over-organization.

### [ADR-045] 2026-05-13 — `--repo OWNER/NAME` scopes a run to a single repository
**Decision:** new CLI flag `--repo OWNER/NAME` populates `AppSettings.target_repo`. When set, `application.run` skips `RepoProvider.list_repos` entirely and uses `[{"full_name": target_repo}]` directly; `PullRequestProvider.fetch` appends `repo:OWNER/NAME` to all three search queries via `_build_query`; `CommitProvider.fetch` already accepts a `repos` list and works unchanged with the single-element list. `GithubService.fetch_pull_requests` pulls the value from settings, so the public method signature didn't grow.
**Alternatives:** require `OWNER/NAME` as a second positional CLI argument (more compact but conflicts with the existing `username` positional); add a `RepoFilter` class encapsulating the scoping (over-abstracted for one optional string); verify the repo exists via `/repos/{owner}/{name}` before scraping (extra API call for a failure that surfaces naturally).
**Why:** scoping a scrape is a common need — debugging a single PR or pulling fresh data for one project shouldn't require touching every repo the user owns. Skipping repo discovery saves a page (or several) of API calls and makes the run trivially bounded. Using the existing search-query builder for the `repo:` filter keeps the change small; the alternative would be threading a separate filter object through every layer.
