"""Cleans everything before it is written to the audit trail: no secrets, bounded size."""

import re
from collections.abc import Iterable, Mapping
from typing import Any

REDACTED = "[REDACTED]"
MAX_DEPTH = 5
MIN_SECRET_LENGTH = 8  # shorter values would also wipe ordinary words

_SECRET_KEY = re.compile(
    r"api[_-]?key|secret|password|passwd|authorization|credential|(access|auth|bearer|id)[_-]?token",
    re.IGNORECASE,
)
_SECRET_VALUE = re.compile(r"sk-ant-[\w-]{10,}|tvly-[\w-]{10,}|Bearer\s+[\w.~+/-]{10,}")


class Sanitizer:
    """Redacts known secrets and secret-looking values, and truncates long text and lists."""

    def __init__(self, secrets: Iterable[str], max_text_chars: int, max_items: int) -> None:
        self._secrets = tuple(s for s in secrets if len(s) >= MIN_SECRET_LENGTH)
        self._max_text_chars = max_text_chars
        self._max_items = max_items

    def clean(self, value: Any, depth: int = 0) -> Any:
        """Return a JSON-friendly, redacted and bounded copy of value."""
        if depth > MAX_DEPTH:
            return "[max depth]"
        if value is None or isinstance(value, bool | int | float):
            return value
        if isinstance(value, str):
            return self._clean_text(value)
        if isinstance(value, Mapping):
            return {str(key): self._clean_entry(key, item, depth) for key, item in value.items()}
        if isinstance(value, list | tuple | set | frozenset):
            return self._clean_items(list(value), depth)
        return self._clean_text(str(value))

    def _clean_entry(self, key: Any, item: Any, depth: int) -> Any:
        if _SECRET_KEY.search(str(key)):
            return REDACTED
        return self.clean(item, depth + 1)

    def _clean_items(self, items: list[Any], depth: int) -> list[Any]:
        cleaned = [self.clean(item, depth + 1) for item in items[: self._max_items]]
        if len(items) > self._max_items:
            cleaned.append(f"[+{len(items) - self._max_items} items]")
        return cleaned

    def _clean_text(self, text: str) -> str:
        for secret in self._secrets:
            text = text.replace(secret, REDACTED)
        text = _SECRET_VALUE.sub(REDACTED, text)
        if len(text) <= self._max_text_chars:
            return text
        return f"{text[: self._max_text_chars]}[+{len(text) - self._max_text_chars} chars]"
