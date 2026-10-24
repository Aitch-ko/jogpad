"""Check the message catalogs against the code.

Fails when a key used in the code is missing from English or German, or when
English and German disagree on their keys. Other languages only get a report:
a new message must not block every pull request until all translators catch up.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "jogpad"
LOCALES = SRC / "locales"
REQUIRED = ("en", "de")
# t("key", ...) in Python and in the web page's JavaScript, and the core's
# self._notify("key", ...), which calls t() itself.
KEY_CALL = re.compile(r"""\b(?:t|_notify)\(\s*["']([a-z0-9_.]+)["']""")


def used_keys() -> set[str]:
    keys: set[str] = set()
    for pattern in ("*.py", "*.js"):
        for path in SRC.rglob(pattern):
            keys |= set(KEY_CALL.findall(path.read_text(encoding="utf-8")))
    return keys


def main() -> int:
    used = used_keys()
    catalogs = {
        p.stem: set(json.loads(p.read_text(encoding="utf-8"))) for p in LOCALES.glob("*.json")
    }
    errors = []
    for lang in REQUIRED:
        missing = sorted(used - catalogs.get(lang, set()))
        if missing:
            errors.append(f"{lang}: missing {', '.join(missing)}")
    if catalogs.get("en", set()) != catalogs.get("de", set()):
        diff = sorted(catalogs.get("en", set()) ^ catalogs.get("de", set()))
        errors.append(f"en and de differ in: {', '.join(diff)}")
    for lang, keys in sorted(catalogs.items()):
        if lang not in REQUIRED and used - keys:
            print(f"note: {lang} lacks {len(used - keys)} of {len(used)} messages")
    unused = sorted(catalogs.get("en", set()) - used)
    if unused:
        print(f"note: unused keys: {', '.join(unused)}")
    for error in errors:
        print(f"error: {error}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
