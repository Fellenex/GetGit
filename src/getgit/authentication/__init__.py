"""Authentication domain — strategies for authenticating against GitHub."""

from .auth import Auth
from .personal_token_auth import PersonalTokenAuth

__all__ = ["Auth", "PersonalTokenAuth"]
