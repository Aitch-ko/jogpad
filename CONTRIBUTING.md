# Contributing to jogpad

Thanks for helping. This file is the rulebook; CI enforces most of it.

## Language

Everything in this repository is written in English: code, comments,
documentation, issues, pull requests and commit messages. Translations of the
user interface live in `src/jogpad/locales/`.

## Workflow

1. Open an issue first for anything larger than a fix, so we can agree on the
   approach.
2. Work on a branch, never on `main`.
3. Open a pull request. Its title follows
   [Conventional Commits](https://www.conventionalcommits.org/): `feat: ...`,
   `fix: ...`, `docs: ...`, `chore: ...`, `refactor: ...`, `test: ...`, `ci: ...`.
   Breaking changes add `!`: `feat!: ...`.
4. Pull requests are squash-merged: the PR title becomes the commit title on
   `main` and decides the next version, the PR description becomes the commit
   body. Write the description as a commit message: why the change is needed,
   plain text.

## Every change: code, docs and translations together

CI checks in every pull request whether documentation and translations still
match the code.

| Check | Fails the PR |
| --- | --- |
| Reference pages (`docs/reference/`) match the code. Regenerate with `python scripts/gen_reference.py` | yes |
| Every message used in the code exists in English and German. `python scripts/check_i18n.py` | yes |
| Other languages are complete | no, report only |
| Documentation builds with `zensical build --strict` (broken links fail) | yes |
| Code under `src/` changed without a change under `docs/` or `README.md` | yes, unless the PR has the label `docs: not needed` |

Rules that make this possible:

- Never edit files under `docs/reference/` by hand; they are generated.
- A new feature, or hardware tested for the first time, updates the Status
  section of `README.md`. No check catches a stale README; reviewers do.
- A visible change to the web page comes with new screenshots:
  `pip install -e ".[screenshots]"`, once `playwright install chromium`, then
  `python scripts/screenshots.py`. A new screen that users need to find gets
  a screenshot in the docs, added to that script.
- Every configuration field has a `description`; it becomes the reference.
- Every user-facing message goes through `t("some.key")` (or, in the core,
  `self._notify("some.key")`) with a literal key, and the key is added to
  `en.json` and `de.json` in the same pull request.

## Code

- Python 3.10 or newer, formatted and linted with ruff, type-checked with mypy
  (strict).
- Tests with pytest. Test behaviour, not implementation: one assertion per
  test, names that say what should happen, mocks only at system boundaries
  (network, devices, clock).

```bash
ruff format . && ruff check . && mypy && pytest
python scripts/gen_reference.py --check
python scripts/check_i18n.py
zensical build --strict
```

## Commits with AI assistance

jogpad is developed with Claude Code; the README says so once. Commits carry
no trailer for it, neither `Assisted-by` nor `Co-Authored-By`: the latter
makes GitHub list the assistant as a person among the contributors. The human
who opens the pull request is its author and answers for it.

## Releases

Versions follow [Semantic Versioning](https://semver.org/), starting at `0.x`.
[release-please](https://github.com/googleapis/release-please) keeps a release
pull request open that bumps the version and updates `CHANGELOG.md` from the
commit titles. Merging it tags `vX.Y.Z` and creates the GitHub release; the
release publishes the package to PyPI.

An update from the update panel of Mainsail and Fluidd installs the new package
and restarts jogpad, but does not run the installer. So a change that existing
installations only get from the installer ends its pull request title in
`; run the installer again`, for example
`fix: the service waits for the network; run the installer again`. That covers
the service, the udev rule and anything else `scripts/install.sh` sets up, and
the switch macro `src/jogpad/klipper/jogpad.cfg`. The title becomes the
release note, which the update panel links.

## Safety

jogpad moves machines. Changes to jogging, locks or STOP need a test that shows
the behaviour, and a sentence in the pull request on how they were tried on real
hardware (or that they were not).
