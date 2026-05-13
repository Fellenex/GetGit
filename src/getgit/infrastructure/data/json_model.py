"""Shared serialization mixin for every model in this package."""

from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any


class JSONModel:
    """Mixin for dataclasses that need to serialize to JSON-safe primitives.

    Subclasses must also be decorated with `@dataclass`. The mixin
    deliberately is *not* a dataclass itself — that way it imposes no
    fields and avoids the inheritance-ordering rules that bite mixed
    dataclass hierarchies.
    """

    def to_jsonable(self) -> dict:
        """Return a dict of JSON-safe primitives representing this instance."""
        if not is_dataclass(self):
            raise TypeError(
                f"{type(self).__name__} subclasses JSONModel but is not a @dataclass"
            )
        return {k: self._jsonable(v) for k, v in asdict(self).items()}

    @classmethod
    def _jsonable(cls, obj: Any) -> Any:
        """Recursively coerce dataclasses, datetimes, and containers into JSON-safe primitives."""
        if isinstance(obj, JSONModel):
            return obj.to_jsonable()
        if is_dataclass(obj):
            return {k: cls._jsonable(v) for k, v in asdict(obj).items()}
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, list):
            return [cls._jsonable(v) for v in obj]
        if isinstance(obj, dict):
            return {k: cls._jsonable(v) for k, v in obj.items()}
        return obj
