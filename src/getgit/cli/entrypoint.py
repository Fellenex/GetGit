"""CLI entry point — turns argv into the settings pair and hands off to `application.run`."""

import logging
import sys

from dotenv import load_dotenv

from ..application import run
from .argument_parser import ArgumentParser


def main(argv: list[str] | None = None) -> int:
    """Load `.env`, parse `argv`, and execute the scrape.

    `argv` is exposed for testing; production callers leave it `None`
    so argparse reads `sys.argv`. Returns a process exit code.
    """
    load_dotenv()
    _configure_logging()
    app_settings, scrape_settings = ArgumentParser().parse(argv)
    return run(app_settings, scrape_settings)


def _configure_logging() -> None:
    """Route the `getgit` logger's progress to stderr, as the old prints did.

    The reusable core (`application.run`) emits progress through the
    `getgit` logger and attaches no handler of its own (see [ADR-061]);
    the CLI is the entry point that decides progress goes to stderr at
    INFO, formatted as the bare message so output matches the prior
    `print(..., file=sys.stderr)` behaviour. Idempotent — a second
    in-process `main` call (e.g. across tests) won't stack duplicate
    handlers.
    """
    logger = logging.getLogger("getgit")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)


if __name__ == "__main__":
    raise SystemExit(main())
