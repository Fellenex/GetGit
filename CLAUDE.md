# Process
The process lives in [`.claude/guidelines.md`] — roadmap, architecture, conventions, and the recording-format for architectural decisions.

# Architectural decision log
Historical decisions (the *why* behind every structural choice the project has made) live in [`.claude/architecturalDecisions.md`]. New entries get appended there in chronological order. Reversed/updated entries are annotated in place — never silently overwritten.

# Project README
User-facing material (what the project does, install/run instructions, CLI flags, output formats, task list) lives in [`README.md`]. Keep duplication out of `.claude/guidelines.md`; if a fact is for end users, it belongs in the README.

# Working in this repo

**What it is:** Phase-1 Python CLI (`python -m getgit <username>`) that scrapes a GitHub user's authorship — commits, PRs, reviews, JIRA codes — to JSON + CSV. Currently v0.2.0. See the README for the phase roadmap.

**The invariant that governs every design choice:** the Phase-1 core must stay reusable in Phase 2 (local FastAPI+OAuth) and Phase 3 (cloud). *Only the auth-token source and the storage destination change between phases.* Check new code against this before adding a phase-specific concern to the core.

## Commands
All day-to-day tasks run through [Task](https://taskfile.dev) → Docker (only Docker needed; no local Python/venv). One-time: `cp .env.example .env` and paste your PAT into `GITHUB_TOKEN`.
- Test: `task test` (builds the dev image, runs `pytest` inside it — read the container output for results)
- Scrape (cheap, capped): `task startup-tiny -- <username>`
- Scrape (full, no caps): `task startup -- <username>`
- Scrape (single repo): `task startup-repo -- <username> --repo OWNER/NAME`
- Regenerate the arch diagram: `task generate-diagram` (runs locally — Python 3.10+, no Docker — the lone exception)

CLI flags (`--max-commits`, `--no-extension-breakdown`, …) pass straight through after `--`; the container entry point is `python -m getgit`, so every README flag works unchanged. Local (non-Docker) fallback: `pip install -e ".[dev]"` then `pytest` / `python -m getgit <username>`.

## Code conventions (enforced — see `guidelines.md` for the full list)
- **One class per file**; filename is `snake_case(ClassName)` (`AppSettings` → `app_settings.py`). Never two classes in a file.
- **Source is organized by domain**, not layer. Each domain folder under `src/getgit/` has an `__init__.py` that re-exports its public types; import from the domain (`from getgit.github import PullRequestProvider`), not the module path.
- **Public methods/functions above private** (`_`-prefixed) in every file.
- **Module-level helpers fold into the class they serve** as `_`-prefixed (static/class) methods — the public surface stays = the class.
- **Every function and class gets a docstring**, even one-liners.
- **Minimalism:** don't add features, abstractions, or error handling beyond what the task needs. Validate only at boundaries (PAT, API responses, usernames) — trust internal code. The ADR log is full of "rejected: over-abstracted"; match that bar.
- Prefer editing existing files over creating new ones.

## Tech guardrails (don't reach past these without an ADR)
HTTP: `httpx`, **not** PyGithub. Stdlib `argparse` (not Click/Typer) and `@dataclass` (not Pydantic) for now. Manual constructor DI — **no** DI container. Adding a dependency is an architectural decision.

## Testing
- Tests mirror the package under `tests/getgit/...`. **No `__init__.py` under `tests/`** except `tests/_support/` — it would shadow the real package.
- Reusable fakes live in `tests/_support/<domain>/` (one class per file, imported as `from _support.github import FakeGithubClient`). For one-off behavior use `unittest.mock.Mock(spec=...)` directly — don't grow a fake per scenario. Prefer real value objects (`httpx.Response`, dataclasses); fake the transport, not the values.

## Process rituals
- **Any choice between two or more options → append an ADR** to [`.claude/architecturalDecisions.md`] (format in `guidelines.md`). Stable `[ADR-NNN]` IDs **never change**; reversed/updated entries are annotated in place, never overwritten. The rejected alternatives are the point.
- **The architecture diagram is generated, not drawn.** Edit the spec in [`docs/generate_architecture.py`] and run `task generate-diagram` — never nudge geometry in a drawio editor. Refresh it only when cutting a `git tag`, not per commit.

## Quick reference — exit codes ([`src/getgit/application/data/exit_code.py`])
`0` success · `2` partial save (rate-limited mid-scrape) · `3` repo-access error (`--repo` 422) · `1` is Python's default for an unhandled exception (not used).
