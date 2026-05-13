"""CLI domain — argument parsing and the console entry point."""

from .argument_parser import ArgumentParser
from .main import main

__all__ = ["ArgumentParser", "main"]
