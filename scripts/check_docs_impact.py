"""Fail a pull request that changes code but not the docs, unless it says so.

    python scripts/check_docs_impact.py <base-ref> [--not-needed]

`--not-needed` is passed by CI when the PR carries the label `docs: not needed`.
Generated reference pages do not count as a docs change: they follow the code
by themselves and say nothing about what a user has to do differently.
"""

from __future__ import annotations

import subprocess
import sys

CODE = ("src/",)
DOCS = ("docs/", "README.md")
GENERATED = ("docs/reference/",)


def changed_files(base: str) -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [line for line in out.splitlines() if line]


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    files = changed_files(argv[0])
    code = [f for f in files if f.startswith(CODE)]
    docs = [f for f in files if f.startswith(DOCS) and not f.startswith(GENERATED)]
    if not code or docs or "--not-needed" in argv:
        return 0
    print("This pull request changes code but no documentation:")
    for f in code:
        print(f"  {f}")
    print("Update docs/ or README.md, or add the label 'docs: not needed'.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
