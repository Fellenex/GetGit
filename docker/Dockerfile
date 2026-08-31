# syntax=docker/dockerfile:1
#
# GetGit packaging image (v0.3.0). Builds a self-contained image whose entry
# point is `python -m getgit`, so container CLI args are the same GetGit args
# documented in the README. The operator needs no local Python/venv — only
# Docker. `output/` is a mounted volume at runtime (see docker-compose.yml), so
# a run's JSON/CSV files and the per-user state.json land on the host.
FROM python:3.12-slim

# Fail fast and unbuffer stdout/stderr so container logs stream in real time.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Copy only what `pip install .` needs (packaging metadata + source), so this
# layer is rebuilt only when the package itself changes, not on every edit.
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

# `--out` defaults to ./output, which resolves to /app/output here; that path
# is where docker-compose.yml bind-mounts the host's ./output directory.
# Exec-form ENTRYPOINT so container args append as CLI args to `python -m getgit`.
ENTRYPOINT ["python", "-m", "getgit"]
