# GetGit

A tool for scraping GitHub authorship data — commits, pull requests, and associated metadata — for a given user.

## Status

Phase 1: Python CLI core. Authenticates via a GitHub Personal Access Token (PAT) and pulls data for a single user.

Phase 2 (planned): FastAPI web wrapper with GitHub OAuth login, allowing any user to pull their own data (public + private) or anyone else's public data.

## Data collected

**Commits**
- Total count
- Datetime
- Commit messages

**Pull Requests** (merged and closed)
- Total count
- Lines added / removed per PR
- Comment count per PR
- Associated JIRA ticket codes (extracted via regex from title, body, and branch name — pattern: `[A-Z]{2,10}-\d+`)

## Setup

```bash
pip install -r requirements.txt
export GITHUB_TOKEN=ghp_your_token_here
python -m getgit <username>
```

## Architecture

See [.claude/guidelines.md](.claude/guidelines.md) for the design contract that shapes this project.
