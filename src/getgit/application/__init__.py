"""Application domain — UI-agnostic orchestration and runtime configuration."""

from .app_settings import AppSettings
from .main import run

__all__ = ["AppSettings", "run"]
