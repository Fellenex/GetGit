"""Enables `python -m getgit ...` by delegating to the CLI entry point."""

from .cli import main

raise SystemExit(main())
