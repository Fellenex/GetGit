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
- **On 403, `GithubClient` locks itself and raises `RateLimitExceededError` for every subsequent call.** Each provider catches the error, attaches its partial accumulator to `e.partial`, and re-raises. The orchestrator catches at the top, writes a partial report from whatever was collected, and returns exit code `2`. No automatic backoff/retry — the operator decides when to re-run.
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
- **Source is organized by domain**, not by technical layer. Each domain is a folder under `src/getgit/` with an `__init__.py` that re-exports the public types. Current domains: `authentication/`, `cli/`, `fetchers/`, `github_api/`, `models/`. Single-file utilities (e.g. `storage.py`) stay top-level until they grow a class to organize.
- Prefer editing existing files over creating new ones.

## Architecture diagram

A `.drawio` dependency diagram lives at [`docs/architecture.drawio`](../docs/architecture.drawio). It shows every source file/class as a box, organized in left-to-right columns: **Client → Endpoint → Service → Repository → Source / Models**.

**Update cadence:** the diagram is refreshed only when a new `git tag` is cut (e.g. `v0.1.2`, `v0.2.0`), not on every commit. Updating it per commit would be expensive upkeep relative to the value, and most readers care about the architecture as it stood at a release boundary. When tagging a new version:

1. Open `docs/architecture.drawio` in [diagrams.net](https://app.diagrams.net) (or any drawio editor).
2. Add/remove boxes and arrows so the diagram matches the current source tree.
3. Re-verify the layout constraints — every box ≥80px from its neighbours, no arrow overlaps any box or other arrow, columns left-to-right by responsibility.
4. Commit the updated diagram in the same commit as the version bump (the one being tagged).

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

