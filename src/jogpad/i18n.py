"""Message catalogs.

Every user-facing string goes through `t()` with a literal key, so that
`scripts/check_i18n.py` can find it. English and German must be complete.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

LOCALES_DIR = Path(__file__).parent / "locales"
FALLBACK = "en"


@cache
def _catalog(language: str) -> dict[str, str]:
    path = LOCALES_DIR / f"{language}.json"
    if not path.exists():
        return {}
    data: dict[str, str] = json.loads(path.read_text(encoding="utf-8"))
    return data


def messages(prefix: str, language: str) -> dict[str, str]:
    """All messages starting with `prefix`, for the web page."""
    merged = {**_catalog(FALLBACK), **_catalog(language)}
    return {key: text for key, text in merged.items() if key.startswith(prefix)}


def t(key: str, language: str = FALLBACK, **values: object) -> str:
    text = _catalog(language).get(key) or _catalog(FALLBACK).get(key) or key
    return text.format(**values)
