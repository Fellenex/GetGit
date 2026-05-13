"""CLI domain — argument parsing, runtime settings, and the entry point."""

from .app_settings import AppSettings
from .argument_parser import ArgumentParser
from .main import main

__all__ = ["AppSettings", "ArgumentParser", "main"]
