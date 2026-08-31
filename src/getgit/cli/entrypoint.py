"""CLI entry point — turns argv into an `AppSettings` and hands off to `application.run`."""

from dotenv import load_dotenv

from ..application import run
from .argument_parser import ArgumentParser


def main(argv: list[str] | None = None) -> int:
    """Load `.env`, parse `argv`, and execute the scrape.

    `argv` is exposed for testing; production callers leave it `None`
    so argparse reads `sys.argv`. Returns a process exit code.
    """
    load_dotenv()
    settings = ArgumentParser().parse(argv)
    return run(settings)


if __name__ == "__main__":
    raise SystemExit(main())
