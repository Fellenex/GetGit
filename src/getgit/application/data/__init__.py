"""Application-domain data classes — passive carriers, no behavior."""

from .app_settings import AppSettings
from .exit_code import ExitCode
from .scrape_settings import ScrapeSettings
from .user_state import UserState

__all__ = ["AppSettings", "ExitCode", "ScrapeSettings", "UserState"]
