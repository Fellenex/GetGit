# syntax=docker/dockerfile:1
#
# GetGit development/test image. Unlike the runtime image (docker/Dockerfile),
# this ships the test suite and dev dependencies and runs pytest by default, so
# `task test` executes the suite in a clean, reproducible container with no
# local Python/venv. Built against docker/dev.Dockerfile.dockerignore, which —
# unlike the runtime ignore — keeps tests/ in the build context.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Ship packaging metadata, source, and the suite; install with the dev extra
# (pytest) so the image is self-contained for testing.
COPY pyproject.toml ./
COPY src ./src
COPY tests ./tests
RUN pip install --no-cache-dir ".[dev]"

# Default command runs the suite; `docker run getgit-dev` (or extra args) execs pytest.
CMD ["pytest"]
