"""Application domain — UI-agnostic orchestration and runtime configuration."""

from .data import AppSettings
from .main import run

__all__ = ["AppSettings", "run"]
